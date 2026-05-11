from __future__ import annotations

import re
from typing import Final


SPACED_OCR_PATTERN: Final = re.compile(r"^(?:[A-Za-z]\s+){3,}[A-Za-z]$")
CASE_NAME_MARKERS: Final = (" v. ", " vs ", " vs. ", " v ")
TECH_MARKERS: Final = ("@", "://", ".com", ".php", ".gov", ".org", "?", "=", "www.")
LOWERCASE_PROSE_MIN_WORDS: Final = 3
MAX_HUMAN_NAME_WORDS: Final = 4
MIN_MULTIWORD_NAME_WORDS: Final = 2
MIN_VOWEL_DENSITY_LENGTH: Final = 10
MIN_VOWEL_DENSITY_RATIO: Final = 0.10
MIN_VOWEL_REQUIRED_LENGTH: Final = 5
STREET_NAME_DISQUALIFIERS: Final = {"main", "broadway", "avenue", "street", "highway", "road"}
CONTEXTUAL_NOISE_WORDS: Final = {"park", "clerk", "staff", "manager", "ave", "voter"}
TOTAL_NOISE_PATTERNS: Final[tuple[str, ...]] = (
    r"\bordinance\b",
    r"\bitem\b",
    r"\bpage\b",
    r"\bappendix\b",
    r"\bsection\b",
    r"\bexhibit\b",
    r"\btable\b",
    r"\bbid\b",
    r"\bsolicitation\b",
    r"text box",
    r"\bsupplemental\b",
    r"\bcommunications\b",
    r"rev -",
    r"shx text",
    r"\babsent\b",
    r"\babstain\b",
    r"\bfloor\b",
    r"\bsuite\b",
    r"\bave\b",
    r"\bca\b",
    r"\bcalifornia\b",
    r"\bartist\b",
    r"\bcamera\b",
    r"\border\b",
    r"\bpublic\b",
    r"\bmeeting\b",
    r"\bpolicy\b",
    r"\bupdate\b",
    r"\bdept\b",
    r"\bdepartment\b",
    r"\bcenter\b",
    r"\blocation\b",
    r"\bmarriott\b",
    r"\bgranicus\b",
    r"\bteleconference\b",
    r"\bmailto\b",
    r"city of",
    r"county of",
    r"state of",
    r"incorporated",
    r"district",
    r"city clerk",
    r"city manager",
    r"city attorney",
    r"staff report",
    r"\bstreet\b",
    r"\bavenue\b",
    r"\bblvd\b",
    r"\broad\b",
    r"\bhighway\b",
    r"\bbridge\b",
    r"\blane\b",
    r"\bway\b",
    r"\bcourt\b",
    r"\bdrive\b",
    r"\bcircle\b",
    r"\bfund\b",
    r"\breserve\b",
    r"\btax\b",
    r"\bbudget\b",
    r"\baudit\b",
    r"\bfinancial\b",
    r"\bvendor\b",
    r"typewritten",
    r"\btext\b",
    r"\battachment\b",
    r"\bpacket\b",
    r"closed session",
    r"\binc\b",
    r"\bcorp\b",
    r"\bcorporation\b",
    r"\bllc\b",
    r"\bconsulting\b",
    r"\binfestation\b",
    r"\bcorridor\b",
    r"\bmeter\b",
    r"\bneighborhood\b",
    r"\bproject\b",
    r"\bvoting\b",
    r"\bpeak\b",
    r"\bparking\b",
    r"\bshelter\b",
    r"\brenovation\b",
    r"\bschedule\b",
    r"\bcomplaint\b",
    r"\bnotice\b",
    r"\bonline\b",
    r"\bdisposal\b",
    r"\bappeal\b",
    r"\bupload\b",
    r"\bdownload\b",
    r"\buse\b",
    r"\bfreeze\b",
    r"\bstatus\b",
    r"\bdraft\b",
    r"\brev\b",
    r"\bconcerns\b",
    r"\benvironmental\b",
    r"\bprogram\b",
    r"\bcommittee\b",
    r"\bcommission\b",
    r"\bcouncil\b",
    r"\bboard\b",
    r"\bagency\b",
    r"\bauthority\b",
    r"\bcamera\b",
    r"\bcameras\b",
    r"\bworn\b",
    r"\bbody worn\b",
)
STREET_LIKE_PATTERNS: Final = {r"\bstreet\b", r"\bavenue\b"}


def _passes_obvious_noise_guards(name_clean: str, name_lower: str) -> bool:
    if SPACED_OCR_PATTERN.match(name_clean):
        return False
    if any(marker in name_lower for marker in TECH_MARKERS):
        return False
    if any(marker in name_lower for marker in CASE_NAME_MARKERS):
        return False
    return not (name_clean.isupper() and len(name_clean) > 15)


def _passes_word_count_guards(name_clean: str, allow_single_word: bool) -> bool:
    word_count = len(name_clean.split())
    words = name_clean.lower().split()
    if word_count > MAX_HUMAN_NAME_WORDS:
        return False
    if word_count < MIN_MULTIWORD_NAME_WORDS and not allow_single_word:
        return False
    # Long lowercase phrases are usually prose fragments, not person names.
    if word_count >= LOWERCASE_PROSE_MIN_WORDS and name_clean == name_clean.lower():
        return False
    if words[0] == "the" or words[-1] == "the":
        return False
    return True


def _contains_total_noise(name_clean: str, name_lower: str) -> bool:
    for pattern in TOTAL_NOISE_PATTERNS:
        if re.search(pattern, name_lower):
            if pattern in STREET_LIKE_PATTERNS:
                words = name_clean.split()
                if any(word.lower() in STREET_NAME_DISQUALIFIERS for word in words):
                    return True
                return True
            return True
    return False


def _passes_vowel_density_guard(name_clean: str, name_lower: str) -> bool:
    vowels = set("aeiouy")
    vowel_count = sum(1 for char in name_lower if char in vowels)
    if len(name_clean) > MIN_VOWEL_REQUIRED_LENGTH and vowel_count == 0:
        return False
    if len(name_clean) > MIN_VOWEL_DENSITY_LENGTH and (vowel_count / len(name_clean)) < MIN_VOWEL_DENSITY_RATIO:
        return False
    return True


def is_likely_human_name(name: str | None, allow_single_word: bool = False) -> bool:
    """
    Quality Control: Filters out noise that is definitely not a person.

    Why this is needed:
    NLP models often mistake 'City Clerk', 'Exhibit A', or URLs for a person's name.
    This function uses a 'Bouncer' strategy: if it doesn't look like a name,
    it doesn't get into the database.
    """
    if not name:
        return False

    name_clean = name.strip()
    name_lower = name_clean.lower()
    return (
        _passes_obvious_noise_guards(name_clean, name_lower)
        and _passes_word_count_guards(name_clean, allow_single_word)
        and not _contains_total_noise(name_clean, name_lower)
        and (allow_single_word or name_lower not in CONTEXTUAL_NOISE_WORDS)
        and not any(char.isdigit() for char in name_clean)
        and _passes_vowel_density_guard(name_clean, name_lower)
        and name_clean[-1].isalnum()
    )
