from __future__ import annotations


OFFICIAL_TITLE_PREFIXES = (
    "Mayor ",
    "Councilmember ",
    "Vice Mayor ",
    "Chair ",
    "Commissioner ",
)

PERSON_NAME_PREFIXES = (
    "Mayor ",
    "Councilmember ",
    "Vice Mayor ",
    "Chair ",
    "Director ",
    "Commissioner ",
    "Moved by ",
    "Seconded by ",
    "Ayes: ",
    "Noes: ",
    "Ayes : ",
    "Noes : ",
    "Ayes:  ",
    "Noes:  ",
)


def has_official_title_context(raw_name):
    """
    Returns True when the extracted string includes an official title prefix.
    """
    value = (raw_name or "").strip().lower()
    return any(value.startswith(prefix.lower()) for prefix in OFFICIAL_TITLE_PREFIXES)


def normalize_person_name(raw_name):
    """
    Removes role prefixes and normalizes whitespace before matching/saving.
    """
    name = (raw_name or "").strip()
    for prefix in PERSON_NAME_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :].strip()
    return name


def infer_person_type(raw_name):
    """
    Simple classification gate:
    - Official when strong title context is present
    - Mentioned otherwise
    """
    return "official" if has_official_title_context(raw_name) else "mentioned"
