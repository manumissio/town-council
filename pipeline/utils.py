import uuid
from rapidfuzz import fuzz, process

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

def find_best_person_match(name, existing_people, threshold=85):
    """
    Traditional AI/ML approach: Fuzzy Entity Resolution.
    
    Why this is needed:
    Clerks are inconsistent. One might type 'John Smith' and another 'John A. Smith'.
    Instead of creating two records, we use string mathematics (Levenshtein Distance)
    to see if they are the same person.
    
    Args:
        name (str): The name we just found in a document.
        existing_people (list): A list of Person objects already in our database for this city.
        threshold (int): Similarity score (0-100). 85 is usually safe for names.
        
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
