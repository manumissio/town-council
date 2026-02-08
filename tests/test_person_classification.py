from pipeline.person_linker import (
    has_official_title_context,
    normalize_person_name,
    infer_person_type,
)


def test_official_title_context_detection():
    assert has_official_title_context("Mayor Jesse Arreguin") is True
    assert has_official_title_context("Councilmember Sophie Hahn") is True
    assert has_official_title_context("Jesse Arreguin") is False


def test_normalize_person_name_strips_prefixes():
    assert normalize_person_name("Mayor Jesse Arreguin") == "Jesse Arreguin"
    assert normalize_person_name("Ayes: Sophie Hahn") == "Sophie Hahn"


def test_infer_person_type_defaults_to_mentioned_without_title():
    assert infer_person_type("Jesse Arreguin") == "mentioned"
    assert infer_person_type("Vice Mayor Kate Harrison") == "official"
