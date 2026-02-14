import os
import json
import logging
import threading
import re
from llama_cpp import Llama
from pipeline.utils import is_likely_human_name
from pipeline.config import (
    LLM_CONTEXT_WINDOW,
    LLM_SUMMARY_MAX_TEXT,
    LLM_SUMMARY_MAX_TOKENS,
    LLM_AGENDA_MAX_TEXT,
    LLM_AGENDA_MAX_TOKENS
)

# Setup logging
logger = logging.getLogger("local-ai")

_SUMMARY_DOC_KINDS = {"minutes", "agenda", "unknown"}

def _dedupe_lines_preserve_order(lines):
    """Return unique lines while keeping the first occurrence order."""
    out = []
    seen = set()
    for line in lines:
        key = line.strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _looks_like_attendance_boilerplate(line: str) -> bool:
    """
    Return True when a line is *probably* "how to attend / public comment / ADA" boilerplate.

    Why this exists:
    Agenda PDFs often start with participation instructions (Zoom links, dial-in, ADA info).
    If we feed those lines into the LLM, the model tends to "summarize" the boilerplate.
    """
    if not line:
        return False

    lowered = line.strip().lower()

    # URLs and contact lines are almost never meaningful "meeting content".
    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return True
    if re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", lowered):
        return True

    # Phone numbers and meeting IDs show up in dial-in instructions.
    if re.search(r"\b\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}\b", lowered):
        return True
    if re.search(r"\bmeeting id\b|\bwebinar id\b|\bpasscode\b", lowered):
        return True

    # Common attendance / participation terms.
    boilerplate_fragments = (
        "zoom",
        "webinar",
        "teleconference",
        "livestream",
        "live stream",
        "register in advance",
        "meeting link",
        "join by phone",
        "dial",
        "unmute",
        "raise hand",
        "conference room",
        "virtual meeting",
        "meeting will be held",
        "public comment",
        "public participation",
        "written communications",
        "options to observe",
        "options to participate",
        "attend in person",
        "appear in person",
        "members of the public",
        "submit comments",
        "email comments",
        "communication access",
        "americans with disabilities act",
        "ada",
        "accommodation",
        "auxiliary aids",
        "interpreters",
        "disability-related",
    )
    return any(frag in lowered for frag in boilerplate_fragments)


def _strip_summary_output_boilerplate(summary: str) -> str:
    """
    Backwards-compatible wrapper for summary cleanup.

    New behavior:
    Summaries are normalized into a BLUF-first, plain-text format so the UI never
    needs to render Markdown and never shows teleconference boilerplate.
    """
    return summary


def _strip_summary_boilerplate(text: str) -> str:
    """
    Remove common meeting boilerplate that pollutes both summaries and topic extraction.

    This is intentionally heuristic and conservative:
    - We drop lines that are overwhelmingly "how to attend / Zoom / dial-in / ADA" instructions.
    - If stripping removes too much content, the caller should fall back to the original text.
    """
    if not text:
        return text

    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _looks_like_attendance_boilerplate(line):
            continue
        lines.append(line)

    # De-dupe repeated instruction lines (common in some agenda templates).
    lines = _dedupe_lines_preserve_order(lines)
    return "\n".join(lines).strip()

def _strip_markdown_emphasis(text: str) -> str:
    """
    Remove common Markdown emphasis markers from model output.

    Why this exists:
    The UI renders summaries as plain text. If the model emits Markdown, users see
    raw markers like "**Agenda:**" instead of formatted text.
    """
    if not text:
        return text
    # Keep this conservative: remove only the markers, preserve the inner text.
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def _first_sentence(value: str) -> str:
    """
    Return the first sentence-like chunk (or the whole string if no punctuation).

    This keeps BLUF short and predictable.
    """
    if not value:
        return value
    value = value.strip()
    match = re.search(r"^(.+?[\.!\?])(\s|$)", value)
    return (match.group(1) if match else value).strip()


