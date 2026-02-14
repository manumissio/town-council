import re


_SPACED_ALLCAPS_RE = re.compile(r"\b(?:[A-Z]\s+){2,}[A-Z]\b")


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
    # Normalize excessive whitespace but keep paragraph breaks.
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{4,}", "\n\n\n", value)
    return value.strip()
