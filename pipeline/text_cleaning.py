import re


_SPACED_ALLCAPS_RE = re.compile(r"\b(?:[A-Z]\s+){2,}[A-Z]\b")
_ALLCAPS_TOKEN_RE = re.compile(r"^[A-Z]{1,5}$")


def _collapse_spaced_allcaps(text: str) -> str:
    """
    Collapse spaced-out ALLCAPS words like:
    "P R O C L A M A T I O N" -> "PROCLAMATION"

    Why this exists:
    Some PDF extraction paths (and some OCR outputs) insert spaces between letters.
    That breaks downstream NLP (topics/summaries) by turning one real word into many tokens.
    """
    if not text:
        return ""

    def _join(match: re.Match) -> str:
        raw = match.group(0)
        # Preserve word boundaries when the extraction inserted extra spacing between words
        # (e.g. "C I T Y  C O U N C I L" should become "CITY COUNCIL", not "CITYCOUNCIL").
        raw = raw.replace("\n", "  ")
        raw = re.sub(r"\s{2,}", "|", raw)  # word breaks
        raw = re.sub(r"\s+", "", raw)      # letter spacing
        raw = raw.replace("|", " ")
        return raw.strip()

    return _SPACED_ALLCAPS_RE.sub(_join, text)

def _collapse_chunked_allcaps_line(line: str) -> str:
    """
    Collapse chunked ALLCAPS header artifacts like:
    - "ANN OT AT ED" -> "ANNOTATED"
    - "B ER K EL EY" -> "BERKELEY"

    Why this exists:
    Some PDFs extract ALLCAPS words as small chunks (1-5 letters) separated by spaces.
    This is different from letter-by-letter spacing, so _collapse_spaced_allcaps won't catch it.

    Safety: We only collapse runs that look like broken-up ALLCAPS words (conservative thresholds)
    to avoid merging normal phrases like "CITY OF CA".
    """
    if not line:
        return ""

    tokens = line.split()
    if len(tokens) < 3:
        return line

    out: list[str] = []
    i = 0
    while i < len(tokens):
        if not _ALLCAPS_TOKEN_RE.match(tokens[i]):
            out.append(tokens[i])
            i += 1
            continue

        j = i
        has_single_letter = False
        has_long_chunk = False
        while j < len(tokens) and _ALLCAPS_TOKEN_RE.match(tokens[j]):
            if len(tokens[j]) == 1:
                has_single_letter = True
            if len(tokens[j]) >= 3:
                has_long_chunk = True
            j += 1

        run = tokens[i:j]
        run_len = len(run)
        # Conservative: If a run mixes a single-letter token with longer chunks (>=3),
        # it's often multiple words smashed together (e.g., "... ION C AL LING ...").
        # Collapsing that produces unreadable gibberish, so skip collapsing in that case.
        should_collapse = ((run_len >= 4) or (run_len >= 3 and has_single_letter)) and not (
            has_single_letter and has_long_chunk
        )
        if should_collapse:
            joined = "".join(run)
            # If the run is very long, it's likely multiple words smashed together by extraction.
            # Collapsing it into one token produces unreadable gibberish (e.g., PROCLAMATIONCALLING...).
            # In that case, keep the original spacing and let downstream filters handle it.
            if len(joined) <= 20:
                out.append(joined)
            else:
                out.extend(run)
        else:
            out.extend(run)

        i = j

    return " ".join(out)


def postprocess_extracted_text(text: str) -> str:
    """
    Clean extracted text for downstream NLP without changing semantics.

    This runs after Tika extraction and before we feed content into:
    - topic tagging
    - summarization
    - agenda segmentation

    Design goal:
    Fix common extraction artifacts (especially spaced-letter ALLCAPS) while keeping
    the original ordering and meaning of the text.
    """
    if not text:
        return ""

    value = text
    value = _collapse_spaced_allcaps(value)
    # Chunked-ALLCAPS artifacts are line-local and should stay line-local to reduce accidental merges.
    value = "\n".join(_collapse_chunked_allcaps_line(line) for line in value.splitlines())
    # Normalize excessive whitespace but keep paragraph breaks.
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{4,}", "\n\n\n", value)
    return value.strip()
