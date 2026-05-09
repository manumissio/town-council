from __future__ import annotations

import logging
from typing import Final, Protocol

from rapidfuzz import fuzz, process


logger = logging.getLogger(__name__)

DEFAULT_PERSON_MATCH_THRESHOLD: Final = 85


class PersonLike(Protocol):
    name: str


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

    # We extract names from the Person objects for comparison.
    choices = {p.name: p for p in existing_people}

    # token_sort_ratio is great for names because it ignores word order and middle initials.
    # e.g. 'Smith, John' vs 'John Smith' would score 100.
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
