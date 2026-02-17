from api.main import normalize_city_filter


def test_city_slug_normalization_defaults_to_ca_prefix():
    assert normalize_city_filter("Berkeley") == "ca_berkeley"
    assert normalize_city_filter("San Mateo") == "ca_san_mateo"


def test_city_slug_normalization_preserves_prefixed_slug():
    assert normalize_city_filter("ca_oakland") == "ca_oakland"
    assert normalize_city_filter("ca-san-jose") == "ca_san_jose"
