import os

from pipeline.llm_provider import HttpInferenceProvider, InProcessLlamaProvider


class LocalAIConfigError(RuntimeError):
    """
    Raised when LocalAI is invoked in an unsafe/unsupported runtime configuration.
    """


def normalize_backend(backend: str | None = None) -> str:
    normalized = (backend or "http").strip().lower()
    if normalized not in {"inprocess", "http"}:
        return "http"
    return normalized


def get_provider(local_ai, *, backend: str | None) -> object:
    backend = normalize_backend(backend)
    if local_ai._provider is None or local_ai._provider_backend != backend:
        if backend == "http":
            local_ai._provider = HttpInferenceProvider()
        else:
            local_ai._provider = InProcessLlamaProvider(local_ai)
        local_ai._provider_backend = backend
    return local_ai._provider

def load_model(
    local_ai,
    *,
    logger,
    llama_cls,
    backend: str | None,
    allow_multiprocess: bool,
    require_solo_pool: bool,
    guardrail_inputs_fn,
    guardrail_message_fn,
    context_window: int,
) -> None:
    if normalize_backend(backend) == "http":
        return

    concurrency, pool = guardrail_inputs_fn()
    guardrail_message = guardrail_message_fn(
        backend=backend,
        allow_multiprocess=allow_multiprocess,
        require_solo_pool=require_solo_pool,
        concurrency=concurrency,
        pool=pool,
    )
    if guardrail_message:
        raise LocalAIConfigError(guardrail_message)

    if llama_cls is None:
        logger.error("Local AI model is unavailable (llama_cpp not installed). Falling back to heuristics.")
        return

    with local_ai._lock:
        if local_ai.llm is not None:
            return

        model_path = os.getenv("LOCAL_MODEL_PATH", "/models/gemma-3-270m-it-Q4_K_M.gguf")
        if not os.path.exists(model_path):
            logger.warning("Model not found at %s.", model_path)
            return

        logger.info("Loading Local AI Model from %s...", model_path)
        try:
            local_ai.llm = llama_cls(
                model_path=model_path,
                n_ctx=context_window,
                n_gpu_layers=0,
                verbose=False,
            )
            logger.info("AI Model loaded successfully.")
        except (MemoryError, OSError, RuntimeError, TypeError, ValueError) as error:
            # llama-cpp can fail for missing/corrupt models, incompatible runtime
            # settings, or exhausted memory. Logging and leaving the model unloaded
            # preserves the existing fail-soft behavior.
            logger.error("Failed to load AI model: %s", error)
