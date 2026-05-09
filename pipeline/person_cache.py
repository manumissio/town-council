from __future__ import annotations

from rapidfuzz import fuzz, process


DEFAULT_PERSON_LINK_THRESHOLD = 85


def normalized_name_key(name):
    return " ".join((name or "").strip().split()).casefold()


def build_city_person_cache(people):
    exact = {}
    fuzzy_choices = []
    fuzzy_map = {}
    for person in people:
        exact[normalized_name_key(person.name)] = person
        fuzzy_choices.append(person.name)
        fuzzy_map[person.name] = person
    return {
        "people": list(people),
        "exact": exact,
        "fuzzy_choices": fuzzy_choices,
        "fuzzy_map": fuzzy_map,
    }


def add_person_to_city_cache(cache, person):
    cache["people"].append(person)
    cache["exact"][normalized_name_key(person.name)] = person
    cache["fuzzy_choices"].append(person.name)
    cache["fuzzy_map"][person.name] = person


def find_best_person_match_cached(name, cache, *, global_exact=None, threshold=DEFAULT_PERSON_LINK_THRESHOLD):
    exact_match = cache["exact"].get(normalized_name_key(name))
    if exact_match is not None:
        return exact_match, "exact"
    if global_exact is not None:
        exact_match = global_exact.get(normalized_name_key(name))
        if exact_match is not None:
            return exact_match, "exact"

    if not cache["fuzzy_choices"]:
        return None, None

    result = process.extractOne(name, cache["fuzzy_choices"], scorer=fuzz.token_sort_ratio)
    if result:
        match_name, score, _index = result
        if score >= threshold:
            return cache["fuzzy_map"][match_name], "fuzzy"
    return None, None
