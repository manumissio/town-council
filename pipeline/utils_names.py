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

    # Reject OCR-style spaced letters like "P R O C L A M A T I O N".
    if SPACED_OCR_PATTERN.match(name_clean):
        return False

    # 1. Block 'Tech' characters (Emails, URLs, web parameters)
    if any(marker in name_lower for marker in TECH_MARKERS):
        return False

    # 2. Block Lawsuits and Case Names
    if any(marker in name_lower for marker in CASE_NAME_MARKERS):
        return False

    # 3. Block 'All-Caps Headers'
    if name_clean.isupper() and len(name_clean) > 15:
        return False

    # 4. Word Count Guardrail
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

    # 5. Smart Blacklisting
    # We split the blacklist into 'Total Noise' and 'Contextual Noise'.

    # TOTAL NOISE: These words are almost NEVER part of a legitimate name.
    # We use word boundaries to avoid 'Catherine' / 'ca' type bugs.
    for pattern in TOTAL_NOISE_PATTERNS:
        if re.search(pattern, name_lower):
            # Special exception: allow 'Street' or 'Avenue' if it looks like a person's name.
            # Names in Legistar are usually Title Case.
            # If it's "Main Street", "Main" is Title Case too.
            # A better heuristic: if it's 2 words and the first word is a common street name (Main, Oak, etc), block it.
            # Or simpler: for 'street'/'avenue', we only block if word_count < 3 AND it's not explicitly trusted.
            if pattern in STREET_LIKE_PATTERNS:
                # If it's "John Street", we might be blocking a person.
                # However, "Main Street" is more common in noise.
                # Let's check if the OTHER words in the name look like a person.
                words = name_clean.split()
                if any(word.lower() in STREET_NAME_DISQUALIFIERS for word in words):
                    return False
                # If it's just two words, and one is 'Street', it's 50/50.
                # In municipal docs, it's 90% a location.
                return False
            return False

    # CONTEXTUAL NOISE: These words are common in municipal docs but ALSO common surnames.
    # We only block them if they are the ENTIRE string and no title was provided.
    if name_lower in CONTEXTUAL_NOISE_WORDS and not allow_single_word:
        return False

    # 6. Check for numeric noise (e.g. 'Meeting 2024')
    if any(char.isdigit() for char in name_clean):
        return False

    # 7. Vowel Density Check (Heuristic for OCR Noise)
    # Real names like 'Jesse' or 'Arreguin' have high vowel density.
    # Noise like 'Spl Tax Bds' or 'XF-20' has very low density.
    vowels = set("aeiouy")
    vowel_count = sum(1 for char in name_lower if char in vowels)
    # If the string is long enough, it must have at least one vowel.
    if len(name_clean) > MIN_VOWEL_REQUIRED_LENGTH and vowel_count == 0:
        return False
    # If it's very long, check density (at least 10% vowels).
    if len(name_clean) > MIN_VOWEL_DENSITY_LENGTH and (vowel_count / len(name_clean)) < MIN_VOWEL_DENSITY_RATIO:
        return False

    # 8. End-of-String Cleanup
    # Discard strings ending in weird punctuation like 'Fields Reserve -'
    if not name_clean[-1].isalnum():
        return False

    return True
