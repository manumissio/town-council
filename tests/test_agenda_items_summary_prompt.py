def test_prepare_agenda_items_summary_prompt_forces_bluf_and_forbids_acknowledgement():
    from pipeline.llm import prepare_agenda_items_summary_prompt

    prompt = prepare_agenda_items_summary_prompt(
        meeting_title="Berkeley City Council",
        meeting_date="2025-11-06",
        items=["Corridors Zoning Update", "San Pablo Avenue Specific Plan"],
    )

    assert "<start_of_turn>model\nBLUF:" in prompt
    assert "Do not acknowledge the prompt" in prompt