def _cap_words(value: str, max_words: int = 30) -> str:
    if not value:
        return value
    words = value.strip().split()
    if len(words) <= max_words:
        return value.strip()
    return " ".join(words[:max_words]).rstrip(".,;:") + "."


def _normalize_summary_output_to_bluf(summary: str, source_text: str = "") -> str:
    """
    Normalize summary output into a BLUF-first, plain-text format:

    BLUF: <one-sentence takeaway>.
    - <detail bullet>
    - <detail bullet>

    Requirements:
    - no Markdown markers
    - no teleconference/ADA/how-to-attend boilerplate
    - 3-7 bullets when possible
    """
    if not summary:
        return summary

    raw_lines = [ln.rstrip() for ln in summary.splitlines()]
    cleaned_lines = []
    for raw in raw_lines:
        line = (raw or "").strip()
        if not line:
            continue

        lowered = line.lower()
        # Drop preambles like "Here's a summary..."
        if lowered.startswith("here's a summary") or lowered.startswith("here is a summary"):
            continue
        if lowered.startswith("summary of the meeting"):
            continue

        line = _strip_markdown_emphasis(line).strip()

        # Strip common bullet markers so the output stays consistent.
        # Note: we re-add bullets later using "- ".
        line = re.sub(r"^\s*[\*\-\u2022]+\s*", "", line).strip()
        if not line:
            continue

        # Remove any remaining leading numbering like "1." or "1)".
        line = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", line).strip()
        if not line:
            continue

        if _looks_like_attendance_boilerplate(line):
            continue

        cleaned_lines.append(line)

    cleaned_lines = _dedupe_lines_preserve_order(cleaned_lines)
    if not cleaned_lines:
        # Fall back to something stable instead of returning raw Markdown.
        return "BLUF: Summary unavailable from extracted text.\n- Not enough reliable content to summarize."

    bluf_text = None
    bullets = []
    for line in cleaned_lines:
        if line.lower().startswith("bluf:"):
            bluf_text = line.split(":", 1)[1].strip()
            continue
        bullets.append(line)

    if not bluf_text:
        # Use first bullet/line as the seed for BLUF.
        seed = bullets[0] if bullets else cleaned_lines[0]
        bluf_text = seed

    bluf_text = _cap_words(_first_sentence(bluf_text), max_words=30)
    if bluf_text and not bluf_text.endswith((".", "!", "?")):
        bluf_text = bluf_text.rstrip(".,;:") + "."

    # Drop boilerplate again in case BLUF seed contained it.
    if _looks_like_attendance_boilerplate(bluf_text):
        bluf_text = "Key meeting takeaway is unclear from extracted text."

    # Bound bullet count.
    bullets = [b for b in bullets if b and not _looks_like_attendance_boilerplate(b)]
    bullets = _dedupe_lines_preserve_order(bullets)
    bullets = bullets[:7]

    # Try to keep at least 3 bullets when the model gave enough content.
    if len(bullets) < 3 and len(cleaned_lines) >= 3:
        for extra in cleaned_lines:
            if extra.lower().startswith("bluf:"):
                continue
            if extra in bullets:
                continue
            if _looks_like_attendance_boilerplate(extra):
                continue
            bullets.append(extra)
            if len(bullets) >= 3:
                break
        bullets = bullets[:7]

    # Re-emit canonical format (plain text).
    out_lines = [f"BLUF: {bluf_text}".strip()]
    for b in bullets:
        out_lines.append(f"- {b.strip()}")
    return "\n".join(out_lines).strip()

