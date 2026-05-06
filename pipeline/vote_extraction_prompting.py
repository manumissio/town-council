from __future__ import annotations


def prepare_vote_extraction_prompt(item_title: str, item_text: str, meeting_context: str = "") -> str:
    title = " ".join((item_title or "").split())
    context = " ".join((meeting_context or "").split())
    text = (item_text or "").strip()

    return (
        "<start_of_turn>user\n"
        "Extract vote/outcome details for this council agenda item.\n"
        "Return JSON only. No prose. No markdown.\n"
        "Use this exact schema:\n"
        "{\n"
        '  "outcome_label": "passed|failed|deferred|continued|tabled|withdrawn|no_action|unknown",\n'
        '  "motion_text": "string or null",\n'
        '  "vote_tally_raw": "string or null",\n'
        '  "yes_count": "integer or null",\n'
        '  "no_count": "integer or null",\n'
        '  "abstain_count": "integer or null",\n'
        '  "absent_count": "integer or null",\n'
        '  "confidence": "number between 0 and 1",\n'
        '  "evidence_snippet": "short quote-like snippet from source text or null"\n'
        "}\n"
        "Rules:\n"
        "- If no vote/outcome is present, use outcome_label='unknown' and null vote fields.\n"
        "- Do not invent votes.\n"
        "- If explicit voting terms are missing, lower confidence substantially.\n"
        "- Keep evidence_snippet under 220 characters.\n"
        f"Meeting context: {context}\n"
        f"Agenda item title: {title}\n"
        "Item text:\n"
        f"{text}<end_of_turn>\n"
        "<start_of_turn>model\n"
        "{"
    )
