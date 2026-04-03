# Gemma 4 Local Head-to-Head v1 Writeup

Date: 2026-04-03

## Scope

This was a two-tier diagnostic experiment against the current local-first control model, `gemma-3-270m-custom`.

- Tier 1 asked whether `gemma4:e2b` fit the normal local runtime envelope.
- Tier 2 retried the fit probe and a small smoke A/B run under a temporary higher-memory `inference` container.

This was not a baseline-valid soak or promotion run.

## Outcome

Result: not promising under the current repo integration path.

- Tier 1 failed at the fit gate because the normal `inference` container limit was `4G`.
- Tier 2 passed the fit gate at `10G`, but the treatment smoke arm still breached latency and stability guardrails almost immediately.

## Evidence

### Tier 1

- `gemma4:e2b` initially failed to load with:
  - `model requires more system memory (7.3 GiB) than is available (3.8 GiB)`
- This was a container-envelope issue, not a missing-model issue, once Ollama was upgraded and the model was pulled successfully.

### Tier 2

- The temporary `10G` `inference` cap allowed the fit probe to pass:
  - `experiments/results/model_probes/model_probe_20260403_203901/probe_result.json`
- Control smoke arm completed:
  - `experiments/results/gemma4_ab_control_smoke/tasks.jsonl`
- Treatment smoke arm failed on the first full catalog:
  - `experiments/results/gemma4_ab_treatment_smoke/tasks.jsonl`

Key treatment timings from the first catalog:

- `segment`: `62.450458s`
- `summarize`: `170.434655s` with task failure after timeout/retry behavior

## Root Cause Analysis

The failure was not caused by a single issue. It was a stack interaction:

1. `gemma4:e2b` is much larger than the control model.
- Ollama reported about `7.3 GiB` total memory required for the model.
- By comparison, the control `gemma-3-270m-custom` used about `455.7 MiB`.

2. The repo's HTTP provider uses a conservative transport budget.
- `pipeline/config.py` sets `LOCAL_AI_HTTP_TIMEOUT_SECONDS=60` by default in the `conservative` profile.
- `pipeline/llm_provider.py` applies that same `60s` budget to both `extract_agenda` and `summarize_agenda_items`.
- In conservative mode, summary retries inside the provider are intentionally disabled, so timeouts surface quickly to task orchestration.

3. Agenda prompts in this repo are large enough to stress Gemma 4 under CPU-only local inference.
- `pipeline/llm.py` allows up to `LLM_AGENDA_MAX_TEXT=40000` chars for agenda extraction and up to `LLM_AGENDA_MAX_TOKENS=1500`.
- Ollama logs showed prompt truncation during treatment requests:
  - `truncating input prompt limit=4096 prompt=13257`
  - `truncating input prompt limit=4096 prompt=4183`
- Even after truncation, the model still hit repeated `60s` request limits.

4. The timeout happened at the provider boundary, not because the task runner was broken.
- Worker logs showed:
  - `provider_request ... operation=extract_agenda ... outcome=timeout ... duration_ms=60044.50`
  - `provider_request ... operation=summarize_agenda_items ... outcome=timeout ... duration_ms=60027.83`
- Inference logs matched that:
  - repeated `POST /api/generate` requests ending at `1m0s`
  - `aborting completion request due to client closing the connection`

5. The strongest treatment failure signal was summary retry churn, not segmentation alone.
- Control segmentation for some catalogs was already slow, often around `54-63s`.
- The decisive difference was that control summaries finished in about `6-13s`, while treatment summary on the first catalog timed out, retried, and ended as a task failure.

## Important Artifact Caveat

`experiments/results/gemma4_ab_treatment_smoke/ab_rows.json` is not a pure per-task output artifact for failed rows.

`scripts/collect_ab_results.py` reads current DB state after task execution. Because the same catalogs had already been summarized by the control arm, the treatment `ab_rows.json` can still show summary text for a failed treatment row. For failure analysis, `tasks.jsonl` and the worker/inference logs are the trustworthy ground truth.

## Decision

Decision for this pass: stop.

- Do not advance `gemma4:e2b` to full paired profiling in the current repo setup.
- Do not change the default runtime policy.
- Treat any future Gemma 4 work as a separate opt-in investigation focused on transport budgets, prompt size, or a different runtime envelope.
