from __future__ import annotations

import logging

from pipeline.agenda_extraction_fallback import (
    run_agenda_extraction_pipeline as _run_agenda_extraction_pipeline,
)
from pipeline.agenda_extraction_parser import (
    build_agenda_extraction_prompt,
    iter_fallback_paragraphs,
    parse_llm_agenda_items,
    reconstruct_llm_agenda_content,
)


logger = logging.getLogger("local-ai")


def run_agenda_extraction_pipeline(
    *,
    text: str,
    raw_provider_content: str | None,
    mode: str,
) -> list[dict[str, object]]:
    return _run_agenda_extraction_pipeline(
        text=text,
        raw_provider_content=raw_provider_content,
        mode=mode,
        logger=logger,
    )


__all__ = [
    "build_agenda_extraction_prompt",
    "iter_fallback_paragraphs",
    "parse_llm_agenda_items",
    "reconstruct_llm_agenda_content",
    "run_agenda_extraction_pipeline",
]
