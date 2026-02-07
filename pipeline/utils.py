import uuid
import re
from rapidfuzz import fuzz, process

def validate_ocd_id(ocd_id):
    """
    Strict Validation: Checks if an ID follows the OCD standard.
    Format: ocd-[type]/[uuid]
    """
    pattern = r'^ocd-[a-z]+/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(pattern, ocd_id))

def generate_ocd_id(entity_type):
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

def find_best_person_match(name, existing_people, threshold=90):
    """
    Traditional AI/ML approach: Fuzzy Entity Resolution.
    
    Why this is needed:
    Clerks are inconsistent. One might type 'John Smith' and another 'John A. Smith'.
    Instead of creating two records, we use string mathematics (Levenshtein Distance)
    to see if they are the same person.
    
    Args:
        name (str): The name we just found in a document.
        existing_people (list): A list of Person objects already in our database for this city.
        threshold (int): Similarity score (0-100). 90 is stricter to avoid false matches.
        
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
        match_name, score, index = result
        if score >= threshold:
            # novice-friendly log to show the math in action
            print(f"Fuzzy Match Found: '{name}' matches '{match_name}' (Score: {score})")
            return choices[match_name]
            
    return None

def is_likely_human_name(name, allow_single_word=False):
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
    
    # 1. Block 'Tech' characters (Emails, URLs, web parameters)
    # Human names in minutes almost never contain these symbols.
    tech_chars = ['@', '://', '.com', '.php', '.gov', '.org', '?', '=', 'www.']
    if any(char in name_lower for char in tech_chars):
        return False

    # 2. Block Lawsuits and Case Names
    # 'al v. City' or 'Menda v John Sanford-Leffingwell' are cases, not people.
    if ' v. ' in name_lower or ' vs ' in name_lower or ' vs. ' in name_lower or ' v ' in name_lower:
        return False

    # 3. Block 'All-Caps Headers'
    # 'TELECONFERENCE LOCATION - MARRIOTT' is a header, not a person.
    # Real names are usually Title Case (Jesse Arreguin).
    if name_clean.isupper() and len(name_clean) > 15:
        return False

    # 4. Word Count Guardrail
    # Most names are 'First Last' or 'First Middle Last'.
    # 1-word (Roll) or 5-word (Menda v John Sanford Leffingwell) are noise.
    word_count = len(name_clean.split())
    if word_count > 4:
        return False
    if word_count < 2 and not allow_single_word:
        return False

    # 5. Expanded Blacklist of common municipal noise
    blacklist = [
        'clerk', 'ordinance', 'item', 'page', 'appendix', 'section', 
        'exhibit', 'table', 'bid', 'solicitation', 'text box',
        'supplemental', 'communications', 'rev -', 'shx text',
        'absent', 'abstain', 'floor', 'suite', 'ave',
        'berkeley', 'ca', 'california', 'artist', 'camera', 'order',
        'public', 'meeting', 'policy', 'update', 'staff', 'manager',
        'dept', 'department', 'center',
        'location', 'marriott', 'granicus', 'teleconference', 'mailto',
        'city of', 'county of', 'state of', 'incorporated', 'district',
        'fund', 'reserve', 'tax', 'budget', 'audit', 'financial', 'vendor',
        'typewritten', 'text', 'attachment', 'packet', 'closed session',
        'infestation', 'corridor', 'meter', 'neighborhood', 'avenue', 'street'
    ]
    
    for word in blacklist:
        if word in name_lower:
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
    if len(name_clean) > 5 and vowel_count == 0:
        return False
    # If it's very long, check density (at least 10% vowels)
    if len(name_clean) > 10 and (vowel_count / len(name_clean)) < 0.10:
        return False

    # 8. End-of-String Cleanup
    # Discard strings ending in weird punctuation like 'Fields Reserve -'
    if not name_clean[-1].isalnum():
        return False
        
    return True
