def test_agenda_boilerplate_filter_matches_compacted_strings():
    from pipeline.llm import _looks_like_agenda_segmentation_boilerplate

    assert _looks_like_agenda_segmentation_boilerplate(
        "PUBLIC ADVISORY: THIS MEETING WILL BE CONDUCTED EXCLUSIVELY THROUGH VIDEOCONFERENCE"
    )
    # Extraction sometimes drops spaces/punctuation, so the filter must still work.
    assert _looks_like_agenda_segmentation_boilerplate(
        "PUBLICADVISORYTHISMEETINGWILLBECONDUCTEDEXCLUSIVELYTHROUGHVIDEOCONFERENCE"
    )

