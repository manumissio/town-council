import logging
import threading
from typing import Callable

try:
    # Optional dependency: we still want the pipeline to run (heuristic fallbacks)
    # even if llama-cpp isn't installed in the current environment.
    from llama_cpp import Llama
except Exception:  # pragma: no cover
    Llama = None

from pipeline.agenda_extraction import (
    build_agenda_extraction_prompt,
    iter_fallback_paragraphs as _iter_fallback_paragraphs,
    parse_llm_agenda_items as _parse_llm_agenda_items,
    run_agenda_extraction_pipeline,
)
from pipeline.agenda_text_heuristics import (
    is_tabular_fragment as _is_tabular_fragment_impl,
    looks_like_agenda_segmentation_boilerplate as _looks_like_agenda_segmentation_boilerplate_impl,
)
from pipeline.agenda_summary import (
    _should_drop_from_agenda_summary as _should_drop_from_agenda_summary_impl,
    deterministic_agenda_items_summary as _deterministic_agenda_items_summary_impl,
    prepare_agenda_items_summary_prompt as _prepare_agenda_items_summary_prompt,
    run_agenda_summary_pipeline,
)
from pipeline.config import (
    AGENDA_SUMMARY_MAX_BULLETS,
    AGENDA_SEGMENTATION_MODE,
    LLM_AGENDA_MAX_TEXT,
    LLM_AGENDA_MAX_TOKENS,
    LLM_CONTEXT_WINDOW,
    LOCAL_AI_ALLOW_MULTIPROCESS,
    LOCAL_AI_BACKEND,
    LOCAL_AI_REQUIRE_SOLO_POOL,
)
from pipeline.llm_provider import (
    HttpInferenceProvider as _HttpInferenceProvider,
    InProcessLlamaProvider as _InProcessLlamaProvider,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from pipeline.local_ai_agenda_compat import (
    agenda_items_summary_is_too_short as _agenda_items_summary_is_too_short_impl,
    deterministic_agenda_items_summary as _legacy_deterministic_agenda_items_summary_impl,
)
from pipeline.local_ai_provider_calls import call_provider_text_or_none, log_provider_failure
from pipeline.local_ai_runtime import (
    LocalAIConfigError as _LocalAIConfigError,
    get_provider as get_runtime_provider,
    load_model as load_runtime_model,
)
from pipeline.runtime_guardrails import (
    local_ai_guardrail_inputs_from_env,
    local_ai_runtime_guardrail_message,
)
from pipeline.text_generation import (
    build_title_spacing_prompt,
    normalize_json_response,
    normalize_summary_output_to_bluf as _normalize_summary_output_to_bluf_impl,
    normalize_title_spacing_output,
    prepare_summary_prompt as _prepare_summary_prompt,
    run_summary_text_pipeline,
    strip_llm_acknowledgements as _strip_llm_acknowledgements_impl,
    strip_summary_boilerplate as _strip_summary_boilerplate_impl,
    strip_summary_output_boilerplate as _strip_summary_output_boilerplate_impl,
)


logger = logging.getLogger("local-ai")

HttpInferenceProvider = _HttpInferenceProvider
InProcessLlamaProvider = _InProcessLlamaProvider
LocalAIConfigError = _LocalAIConfigError
prepare_summary_prompt = _prepare_summary_prompt
prepare_agenda_items_summary_prompt = _prepare_agenda_items_summary_prompt
parse_llm_agenda_items = _parse_llm_agenda_items
iter_fallback_paragraphs = _iter_fallback_paragraphs
_strip_summary_output_boilerplate = _strip_summary_output_boilerplate_impl
_strip_summary_boilerplate = _strip_summary_boilerplate_impl
_strip_llm_acknowledgements = _strip_llm_acknowledgements_impl
_normalize_summary_output_to_bluf = _normalize_summary_output_to_bluf_impl
_looks_like_agenda_segmentation_boilerplate = _looks_like_agenda_segmentation_boilerplate_impl
_is_tabular_fragment = _is_tabular_fragment_impl
_should_drop_from_agenda_summary = _should_drop_from_agenda_summary_impl


def _agenda_items_summary_is_too_short(text: str) -> bool:
    return _agenda_items_summary_is_too_short_impl(text)


def _deterministic_agenda_items_summary(
    items,
    max_bullets: int = 25,
    truncation_meta: dict | None = None,
) -> str:
    return _legacy_deterministic_agenda_items_summary_impl(items, max_bullets, truncation_meta)


class LocalAI:
    """
    The 'Brain' of our application.

    Uses a singleton pattern to keep the model loaded in RAM per Python process.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LocalAI, cls).__new__(cls)
                    cls._instance.llm = None
                    cls._instance._provider = None
                    cls._instance._provider_backend = None
        return cls._instance

    def _get_provider(self):
        # Keep backend selection at the LocalAI boundary so tests and callers can
        # still patch pipeline.llm module constants directly.
        return get_runtime_provider(self, backend=LOCAL_AI_BACKEND)

    def _log_provider_failure(self, operation_label: str, error: Exception) -> None:
        log_provider_failure(logger, operation_label, error)

    def _call_provider_text_or_none(
        self,
        provider_call: Callable[[], str | None],
        *,
        operation_label: str,
    ) -> str | None:
        return call_provider_text_or_none(provider_call, operation_label=operation_label, logger=logger)

    def _load_model(self):
        """
        Load the in-process model while preserving the current guardrail behavior.
        """
        load_runtime_model(
            self,
            logger=logger,
            llama_cls=Llama,
            backend=LOCAL_AI_BACKEND,
            allow_multiprocess=LOCAL_AI_ALLOW_MULTIPROCESS,
            require_solo_pool=LOCAL_AI_REQUIRE_SOLO_POOL,
            guardrail_inputs_fn=local_ai_guardrail_inputs_from_env,
            guardrail_message_fn=local_ai_runtime_guardrail_message,
            context_window=LLM_CONTEXT_WINDOW,
        )

    def summarize(self, text, doc_kind: str = "unknown"):
        """
        Generate a BLUF-first summary of meeting text.
        """
        provider = self._get_provider()
        return run_summary_text_pipeline(
            provider,
            text=text,
            doc_kind=doc_kind,
            call_provider_text_or_none=self._call_provider_text_or_none,
        )

    def generate_json(self, prompt: str, max_tokens: int = 256) -> str | None:
        """
        Generate a JSON object from the model.
        """
        provider = self._get_provider()
        text = self._call_provider_text_or_none(
            lambda: (provider.generate_json(prompt, max_tokens=max_tokens) or "").strip(),
            operation_label="AI JSON generation",
        )
        return normalize_json_response(text)

    def summarize_agenda_items(
        self,
        meeting_title: str,
        meeting_date: str,
        items,
        truncation_meta: dict | None = None,
    ) -> str | None:
        """
        Generate a grounded decision-brief summary from structured agenda items.
        """
        provider = self._get_provider()
        try:
            return run_agenda_summary_pipeline(
                provider,
                meeting_title=meeting_title,
                meeting_date=meeting_date,
                items=items,
                truncation_meta=truncation_meta,
            )
        except ProviderResponseError as error:
            logger.error("AI Agenda Items Summarization failed (response): %s", error)
            logger.info("agenda_summary.counters agenda_summary_fallback_deterministic=%s", 1)
            return _deterministic_agenda_items_summary_impl(
                items,
                max_bullets=AGENDA_SUMMARY_MAX_BULLETS,
                truncation_meta=truncation_meta,
            )
        except (ProviderTimeoutError, ProviderUnavailableError) as error:
            self._log_provider_failure("AI Agenda Items Summarization", error)
            return None
        except Exception as error:
            self._log_provider_failure("AI Agenda Items Summarization", error)
            return None

    def repair_title_spacing(self, raw_line: str) -> str | None:
        """
        Repair spacing/kerning artifacts in a single heading-like line.
        """
        provider = self._get_provider()
        source = (raw_line or "").strip()
        if not source:
            return None

        prompt = build_title_spacing_prompt(source)
        text = self._call_provider_text_or_none(
            lambda: (
                provider.summarize_text(
                    prompt,
                    max_tokens=64,
                    temperature=0.0,
                )
                or ""
            ).strip(),
            operation_label="AI title spacing repair",
        )
        return normalize_title_spacing_output(text)

    def extract_agenda(self, text):
        """
        Extract individual agenda items from meeting text.
        """
        provider = self._get_provider()
        mode = (AGENDA_SEGMENTATION_MODE or "balanced").strip().lower()
        raw_provider_content = None
        prompt = build_agenda_extraction_prompt(text, max_text=LLM_AGENDA_MAX_TEXT)
        try:
            raw_provider_content = (
                provider.extract_agenda(
                    prompt,
                    max_tokens=LLM_AGENDA_MAX_TOKENS,
                    temperature=0.1,
                )
                or ""
            ).strip()
        except (ProviderTimeoutError, ProviderUnavailableError, ProviderResponseError) as error:
            logger.error("%s failed: %s", "AI Agenda Extraction", error)
        except Exception as error:
            # Provider/runtime extraction failures should preserve heuristic fallback behavior.
            logger.error("%s failed: %s", "AI Agenda Extraction", error)
        return run_agenda_extraction_pipeline(
            text=text,
            raw_provider_content=raw_provider_content,
            mode=mode,
        )
