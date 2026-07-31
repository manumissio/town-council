import api.search_support as search_support


def test_search_support_does_not_export_main_patch_lookups() -> None:
    removed_lookup_names = {
        "search_client",
        "facade_callable",
        "facade_value",
        "_api_main",
    }

    assert all(not hasattr(search_support, name) for name in removed_lookup_names)
