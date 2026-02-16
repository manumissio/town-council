def test_tabular_fragment_primary_alpha_density_rejects_short_row():
    from pipeline.llm import _is_tabular_fragment

    assert _is_tabular_fragment(
        "Grant #44 | $125,000 | 02/10/2026",
        "Acct 230-99 4.5%",
        context={"has_active_parent": False},
    )


def test_tabular_fragment_does_not_reject_whitespace_signal_alone():
    from pipeline.llm import _is_tabular_fragment

    assert not _is_tabular_fragment(
        "Approve   Zoning Map Amendment",
        "Adopt ordinance to update residential parking standards.",
        context={"has_active_parent": False},
    )