def prepare_summary_prompt(text: str, doc_kind: str = "unknown") -> str:
    """
    Build a summarization prompt that matches the *document type*.

    Why this matters:
    Some cities publish agenda PDFs without minutes PDFs. If we summarize an agenda
    using a "minutes" prompt, the output will focus on attendance/teleconference
    boilerplate and look incorrect.
    """
    kind = (doc_kind or "unknown").strip().lower()
    if kind not in _SUMMARY_DOC_KINDS:
        kind = "unknown"

    # 1) Clean input to avoid "how to attend" text dominating the summary.
    safe_text = (text or "")[:LLM_SUMMARY_MAX_TEXT]
    stripped = _strip_summary_boilerplate(safe_text)
    # If stripping leaves very little, keep the original so we don't summarize nothing.
    if stripped and len(stripped) >= max(200, int(0.2 * len(safe_text))):
        safe_text = stripped

    if kind == "minutes":
        instruction = (
            "Write a plain-text executive summary of these meeting minutes. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Focus on decisions, actions taken, and vote outcomes.\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )
    elif kind == "agenda":
        instruction = (
            "Write a plain-text executive summary of this meeting agenda. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Focus on the main scheduled items and expected actions.\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )
    else:
        instruction = (
            "Write a plain-text executive summary of this meeting document. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )

    return (
        "<start_of_turn>user\n"
        f"{instruction}\n"
        "Return only the BLUF line and the bullet lines. No extra text.\n"
        f"{safe_text}<end_of_turn>\n"
        "<start_of_turn>model\n"
    )

class LocalAI:
    """
    The 'Brain' of our application.

    Uses a singleton pattern to keep the model loaded in RAM.
    What's a singleton? It means only ONE instance of this class ever exists.
    Why? Loading the AI model takes ~5 seconds and uses ~500MB RAM. We don't want
    to load it multiple times!
    """
    _instance = None  # Stores the single instance
    _lock = threading.Lock()  # Prevents race conditions when multiple threads try to create the instance

    def __new__(cls):
        """
        This special method controls how new instances are created.
        Instead of creating a new instance every time, we return the same one.
        """
        # First check: Is there already an instance? (fast path, no lock needed)
        if cls._instance is None:
            # Multiple threads might reach here at the same time, so we need a lock
            with cls._lock:
                # Second check: Now that we have the lock, double-check no one else created it
                if cls._instance is None:
                    cls._instance = super(LocalAI, cls).__new__(cls)
                    cls._instance.llm = None  # Initialize the model as None (we'll load it later)
        return cls._instance

    def _load_model(self):
        """
        Loads the AI model from disk into memory.

        This is wrapped in a lock because:
        1. Loading takes several seconds
        2. If two threads try to load simultaneously, we'd waste RAM and cause errors
        3. The lock ensures only ONE thread loads the model, others wait
        """
        with self._lock:  # Acquire the lock (other threads will wait here)
            # Check if model is already loaded (another thread may have loaded it while we waited)
            if self.llm is not None:
                return  # Already loaded, nothing to do

            # Find where the model file is stored
            model_path = os.getenv("LOCAL_MODEL_PATH", "/models/gemma-3-270m-it-Q4_K_M.gguf")

            # Make sure the file actually exists
            if not os.path.exists(model_path):
                logger.warning(f"Model not found at {model_path}.")
                return  # Can't load what doesn't exist

            logger.info(f"Loading Local AI Model from {model_path}...")
            try:
                # Load the model (this is slow: ~5 seconds, ~500MB RAM)
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=LLM_CONTEXT_WINDOW,  # Maximum context size (how much text it can process at once)
                    n_gpu_layers=0,  # Don't use GPU (we want this to work on any machine)
                    verbose=False  # Don't print debug info
                )
                logger.info("AI Model loaded successfully.")
            except Exception as e:
                # AI model loading errors: Why keep this broad?
                # llama-cpp-python is an external C++ library that can raise many exception types:
                # - OSError: Model file not found or corrupted
                # - RuntimeError: CUDA/GPU errors, incompatible model format
                # - MemoryError: Model too large for available RAM
                # - ValueError: Invalid parameters (context size, layers)
                # - And potentially others from the underlying C++ code
                # DECISION: Keep broad exception handling here. It's safer to catch everything
                # than to miss a specific error type and crash the entire application.
                logger.error(f"Failed to load AI model: {e}")

    def summarize(self, text, doc_kind: str = "unknown"):
        """
        Generates a 3-bullet summary of meeting text using the local AI model.

        We truncate the input text to avoid exceeding the model's context window.
        """
        self._load_model()
        if not self.llm: return None

        prompt = prepare_summary_prompt(text, doc_kind=doc_kind)

        with self._lock:
            try:
                response = self.llm(prompt, max_tokens=LLM_SUMMARY_MAX_TOKENS, temperature=0.1)
                raw = response["choices"][0]["text"].strip()
                normalized = _normalize_summary_output_to_bluf(raw, source_text=text)
                # If normalization fails unexpectedly, fall back to the raw output so the
                # caller can decide how to handle it (e.g., store raw, retry, etc.).
                return normalized or raw
            except Exception as e:
                # AI inference errors: Why keep this broad?
                # During text generation, the model can fail in unpredictable ways:
                # - RuntimeError: Model context overflow, generation timeout
                # - KeyError: Unexpected response format (model behavior changed)
                # - MemoryError: Generated text too large
                # - CUDA errors: GPU issues during generation
                # DECISION: Catch all errors and return None. The caller handles gracefully.
                # Better to skip summarization than crash the entire pipeline.
                logger.error(f"AI Summarization failed: {e}")
                return None
            finally:
                if self.llm: self.llm.reset()

    def extract_agenda(self, text):
        """
        Extracts individual agenda items from meeting text using the local AI model.

        Returns a list of agenda items with titles, page numbers, and descriptions.
        """
        self._load_model()

        items = []
        seen_titles = set()

        def normalize_spaces(value):
            return re.sub(r"\s+", " ", (value or "")).strip()

        def looks_like_spaced_ocr(value):
            tokens = [t for t in normalize_spaces(value).split(" ") if t]
            if not tokens:
                return False
            single_char_tokens = sum(1 for t in tokens if len(t) == 1 and t.isalpha())
            return (single_char_tokens / len(tokens)) >= 0.6

        def is_noise_title(title):
            lowered = normalize_spaces(title).lower()
            if not lowered:
                return True
            if len(lowered) < 6:
                return True
            if looks_like_spaced_ocr(lowered):
                return True
            if lowered.startswith("http://") or lowered.startswith("https://"):
                return True
            # URLs embedded in a line are almost always boilerplate, not an agenda topic.
            if "http://" in lowered or "https://" in lowered or "www." in lowered:
                return True
            # Dates, times, and location/address lines are metadata, not agenda topics.
            if re.match(r"^[A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}$", title):
                return True
            if re.search(r"\b\d{1,2}:\d{2}\s*(?:a\.m\.|p\.m\.|am|pm)\b", lowered):
                return True
            if re.search(r"\b\d{2,6}\s+[A-Za-z].*(street|st|avenue|ave|road|rd|blvd|boulevard)\b", lowered):
                return True
            if "mayor" in lowered or "councilmembers" in lowered:
                return True
            # Common accessibility / participation boilerplate.
            if re.search(r"\b(disability[- ]related|accommodation\\(s\\)|auxiliary aids|interpreters?)\b", lowered):
                return True
            if re.search(r"\b(brown act|executive orders?)\b", lowered):
                return True
            if re.search(r"\b(communication access information|questions regarding|public comment portion)\b", lowered):
                return True
            if re.search(r"\b(agendas? and agenda reports?|agenda reports? may be accessed)\b", lowered):
                return True
            if re.search(r"\b(may participate in the public comment|meeting will be conducted in accordance)\b", lowered):
                return True
            if re.search(r"\b(city clerk|cityofberkeley\\.info|cityofberkeley\\.org)\b", lowered):
                return True
            if "as follows" in lowered and len(lowered) <= 40:
                return True
            if lowered.endswith(":") and len(lowered) <= 45:
                return True

            # Common meeting header noise that should not become agenda items.
            header_noise = [
                "special closed meeting",
                "calling a special meeting",
                "city council",
                "agenda packet",
                "table of contents",
                "supplemental communications",
                "form letters",
            ]
            if any(token in lowered for token in header_noise):
                return True
            if re.match(r"^district\s+\d+\b", lowered):
                return True

            # Generic procedural placeholders are not user-meaningful topics.
            generic_blacklist = [
                "call to order",
                "roll call",
                "adjournment",
                "pledge of allegiance",
            ]
            if any(token in lowered for token in generic_blacklist):
                return True

            return False

        def add_item(order, title, page_number, description, result=""):
            clean_title = normalize_spaces(title)
            clean_description = normalize_spaces(description) if description else ""
            if is_noise_title(clean_title):
                return
            dedupe_key = clean_title.lower()
            if dedupe_key in seen_titles:
                return
            seen_titles.add(dedupe_key)
            items.append({
                "order": order,
                "title": clean_title,
                "page_number": page_number,
                "description": clean_description,
                "classification": "Agenda Item",
                "result": normalize_spaces(result)
            })

        def is_probable_person_name(value):
            """
            Heuristic guardrail:
            speaker roll lists are often numbered lines with person names.
            """
            clean = normalize_spaces(value)
            if not clean:
                return False
            clean = re.sub(r"\(\d+\)", "", clean).strip()
            lowered = clean.lower()
            # Speaker roll entries frequently contain this phrase.
            if "on behalf of" in lowered:
                return True
            if re.search(
                r"\b(update|plan|zoning|hearing|budget|report|session|meeting|ordinance|resolution|project|communications|adjournment|amendment|specific|corridor|worksession)\b",
                lowered
            ):
                return False
            if is_likely_human_name(clean, allow_single_word=True):
                return True
            # Catch multi-person entries that may include "&" / "and".
            if " and " in lowered or " & " in clean:
                tokens = re.split(r"\s+(?:and|&)\s+|\s+", clean)
                tokens = [t for t in tokens if t]
                if 2 <= len(tokens) <= 8 and all(re.match(r"^[A-Z][A-Za-z'’\.\-]*$", t) for t in tokens):
                    return True
            return False

        def split_text_by_page_markers(raw_text):
            """
            Build page chunks from either explicit OCR tags ([PAGE N]) or document headers
            like "... Page 2". This avoids defaulting everything to page 1 when OCR tags are sparse.
            """
            markers = []
            for match in re.finditer(r"\[PAGE\s+(\d+)\]", raw_text, flags=re.IGNORECASE):
                markers.append((match.start(), int(match.group(1))))
            for match in re.finditer(r"(?im)^.*\bPage\s+(\d+)\s*$", raw_text):
                markers.append((match.start(), int(match.group(1))))

            if not markers:
                return [(1, raw_text)]

            markers.sort(key=lambda item: item[0])

            # Deduplicate near-identical markers that point to same page.
            deduped = []
            for pos, page in markers:
                if deduped and deduped[-1][1] == page and (pos - deduped[-1][0]) < 120:
                    continue
                deduped.append((pos, page))

            chunks = []
            for i, (start_pos, page_num) in enumerate(deduped):
                end_pos = deduped[i + 1][0] if i + 1 < len(deduped) else len(raw_text)
                chunk = raw_text[start_pos:end_pos].strip()
                if chunk:
                    chunks.append((page_num, chunk))
            return chunks or [(1, raw_text)]

        if self.llm:
            # We increase context slightly to catch more items, focusing on the start
            safe_text = text[:LLM_AGENDA_MAX_TEXT]
            
            # PROMPT: We now ask for Page numbers and a clean list.
            # We explicitly tell it to ignore boilerplate and headers.
            prompt = (
                "<start_of_turn>user\n"
                "Extract ONLY the real agenda items from this meeting document. "
                "Include the page number where each item starts. "
                "Format: ITEM [Order]: [Title] (Page [X]) - [Brief Summary]\n\n"
                f"Text:\n{safe_text}<end_of_turn>\n"
                "<start_of_turn>model\n"
                "ITEM 1:"
            )
            
            with self._lock:
                try:
                    response = self.llm(prompt, max_tokens=LLM_AGENDA_MAX_TOKENS, temperature=0.1)
                    raw_content = response["choices"][0]["text"].strip()
                    content = "ITEM 1:" + raw_content
                    pattern = r"ITEM\s+(\d+):\s*(.*?)\s*\(Page\s*(\d+)\)\s*-\s*(.*)"
                    
                    for line in content.split("\n"):
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            order = int(match.group(1))
                            title = match.group(2).strip()
                            page = int(match.group(3))
                            desc = match.group(4).strip()
                            add_item(order, title, page, desc)
                except Exception as e:
                    # AI agenda extraction errors: Same rationale as above
                    # The model can fail during generation, response parsing, or regex matching
                    # DECISION: Log the error but return partial results (items extracted so far)
                    # rather than crashing. The fallback heuristic will catch items anyway.
                    logger.error(f"AI Agenda Extraction failed: {e}")
                finally:
                    if self.llm: self.llm.reset()

        # FALLBACK: If AI fails, use text heuristics with page-aware chunking.
        if not items:
            for page_num, page_content in split_text_by_page_markers(text):
                page_lower = page_content.lower()
                speaker_context = (
                    "communications" in page_lower
                    or "speakers" in page_lower
                    or "public comment" in page_lower
                    or "item #1" in page_lower
                    or "item #2" in page_lower
                )

                # Prefer explicit numbered agenda lines when available.
                numbered_line_pattern = re.compile(
                    r"(?m)^\s*(?:item\s*)?#?\s*(\d{1,2}(?:\.\d+)?|[A-Z]|[IVXLC]+)[\.\):]\s+(.{6,200})$"
                )

                numbered_lines = list(numbered_line_pattern.finditer(page_content))
                if numbered_lines:
                    # If a numbered block is mostly person-name lines, it is likely a speaker list.
                    person_like_count = sum(
                        1 for m in numbered_lines if is_probable_person_name(m.group(2).strip())
                    )
                    person_heavy_numbered_list = (
                        len(numbered_lines) >= 5
                        and (person_like_count / len(numbered_lines)) >= 0.5
                    )

                    for idx, match in enumerate(numbered_lines):
                        marker = match.group(1)
                        title = match.group(2).strip()
                        if is_probable_person_name(title) and (
                            speaker_context or person_heavy_numbered_list
                        ):
                            # Do not promote speaker-name roll calls into agenda topics.
                            continue

                        block_start = match.end()
                        block_end = numbered_lines[idx + 1].start() if idx + 1 < len(numbered_lines) else len(page_content)
                        block_text = page_content[block_start:block_end]
                        vote_match = re.search(r"(?im)\bVote:\s*([^\n\r]+)", block_text)
                        vote_result = vote_match.group(1) if vote_match else ""

                        add_item(
                            len(items) + 1,
                            title,
                            page_num,
                            f"Agenda section {marker}",
                            result=vote_result
                        )
                    continue

                # Fallback for unnumbered formats: use paragraph starts carefully.
                paragraphs = [p.strip() for p in page_content.split("\n\n") if 10 < len(p.strip()) < 1000]

                for p in paragraphs:
                    lines = p.split("\n")
                    if not lines:
                        continue
                    title = re.sub(r"^\s*\d+(?:\.\d+)?[\.\):]?\s*", "", lines[0].strip())

                    # Keep only plausible title lengths and skip common extraction junk.
                    if 10 < len(title) < 150 and not any(
                        b in title.lower() for b in ['page', 'packet', 'continuing']
                    ):
                        if title.lower().startswith("item #"):
                            continue
                        if is_probable_person_name(title):
                            continue
                        desc = (p[:500] + "...") if len(p) > 500 else p
                        add_item(len(items) + 1, title, page_num, desc)
                        # Limit to 3 items per page to reduce noise in fallback
                        if len([it for it in items if it['page_number'] == page_num]) >= 3:
                            break
                            
                if len(items) > 30: break # Cap total items per doc
        
        return items
