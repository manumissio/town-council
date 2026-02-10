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

def _strip_summary_boilerplate(text: str) -> str:
    """
    Remove common meeting boilerplate that pollutes both summaries and topic extraction.

    This is intentionally heuristic and conservative:
    - We drop lines that are overwhelmingly "how to attend / Zoom / dial-in / ADA" instructions.
    - If stripping removes too much content, the caller should fall back to the original text.
    """
    if not text:
        return text

    boilerplate_line = re.compile(
        r"("
        r"https?://|www\."
        r"|zoom|webinar|register|unmute|raise hand"
        r"|dial\s+\d|meeting id|webinar id|passcode"
        r"|teleconference|livestream|live stream"
        r"|options to observe|options to participate"
        r"|public participation"
        r"|americans with disabilities act|\bada\b|accommodations?|auxiliary aids|interpreters?"
        r")",
        re.IGNORECASE,
    )

    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if boilerplate_line.search(line):
            continue
        lines.append(line)

    return "\n".join(lines).strip()

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
            "Summarize these meeting minutes into 3 bullet points. "
            "Focus on decisions, actions taken, and vote outcomes. "
            "Ignore attendance/teleconference/ADA boilerplate."
        )
    elif kind == "agenda":
        instruction = (
            "Summarize this meeting agenda into 3 bullet points. "
            "Focus on the main scheduled items and expected actions. "
            "Ignore attendance/teleconference/ADA boilerplate."
        )
    else:
        instruction = (
            "Summarize this meeting document into 3 bullet points. "
            "Ignore attendance/teleconference/ADA boilerplate."
        )

    return (
        "<start_of_turn>user\n"
        f"{instruction}\n"
        "No chat, just bullets:\n"
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
                return response["choices"][0]["text"].strip()
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
