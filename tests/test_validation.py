from pipeline.utils import validate_ocd_id

def test_validate_ocd_id_valid():
    """
    Test: Does the validator accept correct OCD-IDs?
    """
    valid_id = "ocd-person/550e8400-e29b-41d4-a716-446655440000"
    assert validate_ocd_id(valid_id) is True

def test_validate_ocd_id_invalid():
    """
    Test: Does the validator reject malformed IDs?
    """
    invalid_ids = [
        "ocd-person/123", # Not a UUID
        "person/550e8400-e29b-41d4-a716-446655440000", # Missing prefix
        "ocd-PERSON/550e8400-e29b-41d4-a716-446655440000", # Wrong case
        "ocd-person/invalid-uuid-format"
    ]
    for bad_id in invalid_ids:
        assert validate_ocd_id(bad_id) is False
