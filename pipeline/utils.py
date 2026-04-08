from __future__ import annotations

import logging
import re
import uuid
from typing import Final, Protocol, TypedDict

from rapidfuzz import fuzz, process


logger = logging.getLogger(__name__)

OCD_ID_PATTERN: Final = re.compile(
    r"^ocd-[a-z]+/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
SPACED_OCR_PATTERN: Final = re.compile(r"^(?:[A-Za-z]\s+){3,}[A-Za-z]$")
CASE_NAME_MARKERS: Final = (" v. ", " vs ", " vs. ", " v ")
TECH_MARKERS: Final = ("@", "://", ".com", ".php", ".gov", ".org", "?", "=", "www.")
LOWERCASE_PROSE_MIN_WORDS: Final = 3
MAX_HUMAN_NAME_WORDS: Final = 4
MIN_MULTIWORD_NAME_WORDS: Final = 2
MIN_VOWEL_DENSITY_LENGTH: Final = 10
MIN_VOWEL_DENSITY_RATIO: Final = 0.10
MIN_VOWEL_REQUIRED_LENGTH: Final = 5
DEFAULT_PERSON_MATCH_THRESHOLD: Final = 85
COORDINATE_ROUNDING_PRECISION: Final = 2
UTILS_LOGGER_NAME: Final = "utils"
STREET_NAME_DISQUALIFIERS: Final = {"main", "broadway", "avenue", "street", "highway", "road"}
CONTEXTUAL_NOISE_WORDS: Final = {"park", "clerk", "staff", "manager", "ave", "voter"}
TOTAL_NOISE_PATTERNS: Final[tuple[str, ...]] = (
    r"\bordinance\b", r"\bitem\b", r"\bpage\b", r"\bappendix\b", r"\bsection\b",
    r"\bexhibit\b", r"\btable\b", r"\bbid\b", r"\bsolicitation\b", r"text box",
    r"\bsupplemental\b", r"\bcommunications\b", r"rev -", r"shx text",
    r"\babsent\b", r"\babstain\b", r"\bfloor\b", r"\bsuite\b", r"\bave\b",
    r"\bca\b", r"\bcalifornia\b", r"\bartist\b", r"\bcamera\b", r"\border\b",
    r"\bpublic\b", r"\bmeeting\b", r"\bpolicy\b", r"\bupdate\b",
    r"\bdept\b", r"\bdepartment\b", r"\bcenter\b",
    r"\blocation\b", r"\bmarriott\b", r"\bgranicus\b", r"\bteleconference\b", r"\bmailto\b",
    r"city of", r"county of", r"state of", r"incorporated", r"district",
    r"city clerk", r"city manager", r"city attorney", r"staff report",
    r"\bstreet\b", r"\bavenue\b", r"\bblvd\b", r"\broad\b", r"\bhighway\b", r"\bbridge\b",
    r"\blane\b", r"\bway\b", r"\bcourt\b", r"\bdrive\b", r"\bcircle\b",
    r"\bfund\b", r"\breserve\b", r"\btax\b", r"\bbudget\b", r"\baudit\b",
    r"\bfinancial\b", r"\bvendor\b", r"typewritten", r"\btext\b",
    r"\battachment\b", r"\bpacket\b", r"closed session",
    r"\binc\b", r"\bcorp\b", r"\bcorporation\b", r"\bllc\b", r"\bconsulting\b",
    r"\binfestation\b", r"\bcorridor\b", r"\bmeter\b", r"\bneighborhood\b",
    r"\bproject\b", r"\bvoting\b", r"\bpeak\b", r"\bparking\b", r"\bshelter\b",
    r"\brenovation\b", r"\bschedule\b", r"\bcomplaint\b", r"\bnotice\b",
    r"\bonline\b", r"\bdisposal\b", r"\bappeal\b", r"\bupload\b", r"\bdownload\b",
    r"\buse\b", r"\bfreeze\b", r"\bstatus\b", r"\bdraft\b", r"\brev\b",
    r"\bconcerns\b", r"\benvironmental\b", r"\bprogram\b", r"\bcommittee\b",
    r"\bcommission\b", r"\bcouncil\b", r"\bboard\b", r"\bagency\b", r"\bauthority\b",
    r"\bcamera\b", r"\bcameras\b", r"\bworn\b", r"\bbody worn\b",
)
STREET_LIKE_PATTERNS: Final = {r"\bstreet\b", r"\bavenue\b"}


class PersonLike(Protocol):
    name: str


class PdfCoordinate(TypedDict):
    page: int
    x: float
    y: float
    width: float
    height: float


def validate_ocd_id(ocd_id: str) -> bool:
    """
    Strict Validation: Checks if an ID follows the OCD standard.
    Format: ocd-[type]/[uuid]
    """
    return bool(OCD_ID_PATTERN.match(ocd_id))


def generate_ocd_id(entity_type: str) -> str:
    """
    Generates a standardized Open Civic Data (OCD) identifier.
    
    Why this is needed:
    Following the OCD standard ensures our data is interoperable with 
    other civic projects. Standard format: ocd-[type]/[uuid]
    
    Args:
        entity_type (str): The type of entity (e.g., 'event', 'person', 'organization', 'agendaitem')
        
    Returns:
        str: A unique OCD-compliant identifier.
    """
    unique_id = str(uuid.uuid4())
    # OCD-IDs are lowercase and use hyphens
    return f"ocd-{entity_type.lower()}/{unique_id}"


def find_best_person_match(
    name: str,
    existing_people: list[PersonLike],
    threshold: int = DEFAULT_PERSON_MATCH_THRESHOLD,
) -> PersonLike | None:
    """
    Traditional AI/ML approach: Fuzzy Entity Resolution.
    
    Why this is needed:
    Clerks are inconsistent. One might type 'John Smith' and another 'John A. Smith'.
    Instead of creating two records, we use string mathematics (Levenshtein Distance)
    to see if they are the same person.
    
    Args:
        name (str): The name we just found in a document.
        existing_people (list): A list of Person objects already in our database for this city.
        threshold (int): Similarity score (0-100). 85 allows middle initials while avoiding false matches.
        
    Returns:
        Person: The matching Person object if found, otherwise None.
    """
    if not existing_people:
        return None

    # We extract names from the Person objects for comparison
    choices = {p.name: p for p in existing_people}
    
    # token_sort_ratio is great for names because it ignores word order and middle initials
    # e.g. 'Smith, John' vs 'John Smith' would score 100
    result = process.extractOne(name, choices.keys(), scorer=fuzz.token_sort_ratio)
    
    if result:
        match_name, score, _index = result
        if score >= threshold:
            # Match diagnostics help explain why we linked a clerk-facing name variant.
            logger.info(
                "people_match.fuzzy_hit candidate_name=%s matched_name=%s score=%s",
                name,
                match_name,
                score,
            )
            return choices[match_name]
            
    return None


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
    vowels = set('aeiouy')
    vowel_count = sum(1 for char in name_lower if char in vowels)
    # If the string is long enough, it must have at least one vowel
    if len(name_clean) > MIN_VOWEL_REQUIRED_LENGTH and vowel_count == 0:
        return False
    # If it's very long, check density (at least 10% vowels)
    if len(name_clean) > MIN_VOWEL_DENSITY_LENGTH and (vowel_count / len(name_clean)) < MIN_VOWEL_DENSITY_RATIO:
        return False

    # 8. End-of-String Cleanup
    # Discard strings ending in weird punctuation like 'Fields Reserve -'
    if not name_clean[-1].isalnum():
        return False
        
    return True


def find_text_coordinates(pdf_path: str, search_text: str) -> list[PdfCoordinate]:
    """
    Finds the exact page and (x, y) coordinates of search_text in a PDF.
    
    Why this is needed:
    To create 'Deep Links' that scroll exactly to the vote/action block.
    """
    import pymupdf
    try:
        doc = pymupdf.open(pdf_path)
        locations: list[PdfCoordinate] = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # search_for returns a list of Rect objects
            found_areas = page.search_for(search_text)
            
            for rect in found_areas:
                locations.append({
                    "page": page_num + 1,
                    "x": round(rect.x0, COORDINATE_ROUNDING_PRECISION),
                    "y": round(rect.y0, COORDINATE_ROUNDING_PRECISION),
                    "width": round(rect.width, COORDINATE_ROUNDING_PRECISION),
                    "height": round(rect.height, COORDINATE_ROUNDING_PRECISION),
                })
        
        doc.close()
        return locations
    except (OSError, ValueError, RuntimeError) as exc:
        # PDF coordinate finding errors: What can fail when searching PDFs?
        # - OSError: PDF file not found, corrupted, or locked
        # - ValueError: Invalid PDF structure or malformed page
        # - RuntimeError: PyMuPDF library error (unsupported PDF version)
        # Why return empty list? Caller can handle gracefully (no coordinates = no verification)
        logger.error("Error finding coordinates in %s: %s", pdf_path, exc)
        return []
