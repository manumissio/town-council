# Architecture Decision Record Index

This file is the indexed log of material architecture decisions for Town Council.

Use each entry to record:
- the decision
- the reason it was made
- the affected boundary or contract
- links to the canonical docs that carry the ongoing operational or architecture detail

## 2026-05-17: Retire legacy runtime profiles behind a lifecycle manifest

- Status: Accepted
- Decision:
  - Active runtime profiles are classified in `env/profiles/profile_manifest.csv`.
  - Docker/Ollama `gemma-3-270m-custom` remains the shared default and reproducible baseline.
  - MLX-LM `mlx-community/gemma-3-text-4b-it-4bit` is the preferred M5 Pro opt-in local AI path.
  - Ollama `gemma4:e2b` remains diagnostic only until stronger gate evidence supports promotion.
  - Host-Ollama 270M helper scripts and M1/host-Ollama profiles move to `archive/`.
- Why:
  - The active runtime surface had accumulated historical M1, host-Ollama, Gemma 4, Docker/Ollama, and MLX options without a machine-readable lifecycle policy.
  - Keeping Docker/Ollama 270M preserves reproducible contributor defaults while M5 MLX becomes the practical performance path for the current host.
  - Gemma 4 showed useful instruction-following behavior but still produced empty minutes-summary responses, so it remains diagnostic.
- Affected boundaries:
  - `env/profiles/*.env` contains active runtime profiles only.
  - `env/profiles/profile_manifest.csv` is the active profile inventory.
  - `archive/env/profiles/` and `archive/scripts/` hold historical runtime workflows.
  - Runtime defaults, Compose defaults, API behavior, DB schema, and fallback policy stay unchanged.
- Canonical references:
  - [README.md](../README.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [docs/PERFORMANCE.md](PERFORMANCE.md)

## 2026-05-12: Track Batch G semantic service cleanup helpers

- Status: Accepted
- Decision:
  - Batch G keeps semantic service complexity cleanup behind the stable `semantic_service/main.py` route facade.
  - `semantic_service/candidates.py` owns candidate parsing, metadata filter matching, and dedupe helpers.
  - `semantic_service/filters.py` owns semantic filter validation and Meilisearch filter wrapping.
  - `semantic_service/retrieval.py` owns semantic retrieval orchestration, lexical recall, fallback diagnostics, and vector expansion.
  - `semantic_service/hydration.py` owns DB hydration and final semantic response assembly.
- Why:
  - Batch G reduced the last semantic service god-module and Radon hotspot without changing `/search/semantic`, `/health`, diagnostics, backend selection, DB session ownership, or monkeypatch seams.
  - Keeping docs and guardrails in one follow-up PR avoids source-map conflicts across the staged semantic service code PRs.
- Affected boundaries:
  - `semantic_service/main.py` remains the ASGI app, route facade, runtime env owner, DB dependency owner, and compatibility patch surface.
  - Helper modules receive dependencies explicitly and do not import `semantic_service.main`.
  - Radon and Vulture remain advisory local audits, not CI gates.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-11: Track Batch F complexity cleanup helpers

- Status: Accepted
- Decision:
  - Batch F keeps complexity cleanup behind stable facades and enrolls the merged helper modules in repository guardrails.
  - `api/search_read_routes.py` remains the `/search` and `/metadata` route facade while `api/search_read_*` helpers own lexical parameter building, Meilisearch error mapping, and people metadata truncation.
  - `pipeline/city_coverage_audit.py` remains the city coverage audit contract while `pipeline/city_coverage_*` helpers own contracts, month windows, bucket ingestion, SQL row loading, and summary assembly.
  - `pipeline/lineage_service.py` remains the lineage assignment entrypoint while `pipeline/lineage_*` helpers own graph construction, confidence calculation, and catalog row mutation.
  - `scripts/operator_profile_ab.py` remains the operator A/B report facade while `scripts/operator_profile_ab_aggregate.py` owns arm aggregation.
- Why:
  - Batch F reduced remaining Radon D/E hotspots without changing public API, CLI, data, metrics, runtime defaults, or CI policy.
  - Keeping docs and guardrails in one follow-up PR avoids source-map conflicts across parallel code PRs.
- Affected boundaries:
  - Public facades stay import-compatible.
  - Helper modules do not import their facades.
  - Radon and Vulture remain advisory local audits, not CI gates.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-11: Track Batch E cleanup helpers and audit tools

- Status: Accepted
- Decision:
  - `scripts/evaluate_soak_week.py` and `scripts/collect_ab_results.py` remain operator CLI facades while gate evaluation and A/B row normalization live behind focused helper modules.
  - `pipeline/cli_logging.py` and `scripts/operator_numeric.py` own shared helper behavior extracted during Batch E.
  - `pipeline/agenda_qa.py`, `pipeline/agenda_resolver_quality.py`, and `pipeline/utils_names.py` remain tracked agenda/person scoring surfaces.
  - `vulture==2.16` and `radon==6.0.1` are pinned as development-only local audit tools, not CI gates.
- Why:
  - Batch E reduced dead code, duplicate helper drift, and high-complexity reporting/quality code without changing runtime behavior.
  - Keeping docs and guardrail enrollment in one follow-up PR avoids source-map conflicts across parallel code PRs.
- Affected boundaries:
  - Operator commands, JSON/stdout contracts, API behavior, runtime defaults, and CI policy scope stay unchanged.
  - Guardrails track the new helper families under the 300-line cleanup target and keep helper modules from importing their facades.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [docs/PERFORMANCE.md](PERFORMANCE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-10: Split LocalAI compatibility helpers behind the facade

- Status: Accepted
- Decision:
  - `pipeline/llm.py` remains the public `LocalAI` product-policy boundary and keeps singleton state, runtime config aliases, provider aliases, and helper compatibility exports.
  - Legacy agenda-summary helper behavior moves behind `pipeline/local_ai_agenda_compat.py`.
  - Provider-call failure wrapping moves behind `pipeline/local_ai_provider_calls.py` while `LocalAI` keeps the method seam.
- Why:
  - `pipeline/llm.py` was the only remaining Python module over the 300-line cleanup target after model/migration cleanup.
  - Moving helper logic narrows the facade without changing backend selection, fallback policy, provider failure semantics, or monkeypatch paths.
- Affected boundaries:
  - `pipeline.llm.LocalAI` continues to own provider acquisition and interpretation of typed provider failures.
  - Runtime defaults, remote/local fail-fast policy, and deterministic fallback behavior stay unchanged.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-10: Split API task route helpers behind the task route facade

- Status: Accepted
- Decision:
  - `api/task_routes.py` remains the protected task-route facade and `build_task_router` entrypoint.
  - Summary, segmentation, and generation/extraction endpoint decisions move behind focused `api/task_route_*` helpers.
- Why:
  - The task route facade had reached the cleanup size target while still mixing route wiring, cache checks, freshness checks, and enqueue decisions.
  - Passing the task facade, DB session, route parameters, models, and helper dependencies explicitly keeps `api.main` monkeypatch seams intact without helper imports from `api.main`.
- Affected boundaries:
  - Routes, auth dependencies, rate limits, response payloads, task names, enqueue behavior, and task polling remain unchanged.
  - Guardrails track the task API helper family under the 300-line cleanup target.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-10: Split model and migration cleanup seams

- Status: Accepted
- Decision:
  - `pipeline/models.py` remains the public ORM import facade while `Base`, runtime engine setup, civic entities, event/stage entities, and catalog/document/embedding records move behind focused `pipeline/model_*` modules.
  - `pipeline/db_migrate.py` remains the supported additive migration entrypoint while column checks, additive column plans, backfills, and runner/submigration orchestration move behind focused `pipeline/db_migration_*` modules.
  - `pipeline/migrate_v8.py` and `pipeline/migrate_v9.py` remain compatibility wrappers while descriptive implementation modules own pgvector semantic embeddings and catalog lineage columns.
- Why:
  - Models and additive migrations were the largest remaining cleanup targets after hydration CLI cleanup.
  - Existing ORM imports, metadata registration, migration patch seams, SQLite skip behavior, and PostgreSQL migration order must remain stable.
- Affected boundaries:
  - `pipeline.models` keeps exporting `Base`, `db_connect`, `create_tables`, `VECTOR_COLUMN_TYPE`, `IssueType`, and all ORM classes.
  - `pipeline.db_migrate` keeps running core additive migrations before pgvector and lineage submigrations.
  - Guardrails track the model and migration helper families under the 300-line cleanup target.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-09: Split Wave 2 task, search, onboarding, and repair cleanup seams

- Status: Accepted
- Decision:
  - `pipeline/tasks.py`, `api/task_routes.py`, and `pipeline/task_summary_generation.py` remain task/API facades while dispatch, route-status, task-helper, and summary-side-effect logic move behind focused support modules.
  - `api/search_support.py` remains the compatibility surface while shared filter, trends, semantic, and client helper logic moves behind focused `api/search/*_support.py` modules.
  - `scripts/evaluate_city_onboarding.py` remains the CLI facade while city metric collection and gate/report rendering move behind focused `pipeline/city_onboarding_*` modules.
  - `scripts/repair_san_mateo_laserfiche_backlog.py` remains the CLI facade while Laserfiche parsing/contracts, PDF I/O, download/classification, and backlog mutation move behind focused `scripts/laserfiche_repair_*` modules.
- Why:
  - These files were the lowest-conflict cleanup targets left after the provider/person/reporting split.
  - Existing task names, API routes, operator commands, JSON/stdout contracts, and patch seams must remain stable.
- Affected boundaries:
  - Celery retry/session ownership, API task dispatch, search response helpers, onboarding artifacts, Laserfiche repair mutation/reindex behavior, and operator exit codes stay unchanged.
  - Guardrails track the new module families under the 300-line cleanup target.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-10: Split downloader, NLP, and segment-city cleanup seams

- Status: Accepted
- Decision:
  - `pipeline/downloader.py` remains the downloader import facade while archive, media fetch, processing, and staged selection logic move behind focused `pipeline/downloader_*` modules.
  - `pipeline/nlp_worker.py` remains the NLP/entity facade while candidate text, extraction, and model-loading policy move behind focused `pipeline/nlp_entity_*` modules.
  - `scripts/segment_city_corpus.py` remains the CLI and subprocess import facade while selection, worker, runner, and contract logic move behind focused `scripts/segment_city_*` modules.
- Why:
  - These were the lowest-conflict targets left after PR #65 and can be cleaned in parallel without touching repaired hydration, models, or DB migration.
  - Downloader patch seams, NLP model compatibility, and segment subprocess imports must remain stable.
- Affected boundaries:
  - Downloader DB/archive behavior, entity payload shape, city segmentation CLI output, and subprocess `_segment_catalog_inline` import stay unchanged.
  - Guardrails track the new module families under the 300-line cleanup target.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-10: Split hydration CLI cleanup seams

- Status: Accepted
- Decision:
  - `scripts/staged_hydrate_cities.py` remains the city-wide hydration CLI facade while segment wrapping, chunk-loop orchestration, snapshots, output rendering, and shared counts move behind focused hydration helper modules.
  - `scripts/hydrate_repaired_city_catalogs.py` remains the repaired-catalog CLI facade while selectors, extract, segment, summary, run-status lifecycle, and shared count/output logic move behind focused hydration helper modules.
- Why:
  - These operator scripts were the largest remaining non-model cleanup targets after the segment-city split.
  - Existing CLI arguments, JSON/stdout contracts, run-status artifacts, and private patch seams must remain stable.
- Affected boundaries:
  - DB session ownership, extracted catalog ID flow, segment/summary timeout scoping, `MaintenanceRunStatus` artifact writes, and segment-city facade usage stay unchanged.
  - Guardrails track the new hydration helper family under the 300-line cleanup target.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-09: Split parallel Wave 1 legacy cleanup seams behind stable entrypoints

- Status: Accepted
- Decision:
  - Profiling and soak-reporting scripts remain CLI entrypoints while shared artifact loading, metric deltas, baseline comparison, and report rendering move behind focused `scripts/operator_profile_*` and `scripts/pipeline_profile_*` helpers.
  - `pipeline/http_inference_provider.py` remains the HTTP provider compatibility surface while retry attempts, payload parsing, provider policy, typed errors, and telemetry helpers move behind focused `pipeline/http_inference_*` modules.
  - `pipeline/utils.py` and `pipeline/person_linker.py` remain public import surfaces while OCD ID helpers, name policy, fuzzy matching, PDF coordinates, person selection, mutation, and cache helpers move behind focused `pipeline/utils_*` and `pipeline/person_*` modules.
- Why:
  - The largest remaining cleanup targets were independent enough to split in parallel without touching `pipeline/tasks.py`, hydration/repair scripts, or `pipeline/models.py`.
  - Existing operator output, provider import seams, and person-linking side effects must stay stable while reducing module size and review risk.
- Affected boundaries:
  - CLI JSON/stdout contracts, provider timeout/retry/error mapping, telemetry labels, person matching thresholds, reindex behavior, and DB session ownership stay unchanged.
  - Guardrails track the new helper families under the 300-line cleanup target.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-08: Split indexing, semantic backend helpers, and summary text runtime behind facades

- Status: Accepted
- Decision:
  - `pipeline/indexer.py` remains the compatibility facade for full and targeted Meilisearch indexing.
  - Search document payload assembly moves behind `pipeline/indexer_documents.py`.
  - Meilisearch settings, batch flush, task id, and filtered-delete compatibility helpers move behind `pipeline/indexer_meilisearch.py`.
  - FAISS artifact and row collection helpers move behind `pipeline/semantic_faiss_artifacts.py` and `pipeline/semantic_faiss_rows.py`.
  - Pgvector source-row collection and hybrid rerank diagnostics move behind `pipeline/semantic_pgvector_rows.py` and `pipeline/semantic_pgvector_rerank.py`.
  - `pipeline/text_generation.py`, `pipeline/summary_quality.py`, and `pipeline/summary_backfill.py` remain compatibility facades for summary runtime, quality, and hydration imports.
  - Summary formatting, prompting, source-quality checks, grounding, and hydration runner/query helpers move behind focused `pipeline/summary_*` modules.
- Why:
  - Indexing, semantic backend, and summary runtime modules still mixed payload construction, backend compatibility, source quality, grounding, and orchestration after earlier cleanup waves.
  - Existing task, API, script, and test imports patch through the facade modules, so the public import surfaces remain stable.
- Affected boundaries:
  - Meilisearch document shape, semantic diagnostics, BLUF output, low-signal messages, summary hydration counters, task retry/session ownership, and CLI/API contracts stay unchanged.
  - Guardrails track the new module families under the 300-line cleanup target.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-08: Split config behind reload-safe facade

- Status: Accepted
- Decision:
  - `pipeline/config.py` remains the compatibility facade for all config constant imports.
  - Env parsing helpers move behind `pipeline/config_env.py`.
  - Startup, inference, semantic, processing, topic/similarity, and table config move behind focused `pipeline/config_*` loader modules.
  - Focused modules expose typed dataclass payloads and loader functions; they do not assign env-derived constants at import time.
- Why:
  - `pipeline/config.py` mixed runtime policy, provider defaults, batch settings, extraction knobs, and indexing thresholds in one large module.
  - Existing tests use `importlib.reload(pipeline.config)` after env changes, so the facade must recompute constants on each reload instead of thinly re-exporting submodule constants.
- Affected boundaries:
  - Env var names, defaults, invalid-value normalization, and direct constant imports stay unchanged.
  - Guardrails track the config module family under the 300-line cleanup target and strict typed/formatter scope.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-08: Extract shared operator CLI and Prometheus helpers

- Status: Accepted
- Decision:
  - Shared argparse validators and run-id validation move behind `scripts/operator_cli.py`.
  - Shared Prometheus text parsing and metric summing move behind `scripts/operator_prometheus.py`.
  - Operator scripts remain CLI entrypoints and keep existing output contracts.
- Why:
  - Maintenance scripts duplicated integer validators, run-id wrappers, and Prometheus parser helpers.
  - Extracting the shared helpers removes duplication without changing command behavior or operator-visible output.
- Affected boundaries:
  - `--json` output, progress lines, generated artifact names, and existing test patch seams stay unchanged.
  - Larger script orchestration splits remain deferred to later waves.
- Canonical references:
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-08: Split topic generation behind the facade

- Status: Accepted
- Decision:
  - `pipeline/topic_generation.py` remains the compatibility facade for shared topic-generation imports.
  - Topic-generation contracts and constants move behind `pipeline/topic_generation_contracts.py`.
  - Text sanitation, stop words, and place-token policy move behind `pipeline/topic_generation_text.py`.
  - Small-corpus keyword fallback and TF-IDF helpers move behind `pipeline/topic_generation_keywords.py`.
  - Single-catalog task implementation and post-commit reindex move behind `pipeline/topic_generation_task.py`.
  - Batch topic tagging moves behind `pipeline/topic_generation_batch.py`.
- Why:
  - `pipeline/topic_generation.py` mixed contracts, text cleanup, keyword extraction, DB persistence, reindex side effects, and batch tagging in one module.
  - Existing `pipeline.enrichment_tasks` and `pipeline.topic_worker` imports must stay stable.
- Affected boundaries:
  - Celery task identity, retry/session ownership, topic payloads, source-hash semantics, and TF-IDF thresholds stay unchanged.
  - Guardrails track the topic-generation module family under the 300-line cleanup target and strict typed/formatter scope.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-05: Split profile manifest packaging behind patch-safe facade

- Status: Accepted
- Decision:
  - `pipeline/profile_manifest.py` remains the compatibility facade for profiling manifest imports and tests.
  - Manifest constants and typed payload aliases move behind `pipeline/profile_manifest_contracts.py`.
  - Manifest sidecar I/O and validation move behind `pipeline/profile_manifest_io.py`.
  - Extract, segmentation, summary, entity, and organization candidate queries move behind `pipeline/profile_manifest_candidates.py`.
  - People reset safety and people candidate loading move behind `pipeline/profile_manifest_people.py`.
  - Quota normalization, ordered dedupe, shortage validation, and package assembly move behind `pipeline/profile_manifest_builder.py`.
  - Dry-run reporting and selected workload preconditioning move behind `pipeline/profile_manifest_preconditioning.py`.
- Why:
  - `pipeline/profile_manifest.py` mixed JSON sidecar handling, quota selection, SQLAlchemy candidate queries, controlled reset mutation, and safety policy in one large operator module.
  - Existing scripts and tests import or patch `pipeline.profile_manifest`, so the facade must keep resolving patched `db_session` and candidate helpers.
- Affected boundaries:
  - `scripts/build_profile_manifest.py` and `scripts/profile_pipeline.py` keep their imports from `pipeline.profile_manifest`.
  - Manifest JSON shape, baseline profiling CLI behavior, preconditioning safety scope, and selected-workload mutation semantics stay unchanged.
  - Guardrails track the profile manifest module family under the 300-line cleanup target and strict typed/formatter scope.
- Canonical references:
  - [docs/PERFORMANCE.md](PERFORMANCE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-05: Split agenda resolver behind the facade

- Status: Accepted
- Decision:
  - `pipeline/agenda_resolver.py` remains the compatibility facade for segmentation callers and tests.
  - Resolver contracts move behind `pipeline/agenda_resolver_contracts.py`.
  - Agenda quality scoring moves behind `pipeline/agenda_resolver_quality.py`.
  - Legistar filtering and acceptance policy move behind `pipeline/agenda_resolver_legistar_policy.py`.
  - HTML agenda candidate loading moves behind `pipeline/agenda_resolver_html.py`.
  - Page-number enrichment moves behind `pipeline/agenda_resolver_enrichment.py`.
  - Structured-source checks and source-priority orchestration move behind `pipeline/agenda_resolver_runner.py`.
- Why:
  - `pipeline/agenda_resolver.py` mixed contracts, quality scoring, Legistar filtering, HTML candidate loading, page-number enrichment, and resolver orchestration in one typed module.
  - Existing task, worker, API, script, and test imports rely on `pipeline.agenda_resolver`, so facade patch seams must stay active.
- Affected boundaries:
  - Source priority remains `Legistar -> HTML -> LLM`.
  - Segmentation payload shape, resolver log events, and structured-source viability behavior stay unchanged.
  - Guardrails track the agenda resolver module family under the 300-line cleanup target and strict typed/formatter scope.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-05: Split vote extraction behind the facade

- Status: Accepted
- Decision:
  - `pipeline/vote_extractor.py` remains the compatibility facade for task imports, tests, and vote-extraction patch seams.
  - Vote extraction constants, protocols, and typed result contracts move behind `pipeline/vote_extraction_contracts.py`.
  - Prompt construction moves behind `pipeline/vote_extraction_prompting.py`.
  - Model-output JSON parsing and payload normalization move behind `pipeline/vote_extraction_parser.py`.
  - Catalog and meeting context construction move behind `pipeline/vote_extraction_context.py`.
  - Existing-vote skip policy, outcome text policy, and ambiguity penalties move behind `pipeline/vote_extraction_policy.py`.
  - Per-catalog item orchestration and update counters move behind `pipeline/vote_extraction_runner.py`.
- Why:
  - `pipeline/vote_extractor.py` mixed prompt scaffolding, parser contracts, context slicing, existing-vote policy, ambiguity handling, logging, counters, and item update orchestration in one typed module.
  - `pipeline.tasks` and focused tests import through `pipeline.vote_extractor`, so the facade must keep resolving patched config constants and prompt helpers.
- Affected boundaries:
  - `pipeline.tasks` keeps importing `run_vote_extraction_for_catalog` from `pipeline.vote_extractor`.
  - Vote extraction prompt shape, parsed result contract, skip reasons, update payloads, log events, and configuration defaults stay unchanged.
  - Guardrails track the vote extraction module family under the 300-line cleanup target and strict typed/formatter scope.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)

## 2026-05-03: Split agenda-summary maintenance behind the facade

- Status: Accepted
- Decision:
  - `pipeline/agenda_summary_maintenance.py` remains the compatibility facade for agenda-summary maintenance imports.
  - Agenda-summary constants and exception contracts move behind `pipeline/agenda_summary_contracts.py`.
  - Input-bundle filtering and payload budgeting move behind `pipeline/agenda_summary_inputs.py`.
  - Post-commit reindex/embed callback summaries move behind `pipeline/agenda_summary_callbacks.py`.
  - Deterministic batch persistence moves behind `pipeline/agenda_summary_batch.py`.
  - Provider fallback and maintenance-mode routing move behind `pipeline/agenda_summary_fallback.py`.
- Why:
  - `pipeline/agenda_summary_maintenance.py` mixed contracts, filtering, DB persistence, callbacks, fallback routing, and timing helpers in one large module.
  - Keeping the facade preserves `pipeline.backlog_maintenance`, `pipeline.tasks`, and maintenance-script patch seams while narrowing implementation ownership.
- Affected boundaries:
  - `pipeline/backlog_maintenance.py` remains the maintenance-facing facade.
  - `pipeline/agenda_summary_maintenance.py` remains the agenda-summary maintenance compatibility boundary.
  - Post-commit reindex/embed failures remain non-gating and return structured failure summaries.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)

## 2026-05-02: Split worker metrics behind the metrics facade

- Status: Accepted
- Decision:
  - `pipeline/metrics.py` remains the public compatibility facade for worker metrics imports, Celery signal registration, and existing test patch seams.
  - Metric schema definitions move behind `pipeline/metrics_definitions.py`.
  - Provider Redis key handling, recorders, and collector behavior move behind focused `pipeline/metrics_provider_*` modules.
  - Task metric recorders move behind `pipeline/metrics_task_recorders.py`.
  - Celery signal handling and profile-event construction move behind `pipeline/metrics_celery_signals.py` and `pipeline/metrics_profile_events.py`.
- Why:
  - `pipeline/metrics.py` combined metric definitions, provider Redis mirroring, Prometheus collection, Celery signals, profile events, and Redis failure handling in one large module.
  - Preserving the facade keeps scripts, provider telemetry hooks, and tests stable while narrowing implementation ownership.
- Affected boundaries:
  - `pipeline/metrics.py` remains the import and patch boundary.
  - `pipeline/metrics_definitions.py` owns Prometheus metric object definitions.
  - `pipeline/metrics_provider_keys.py` owns Redis-safe provider label encoding and decoding.
  - `pipeline/metrics_provider_collector.py` owns Redis-backed provider metric exposition.
  - `pipeline/metrics_provider_recorders.py` owns provider telemetry writes.
  - `pipeline/metrics_task_recorders.py` owns Celery task, queue-wait, phase-duration, and lineage metric writes.
  - `pipeline/metrics_celery_signals.py` owns Celery task metrics hooks.
  - `pipeline/metrics_profile_events.py` owns task profile-event construction.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/PERFORMANCE.md](PERFORMANCE.md)

## 2026-05-10: Split metrics Redis backend helpers behind the metrics facade

- Status: Accepted
- Decision:
  - `pipeline/metrics.py` remains the public metrics facade and Celery signal registration boundary.
  - Redis client availability, degraded-backend state, and Redis write helpers move to `pipeline/metrics_redis_backend.py`.
  - Prometheus metric names, Redis key labels, collector registration behavior, and signal side effects remain unchanged.
- Why:
  - The metrics facade was at the file-size cap and still owned Redis backend failure handling directly.
  - Moving Redis backend helpers narrows the side-effect boundary without changing provider telemetry or worker metrics contracts.
- Affected boundaries:
  - `pipeline/metrics.py` owns public imports and task signal wiring.
  - `pipeline/metrics_redis_backend.py` owns Redis backend availability and write behavior.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)

## 2026-04-22: Split the search route family behind the search facade

- Status: Accepted
- Decision:
  - `api/search_routes.py` remains the search-family compatibility facade and router aggregator.
  - Search/metadata routes move behind `api/search_read_routes.py`.
  - Semantic proxy search moves behind `api/search_semantic_routes.py`.
  - Trends routes move behind `api/trends_routes.py`.
  - Shared helper logic moves behind `api/search_support.py`.
  - `api.main` remains the FastAPI app entrypoint and public patch surface.
- Why:
  - `api/search_routes.py` had become the largest remaining mixed-responsibility API module after the earlier `api.main` cleanup waves.
  - Search, semantic proxying, and trends share one compatibility family, but they do not need to live in one implementation file.
  - Preserving both `api.search_routes` and `api.main` facade seams keeps current tests, direct helper imports, and monkeypatch paths stable while narrowing implementation ownership.
- Affected boundaries:
  - `api/search_routes.py` remains the compatibility boundary for search-family imports.
  - `api/search_read_routes.py` owns `/search` and `/metadata`.
  - `api/search_semantic_routes.py` owns `/search/semantic`.
  - `api/trends_routes.py` owns `/trends/topics`, `/trends/compare`, and `/trends/export`.
  - `api/search_support.py` owns shared Meilisearch, trends, and semantic proxy helpers.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-20: Extract lineage, people, and reporting routes behind the main API facade

- Status: Accepted
- Decision:
  - `api/main.py` remains the FastAPI app entrypoint, middleware/lifecycle owner, router wiring surface, and compatibility facade.
  - Lineage read routes move behind `api/lineage_routes.py`.
  - People/profile read routes move behind `api/people_routes.py`.
  - Data-quality issue reporting moves behind `api/reporting_routes.py`.
  - `/stats`, `/health`, root, middleware, lifecycle, and router wiring remain in `api/main.py`.
- Why:
  - After lifecycle, search/trends, task, and catalog route extraction, these were the remaining coherent business-route families still embedded in `api/main.py`.
  - Keeping three focused modules avoids recreating a generic miscellaneous route bucket.
  - Preserving `api.main` as the facade keeps dependency overrides, legacy imports, and patch seams stable during the cleanup.
- Affected boundaries:
  - `api/main.py` remains the ASGI app and compatibility boundary.
  - `api/lineage_routes.py` owns lineage HTTP reads while `pipeline/lineage_service.py` keeps owning lineage computation.
  - `api/people_routes.py` owns people/profile HTTP reads.
  - `api/reporting_routes.py` owns protected issue-report submission.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-17: Extract catalog read/status routes behind the main API facade

- Status: Accepted
- Decision:
  - `api/main.py` remains the FastAPI app entrypoint and compatibility facade.
  - Catalog batch reads, raw content reads, and derived-status freshness reads move behind `api/catalog_routes.py`.
  - `api.main._summary_doc_kind_and_hashes` remains intentionally available because task routes use that facade seam for summary freshness checks.
  - Lineage, people, stats, and issue-reporting routes remain deferred.
- Why:
  - After lifecycle, search/trends, and task-route extraction, catalog read/status behavior was the next coherent route family still embedded in `api/main.py`.
  - The moved routes share read-only catalog state, freshness/hash calculation, and low-signal status reporting.
  - Keeping `api.main` as the facade preserves current imports, dependency overrides, and Docker `main:app` behavior while narrowing implementation ownership.
- Affected boundaries:
  - `api/main.py` remains the ASGI app and route-wiring boundary.
  - `api/catalog_routes.py` owns `/catalog/batch`, `/catalog/{catalog_id}/content`, `/catalog/{catalog_id}/derived_status`, and `/catalog/{catalog_id}/agenda_items`.
  - `api/task_routes.py` keeps owning task dispatch while using the `api.main` facade for `_summary_doc_kind_and_hashes`.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-15: Extract API task dispatch routes behind the main facade

- Status: Accepted
- Decision:
  - `api/main.py` remains the FastAPI app entrypoint and compatibility facade.
  - Protected task-dispatch routes and task-status polling move behind `api/task_routes.py`.
  - Existing `api.main` task proxy, `AsyncResult`, dependency override, and monkeypatch seams remain intentionally available during this wave.
  - Catalog content/status reads, lineage, people, stats, and issue-reporting routes remain deferred.
- Why:
  - After the lifecycle/search cleanup wave, task dispatch was the largest coherent route family still embedded in `api/main.py`.
  - The task routes share one boundary: validating cached/precondition state, enqueueing Celery work, and returning task polling details.
  - Keeping `api.main` as the facade preserves current tests and API consumers while narrowing implementation ownership.
- Affected boundaries:
  - `api/main.py` remains the ASGI app and route-wiring boundary.
  - `api/task_routes.py` owns protected generation/extraction enqueue routes and `/tasks/{task_id}`.
  - `pipeline/tasks.py` and `pipeline/enrichment_tasks.py` keep owning worker execution, retries, sessions, and persistence.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-13: Start API main cleanup with lifecycle and search route boundaries

- Status: Accepted
- Decision:
  - `api/main.py` remains the FastAPI app entrypoint and compatibility facade.
  - API lifecycle, database dependency setup, API-key verification, and limiter setup move behind `api/app_setup.py`.
  - Search, semantic proxy, metadata, and trends routes move behind `api/search_routes.py`.
  - Existing `api.main` import and monkeypatch seams remain intentionally available during this wave.
- Why:
  - `api/main.py` had become the next large mixed-responsibility runtime module after the semantic backend extraction.
  - Search, semantic proxy, metadata, and trends form a coherent read-route family with shared Meilisearch/filter behavior.
  - Preserving `api.main` as a facade keeps existing tests and callers stable while narrowing implementation ownership.
- Affected boundaries:
  - `api/main.py` remains the ASGI app and route-wiring boundary.
  - `api/app_setup.py` owns lifecycle/session/auth/limiter setup.
  - `api/search_routes.py` owns search, semantic proxy, metadata, and trends routes.
  - Task enqueue/status, lineage, people, catalog, and issue-reporting endpoints remain deferred.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-06: Use seam creation before the next model-coupled typing wave

- Status: Accepted
- Decision:
  - Strict typing has reached a boundary where direct subtree enrollment would immediately drag model-heavy and helper-heavy dependency debt.
  - The next strict-typing follow-up should create a typed seam around the extraction boundary before attempting the next model-coupled service-layer wave.
- Why:
  - Recent typed-subtree waves exhausted the low-churn utility and medium service-layer candidates that stayed isolated.
  - Probing the next likely candidates showed direct typing would spill into `pipeline.models`, extractor/text-cleaning helpers, and related runtime surfaces.
  - A seam at the extraction boundary reduces transitive drag while preserving current extraction behavior.
- Affected boundaries:
  - `pipeline/extraction_service.py` remains the orchestration layer for extraction reprocessing.
  - extractor, cleaning, and bad-content classification helpers remain dependencies behind narrow typed contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-06: Enroll extraction_service before larger service waves

- Status: Accepted
- Decision:
  - `pipeline/extraction_service.py` is the next strict-typing enrollment target after the seam-creation prep wave.
  - The service should isolate extractor, text-cleaning, and bad-content classification behind local typed wrappers so the typed subtree can expand without dragging those neighbors into the same wave.
  - `pipeline/agenda_service.py` remains deferred because its current import surface still spills into untyped `pipeline.models` and `pipeline.utils`.
- Why:
  - The extraction seam was already in place, which made it the narrowest meaningful post-seam enrollment candidate.
  - A direct agenda-service enrollment would still require broader model/helper typing work.
  - This keeps strict-typing progress incremental while preserving the larger model-coupled service wave for later.
- Affected boundaries:
  - `pipeline/extraction_service.py` remains the extraction orchestration layer.
  - extractor, cleaning, and bad-content classification stay behind locally typed service wrappers.
  - the typed subtree expands by one service file without widening into `pipeline.models`.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-07: Enroll summary_hydration_diagnostics after query-boundary cleanup

- Status: Accepted
- Decision:
  - `pipeline/summary_hydration_diagnostics.py` is enrolled in the typed subtree after a boundary-prep pass that split policy logic from query assembly and localized ORM symbol loading.
  - The module keeps `SummaryHydrationSnapshot` and existing script-visible output semantics stable while containing model/query typing inside the diagnostics boundary.
  - `pipeline/agenda_service.py` remains deferred because it still spills directly into untyped `pipeline.models` and `pipeline.utils`.
- Why:
  - The next honest strict-typing problem after `extraction_service` was the model/query-heavy summary hydration diagnostic boundary.
  - Refactoring that boundary made the module type-clean without widening the strict subtree into the ORM layer.
  - This reduces the cost of later service-layer typing work while preserving current operator workflows.
- Affected boundaries:
  - `pipeline/summary_hydration_diagnostics.py` remains the operator-facing hydration backlog diagnostic boundary.
  - `scripts/diagnose_summary_hydration.py` and `scripts/staged_hydrate_cities.py` keep consuming the same snapshot contract.
  - the typed subtree expands by one diagnostics module without typing `pipeline.models`.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-07: Establish a shared models seam before the next service enrollments

- Status: Accepted
- Decision:
  - Strict typing should stop relying on one-off service wrappers and instead introduce a shared `pipeline.models` access seam for agenda and verification workflows.
  - `pipeline/agenda_service.py` is enrolled through that seam as the first consumer.
  - `pipeline/verification_service.py` adopts the seam selectively for session and catalog/item loading, but remains outside the typed subtree until its remaining local annotation debt is addressed separately.
- Why:
  - Repeated direct-enrollment probes had reached the same structural blocker: broad imports from `pipeline.models` and `pipeline.utils`.
  - A shared seam keeps service modules dependent on the smallest record/query contracts they actually consume.
  - `agenda_service` was the narrowest path to prove the seam is reusable without dragging in a full verification cleanup wave.
- Affected boundaries:
  - `pipeline.models` remains the ORM layer.
  - `pipeline/agenda_verification_model_access.py` becomes the typed boundary for narrow agenda and verification model access.
  - `pipeline/agenda_service.py` remains an agenda-domain service and no longer imports broad ORM symbols directly.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-07: Finish strict typing for the reusable pipeline core

- Status: Accepted
- Decision:
  - Strict typing for the reusable pipeline core is complete once the remaining shared foundations and helper modules are enrolled together.
  - `pipeline/models.py`, `pipeline/utils.py`, and `pipeline/verification_service.py` are enrolled alongside the next reusable helper layer: `pipeline/agenda_resolver.py` and `pipeline/vote_extractor.py`.
  - `pipeline/agenda_crosscheck.py` and `pipeline/agenda_legistar.py` are enrolled with `agenda_resolver.py` because they are now part of the same typed helper boundary.
- Why:
  - The shared `pipeline.models` seam removed the structural blocker that had kept `verification_service` out of the typed subtree.
  - The remaining reusable-core debt was concentrated in typed foundations and helper modules, not in new architecture work.
  - Stopping here keeps strict typing scoped to reusable pipeline modules without widening into worker entrypoints or backend-heavy modules.
- Affected boundaries:
  - `pipeline.models` remains the ORM layer, but its helper surface is now part of the strict typed core.
  - `pipeline.utils` remains the shared utility boundary, now with explicit contracts.
  - `pipeline.verification_service`, `pipeline.agenda_resolver`, and `pipeline.vote_extractor` are part of the reusable typed pipeline core.
  - worker/orchestration modules and backend-heavy modules remain separate follow-ups.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Enforce Ruff formatting for the scoped formatter-ready path set

- Status: Accepted
- Decision:
  - The current formatter-ready path set is mechanically normalized with Ruff and now enforced in CI with a path-scoped `ruff format --check` command.
  - Formatter enforcement remains limited to the existing formatter-ready path set rather than expanding to repo-wide Python coverage.
- Why:
  - The reusable pipeline core is now stable enough to support a dedicated mechanical formatting wave.
  - The repo already had an explicit formatter-ready path set, which made it possible to enforce formatting without widening into unrelated modules.
  - Keeping the formatter command path-scoped preserves low-risk rollout and avoids conflating formatting policy with broader cleanup.
- Affected boundaries:
  - `docs/ENGINEERING_GUARDRAILS.md` remains the human-readable formatter policy.
  - `tests/test_repository_guardrails.py` remains the alignment check for the scoped formatter command.
  - `.github/workflows/python-guardrails.yml` enforces the same explicit path set in CI.
- Canonical references:
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Start legacy cleanup with stale suppression inventory only

- Status: Accepted
- Decision:
  - The first legacy-cleanup wave audits stale suppressions and matching allowlist entries before any structural cleanup.
  - A suppression or allowlist entry is removable only when both the Ruff layer and the repository guardrail layer prove it is stale.
  - Runtime refactors, broad exception-policy rewrites, and wildcard suppression cleanup remain out of scope for this first pass.
- Why:
  - The remaining cleanup debt now splits between low-risk hygiene/config drift and high-risk structural legacy refactors.
  - Some files can look stale in one enforcement layer while still being active in another, so a dual-proof rule avoids accidental policy drift.
  - This creates a narrower, safer baseline for later structural cleanup waves.
- Affected boundaries:
  - `ruff.toml` remains the suppression source of truth.
  - `tests/test_repository_guardrails.py` remains the alignment and enforcement source of truth.
  - `docs/ENGINEERING_GUARDRAILS.md` now states that stale path-specific suppressions should be removed only when both layers prove they are unnecessary.
- Canonical references:
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Refactor the provider boundary before wider runtime cleanup

- Status: Accepted
- Decision:
  - The first structural legacy-cleanup wave targets the inference provider boundary in `pipeline/llm_provider.py` and the provider-facing `LocalAI` methods in `pipeline/llm.py`.
  - Transitional provider shims are removed in favor of explicit operation methods for agenda extraction, summary generation, topic generation, and JSON generation.
  - Provider code owns transport classification, timeout policy, retry-budget policy, payload validation, and provider metrics.
  - `LocalAI` remains the layer that interprets typed provider failures into product behavior such as deterministic fallback or `None`.
- Why:
  - This boundary is smaller, more testable, and more cross-cutting than a first-pass refactor of task orchestration or the full LLM heuristic module.
  - Cleaning the seam preserves Town Council's local-first and fail-fast defaults while reducing duplication and ambiguity around provider errors.
  - Keeping retry ownership above the provider layer avoids hidden orchestration drift.
- Affected boundaries:
  - `pipeline/llm_provider.py` now owns operation-specific provider methods and typed failure mapping.
  - `pipeline/llm.py` continues to own fallback and degradation policy.
  - Runtime profiles and backend defaults remain unchanged.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Extract task families before introducing any generic task wrapper

- Status: Accepted
- Decision:
  - The first `pipeline/tasks.py` cleanup wave extracts family-local helpers for text extraction, vote extraction, and summary generation while keeping the Celery task entrypoints in place.
  - `pipeline/tasks.py` remains the retry boundary: each bound task still owns `SessionLocal()`, rollback, `self.retry(...)`, and final payload shape.
  - The extracted helpers own only family-specific orchestration such as loading records, enforcing preconditions, persisting writes, and running best-effort post-commit side effects.
  - The cleanup intentionally avoids a shared task executor, shared retry engine, or hidden transaction wrapper.
- Why:
  - `pipeline/tasks.py` had repeated inline orchestration, but the repeated parts were not uniform enough to justify a generic wrapper without risking retry and transaction drift.
  - Celery retries need to stay explicit at the task boundary, and DB commit/rollback ownership needs to remain obvious and short-lived.
  - Family-by-family extraction reduces duplication now while preserving current task signatures, retry semantics, and post-write best-effort behavior.
- Affected boundaries:
  - `pipeline/tasks.py` remains the Celery entrypoint layer.
  - Extracted family helpers stay file-local and do not bypass existing domain services such as `pipeline.extraction_service` or `pipeline.vote_extractor`.
  - Higher-risk task families such as agenda segmentation, worker startup handling, and lineage recompute remain separate follow-ups.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Extract the segmentation task family without widening the worker boundary

- Status: Accepted
- Decision:
  - The next `pipeline/tasks.py` cleanup wave extracts the `segment_agenda_task` family into private file-local helpers.
  - The segmentation family now has one helper for the main segmentation flow and one helper for the non-gating post-segmentation vote extraction stage.
  - `segment_agenda_task` remains the retry boundary and continues to own `SessionLocal()`, rollback, `self.retry(...)`, and best-effort failure-status persistence in exception paths.
  - The cleanup does not refactor `pipeline.agenda_worker` or backlog-maintenance segmentation flows in the same wave.
- Why:
  - `segment_agenda_task` was the largest remaining mixed-responsibility task wrapper after the earlier family extractions.
  - Splitting the family locally reduces inline orchestration without hiding retry or transaction semantics behind a generic wrapper.
  - Keeping post-segmentation vote extraction inside the family preserves the rule that segmentation success must survive vote-extraction failure.
- Affected boundaries:
  - `pipeline/tasks.py` remains the Celery entrypoint and retry boundary.
  - `pipeline.agenda_resolver`, `pipeline.agenda_service`, and `pipeline.vote_extractor` keep owning their existing domain logic.
  - `pipeline.agenda_worker` and backlog-maintenance segmentation paths remain separate follow-ups.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Finish `pipeline/tasks.py` by extracting the remaining orchestration clusters

- Status: Accepted
- Decision:
  - The final `pipeline/tasks.py` cleanup wave extracts the remaining orchestration-heavy clusters into dedicated support modules:
    - summary hydration/backfill orchestration
    - lineage recompute orchestration
    - worker startup guardrail and startup purge orchestration
  - `pipeline/tasks.py` remains the Celery and signal entrypoint layer and continues to own visible retry boundaries, task decorators, and task payload boundaries.
  - The cleanup keeps compatibility wrappers for the summary-hydration helper entrypoints so existing maintenance scripts can continue importing them from `pipeline.tasks`.
  - No generic task executor, retry abstraction, or shared transaction wrapper is introduced.
- Why:
  - After the earlier task-family waves, the remaining complexity in `pipeline/tasks.py` no longer represented one task family; it represented three separate orchestration domains.
  - Extracting those domains finishes the file without hiding retry/session ownership or widening into unrelated runtime cleanup.
  - Keeping the summary-hydration entrypoints importable from `pipeline.tasks` preserves maintenance tooling compatibility while moving the real orchestration out of the task module.
- Affected boundaries:
  - `pipeline/tasks.py` is now mostly an entrypoint module.
  - `pipeline/summary_backfill.py` owns backlog selection, summary hydration counting, progress reporting, and embed dispatch orchestration.
  - `pipeline/lineage_task_support.py` owns lineage recompute lock/recompute/metrics orchestration.
  - `pipeline/task_startup.py` owns worker-startup guardrail and startup-purge orchestration.
  - `pipeline/task_runtime.py` centralizes the task logger and shared session factory used by the extracted support modules.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-09: Extract the agenda-summary subsystem before broader `pipeline/llm.py` cleanup

- Status: Accepted
- Decision:
  - The next `pipeline/llm.py` legacy-cleanup wave extracts the agenda-summary subsystem centered on `LocalAI.summarize_agenda_items(...)` into a dedicated support module.
  - `LocalAI` remains the orchestration and provider-policy boundary: it still owns provider acquisition plus interpretation of typed provider failures into deterministic fallback or `None`.
  - The extracted module owns agenda-summary-specific flow only: item coercion/filtering, scaffold construction, prompt assembly, output normalization, grounding/pruning, and deterministic fallback selection.
  - Generic summary generation, JSON generation, agenda extraction heuristics, runtime defaults, and task retry ownership remain unchanged.
- Why:
  - After the provider and task-layer cleanup waves, the agenda-summary path is the narrowest high-value seam left inside `pipeline/llm.py`.
  - The path already has dense contract tests for structure, grounding, truncation disclosure, unknowns, and fallback semantics, which makes cleanup safer than a broad `LocalAI` rewrite.
  - Keeping provider policy in `LocalAI` avoids mixing transport outcomes with summary transformation logic.
- Affected boundaries:
  - `pipeline/llm.py` remains the product-policy boundary for local AI behavior.
  - `pipeline/agenda_summary.py` owns agenda-summary transformation and normalization flow.
  - `pipeline/llm_provider.py` continues to own provider transport, payload validation, timeout policy, retry-budget policy, and typed provider failures.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-05-04: Split summary hydration diagnostics behind the facade

- Status: Accepted
- Decision:
  - `pipeline/summary_hydration_diagnostics.py` remains the operator-facing facade for diagnostic scripts and tests.
  - `pipeline/summary_hydration_diagnostic_contracts.py` owns snapshot contracts, path/root-cause constants, sample bucket names, and model protocols.
  - `pipeline/summary_hydration_diagnostic_policy.py` owns summary-path prediction and primary root-cause selection.
  - `pipeline/summary_hydration_diagnostic_queries.py` owns runtime model loading and the typed SQLAlchemy query facade.
  - `pipeline/summary_hydration_diagnostic_samples.py` owns sample-ID SQLAlchemy query helpers.
  - `pipeline/summary_hydration_diagnostic_builder.py` owns backlog classification and snapshot assembly.
- Why:
  - The diagnostic module had become a mixed contract, policy, query, and snapshot-building boundary.
  - Keeping the facade preserves `scripts/diagnose_summary_hydration.py` and `scripts/staged_hydrate_cities.py` imports.
  - Keeping runtime ORM model loading localized preserves the strict typed subtree boundary.
- Affected boundaries:
  - Operator CLI usage and JSON/text output stay unchanged.
  - New diagnostic modules join strict mypy and scoped formatter guardrails.
- Canonical references:
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)

## 2026-05-03: Split runtime agenda-summary implementation behind the facade

- Status: Accepted
- Decision:
  - `pipeline/agenda_summary.py` remains the runtime agenda-summary compatibility facade for `pipeline.llm` imports and config monkeypatch seams.
  - `pipeline/agenda_summary_items.py` owns item coercion, source text, and drop/noise policy.
  - `pipeline/agenda_summary_scaffold.py` owns scaffold seeds, money references, impacts, unknowns, and single-item mode inputs.
  - `pipeline/agenda_summary_prompting.py` owns structured agenda-summary prompt assembly.
  - `pipeline/agenda_summary_rendering.py` owns deterministic rendering and model-output normalization.
  - `pipeline/agenda_summary_counters.py` owns existing agenda-summary counter log payloads.
  - `pipeline/agenda_summary_pipeline.py` owns provider orchestration, grounding/pruning, and deterministic fallback choice.
- Why:
  - Runtime agenda-summary generation had become a mixed transformation, prompt, rendering, counter, and provider orchestration module.
  - Keeping config-aware wrappers in the facade preserves existing `pipeline.agenda_summary` monkeypatch behavior.
  - Moving the drop policy out of the `pipeline.llm` dependency path lets maintenance input building reuse runtime filtering without importing the full LLM facade.
- Affected boundaries:
  - `pipeline.llm` continues importing runtime agenda-summary names from `pipeline.agenda_summary`.
  - `pipeline/agenda_summary_inputs.py` uses the shared item/drop-policy owner directly.
  - Agenda-summary maintenance modules continue to own persistence, routing, and post-commit side effects.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-05-10: Track Batch D near-cap helper splits in guardrails

- Status: Accepted
- Decision:
  - Batch D keeps near-cap cleanup as facade-preserving module extraction rather than behavior change.
  - `pipeline/summary_backfill_runner.py` remains the summary backfill runner facade while `pipeline/summary_backfill_progress.py` owns progress payloads and count aggregation.
  - `scripts/laserfiche_repair_downloads.py` remains the repair-download facade while `scripts/laserfiche_repair_generated_pdf.py` owns generated-PDF transition polling and fetch retries.
  - `pipeline/vote_extraction_runner.py` remains the vote extraction runner facade while `pipeline/vote_extraction_item.py` owns item skip, update, logging, and counter helpers.
  - `scripts/profile_pipeline_runner.py` and `scripts/operator_profile_metrics.py` remain operator entrypoints/facades while `scripts/profile_pipeline_commands.py`, `scripts/profile_pipeline_results.py`, and `scripts/operator_profile_worker_metrics.py` own focused helper behavior.
  - Code PRs deliberately avoided source-map and guardrail edits; this follow-up records the merged helper modules in docs and repository guardrails.
- Why:
  - Batch D reduced files close to the 300-line cap without changing CLI output, JSON artifact keys, task/session ownership, vote payloads, Laserfiche retry classification, or profiling scrape semantics.
  - Keeping docs and guardrails in one follow-up PR avoids source-map conflicts across parallel code PRs while still preventing new helper modules from escaping cleanup guardrails.
- Affected boundaries:
  - Public facades stay import-compatible.
  - New helper modules do not import their facades.
  - Vote extraction helper scope joins strict typed and formatter guardrails because the existing vote extraction family is already enrolled.
  - Summary backfill, Laserfiche repair, and profile/operator helpers join cleanup-size guardrails without expanding typed or formatter scope.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-09: Extract the agenda-extraction subsystem before finishing broader `pipeline/llm.py` cleanup

- Status: Accepted
- Decision:
  - The next `pipeline/llm.py` legacy-cleanup wave extracts the agenda-extraction subsystem centered on `LocalAI.extract_agenda(...)` into a dedicated support module.
  - `LocalAI` remains the orchestration and provider-policy boundary: it still owns provider acquisition plus interpretation of typed provider failures into heuristic fallback behavior.
  - The extracted module owns agenda-extraction-specific flow only: prompt assembly, provider-output parsing, fallback paragraph/numbered-line parsing, grounding-style acceptance checks, deduplication, and extraction counter logging.
  - Generic summary generation, JSON generation, agenda-summary behavior, runtime defaults, and task retry ownership remain unchanged.
- Why:
  - After the provider cleanup, task extraction waves, and agenda-summary extraction, the agenda-extraction path was the next coherent subsystem still embedded inside `pipeline/llm.py`.
  - That path already had focused regression coverage for prompt budgets, parser behavior, segmentation heuristics, backend parity, and task-facing retry semantics, which made it a safer cleanup target than a full `LocalAI` rewrite.
  - Keeping provider outcome interpretation in `LocalAI` avoids mixing provider-policy behavior with extraction heuristics and normalization code.
- Affected boundaries:
  - `pipeline/llm.py` remains the product-policy boundary for local AI behavior.
  - `pipeline/agenda_extraction.py` owns agenda-extraction transformation and fallback parsing flow.
  - `pipeline/llm_provider.py` continues to own provider transport, payload validation, timeout policy, retry-budget policy, and typed provider failures.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-05-03: Split agenda-extraction implementation behind the facade

- Status: Accepted
- Decision:
  - `pipeline/agenda_extraction.py` remains the public compatibility facade for `LocalAI.extract_agenda(...)`, direct helper imports, and existing `pipeline.llm` aliases.
  - Agenda-extraction implementation now lives in focused modules for prompt/parser behavior, fallback parsing, acceptance gates, page handling, numbered-item handling, paragraph fallback, noise filtering, and diagnostics.
  - `pipeline/llm.py` continues to own provider acquisition plus interpretation of typed provider failures into heuristic fallback behavior.
- Why:
  - The previous extraction moved agenda segmentation out of `pipeline/llm.py`, but `pipeline/agenda_extraction.py` became a mixed-responsibility module.
  - Splitting behind the facade preserves public behavior while making the fallback parser and diagnostics easier to audit.
  - Keeping `agenda_text_heuristics.py` separate avoids mixing shared lexical rules with the agenda-extraction orchestration flow.
- Affected boundaries:
  - `pipeline/agenda_extraction.py` owns facade compatibility only.
  - `pipeline/agenda_extraction_parser.py`, `pipeline/agenda_extraction_fallback.py`, `pipeline/agenda_extraction_acceptance.py`, `pipeline/agenda_extraction_pages.py`, `pipeline/agenda_extraction_noise.py`, `pipeline/agenda_extraction_numbered.py`, `pipeline/agenda_extraction_paragraphs.py`, and `pipeline/agenda_extraction_diagnostics.py` own focused implementation details.
  - `pipeline/llm.py` remains the local AI product-policy boundary.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-05-03: Split agenda text heuristics behind the facade

- Status: Accepted
- Decision:
  - `pipeline/agenda_text_heuristics.py` remains the compatibility facade for shared agenda text helper imports.
  - Shared agenda text behavior now lives in focused modules for normalization, boilerplate/noise detection, item acceptance, fuzzy dedupe, and end-marker policy.
  - Existing callers keep importing through the facade in this wave to avoid broad import-path churn.
- Why:
  - `pipeline/agenda_text_heuristics.py` became the largest shared agenda helper after agenda extraction cleanup.
  - Splitting behind the facade narrows ownership without changing segmentation, summary, or text-generation behavior.
  - Keeping callers on the facade preserves `pipeline.llm` compatibility aliases and reduces monkeypatch/import risk.
- Affected boundaries:
  - `pipeline/agenda_text_heuristics.py` owns facade compatibility only.
  - `pipeline/agenda_text_normalization.py`, `pipeline/agenda_text_noise.py`, `pipeline/agenda_text_noise_patterns.py`, `pipeline/agenda_item_acceptance.py`, `pipeline/agenda_item_dedupe.py`, and `pipeline/agenda_end_markers.py` own focused helper implementation.
  - `pipeline/llm.py` remains the local AI product-policy boundary.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-09: Finish `pipeline/llm.py` by extracting heuristics, generic generation, and runtime bootstrap

- Status: Accepted
- Decision:
  - The final structural cleanup wave for `pipeline/llm.py` extracts three remaining mixed-responsibility clusters into dedicated support modules:
    - `pipeline/agenda_text_heuristics.py` for shared agenda lexical and filtering heuristics
    - `pipeline/text_generation.py` for generic summary, JSON-generation normalization, and title-spacing generation helpers
    - `pipeline/local_ai_runtime.py` for backend normalization, provider construction, and in-process runtime bootstrap
  - `pipeline/llm.py` remains the public `LocalAI` product-policy boundary and keeps the public methods `summarize(...)`, `generate_json(...)`, `summarize_agenda_items(...)`, `repair_title_spacing(...)`, and `extract_agenda(...)`.
  - `pipeline/llm.py` also keeps compatibility exports for currently used helper seams so in-repo callers and tests do not need a concurrent migration.
  - Provider-failure semantics, runtime defaults, local-first/fail-fast guardrails, and task retry ownership remain unchanged.
- Why:
  - After the provider cleanup plus the agenda-summary and agenda-extraction extractions, the remaining complexity in `pipeline/llm.py` was no longer one coherent subsystem; it was a mix of residual heuristics, generic text-generation code, and runtime/bootstrap code.
  - Extracting those clusters finishes the file structurally without widening into policy redesign or retry/session abstraction changes.
  - Keeping `LocalAI` as the product-policy boundary preserves the current `None` vs deterministic-fallback behavior while making the implementation easier to reason about and test.
- Affected boundaries:
  - `pipeline/llm.py` is now a thin public boundary centered on `LocalAI` plus compatibility exports.
  - `pipeline/agenda_text_heuristics.py` owns shared agenda text heuristics used by agenda extraction, agenda summary, and a small set of compatibility callers.
  - `pipeline/text_generation.py` owns generic summary formatting, JSON normalization, and title-spacing prompt/output helpers.
  - `pipeline/local_ai_runtime.py` owns runtime/bootstrap mechanics and provider construction while `LocalAI` retains the public seam.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-10: Extract the agenda-summary maintenance family before wider backlog-maintenance cleanup

- Status: Accepted
- Decision:
  - The next `pipeline/backlog_maintenance.py` cleanup wave extracts the agenda-summary maintenance family into `pipeline/agenda_summary_maintenance.py`.
  - The extracted module owns agenda-summary bundle construction, deterministic rendering, summary persistence/hash updates, batch reindex/embed timing helpers, and maintenance summary fallback orchestration.
  - `pipeline/backlog_maintenance.py` remains the maintenance-facing compatibility facade for the currently imported summary-maintenance names.
  - The segmentation maintenance family, timeout overrides, and fallback-event capture helpers remain in `pipeline/backlog_maintenance.py` for now.
  - Summary-backfill reporting fields, timing names, progress payloads, `completion_mode` values, retry ownership, and session ownership remain unchanged.
- Why:
  - The agenda-summary maintenance cluster was the clearest coherent seam left in `pipeline/backlog_maintenance.py` after the provider, task, and `pipeline/llm.py` cleanup waves.
  - That cluster was already consumed as a service-style API by `pipeline/summary_backfill.py`, task maintenance flows, and maintenance scripts, so extracting it sharpens an existing boundary instead of introducing a new abstraction.
  - Deferring segmentation maintenance avoids widening this wave into the more fragile timeout/log-capture cluster or into `pipeline/agenda_worker.py` behavior changes.
- Affected boundaries:
  - `pipeline/backlog_maintenance.py` remains the compatibility import surface for maintenance helpers.
  - `pipeline/agenda_summary_maintenance.py` owns agenda-summary maintenance orchestration only.
  - `pipeline/summary_backfill.py` continues to own backlog selection, reporting, and hydration-loop orchestration.
  - `pipeline/tasks.py` and `pipeline/agenda_worker.py` keep their current retry/session and non-maintenance boundaries.

- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-11: Finish backlog-maintenance cleanup by extracting agenda-segmentation maintenance

- Status: Accepted
- Decision:
  - The final structural cleanup wave for `pipeline/backlog_maintenance.py` extracts the agenda-segmentation maintenance family into `pipeline/agenda_segmentation_maintenance.py`.
  - The extracted module owns maintenance timeout overrides, fallback-event capture, heuristic-first segmentation gating, segmentation status persistence, and `segment_catalog_with_mode(...)`.
  - `pipeline/backlog_maintenance.py` remains the maintenance-facing compatibility facade for both agenda-summary and agenda-segmentation maintenance names.
  - Existing task, worker, script, and test import paths remain stable during this wave.
  - Task retry ownership, session ownership, fallback-counter names, segmentation status semantics, and summary-backfill reporting contracts remain unchanged.
- Why:
  - After agenda-summary maintenance was extracted, the remaining behavior in `pipeline/backlog_maintenance.py` formed one coherent segmentation maintenance family plus the timeout/log-capture helpers that support it.
  - Keeping a compatibility facade avoids a broad patch-path migration while still making the domain boundary explicit.
  - Deferring any redesign of log-derived fallback counters keeps this wave focused on structure rather than behavior.
- Affected boundaries:
  - `pipeline/backlog_maintenance.py` is now a compatibility import surface for maintenance helpers.
  - `pipeline/agenda_segmentation_maintenance.py` owns agenda-segmentation maintenance orchestration.
  - `pipeline/agenda_summary_maintenance.py` continues to own agenda-summary maintenance orchestration.
  - `pipeline/agenda_worker.py` and maintenance scripts keep their existing caller-facing contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-11: Start semantic-index cleanup with shared semantic text utilities

- Status: Accepted
- Decision:
  - The first `pipeline/semantic_index.py` cleanup wave extracts shared semantic text normalization, source hashing, and fallback content chunking into `pipeline/semantic_text.py`.
  - `pipeline.semantic_index` remains the public compatibility facade for semantic backend classes, backend selection, and existing text-helper imports.
  - Backend extraction is deferred: `PgvectorSemanticBackend`, `FaissSemanticBackend` / NumPy artifact fallback, and runtime guardrails remain in `pipeline.semantic_index`.
  - Semantic ranking, source-hash semantics, diagnostics, config defaults, and runtime guardrails remain unchanged.
- Why:
  - `pipeline.semantic_index` is directly imported by semantic tasks, semantic service code, and tests, so splitting backend classes first would risk class-identity, singleton, and monkeypatch drift.
  - The shared text helpers are a low-risk boundary that already supports both semantic indexing and embedding freshness checks.
  - Keeping backend internals in place preserves FAISS/NumPy artifact behavior, pgvector rerank SQL, model loading, and guardrail policy while still reducing mixed responsibility in the module.
- Affected boundaries:
  - `pipeline/semantic_text.py` owns semantic text normalization, truncation, source hashing, and fallback chunking.
  - `pipeline/semantic_index.py` remains the semantic backend facade and compatibility import surface.
  - `pipeline/semantic_tasks.py` and `semantic_service/main.py` keep their existing public contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-12: Finish semantic-index cleanup with backend extraction

- Status: Accepted
- Decision:
  - The final structural cleanup wave for `pipeline/semantic_index.py` extracts backend contracts into `pipeline/semantic_backend_types.py`.
  - Pgvector embedding build and hybrid rerank implementation move into `pipeline/semantic_pgvector_backend.py`.
  - FAISS direct vector search, NumPy fallback behavior, and artifact read/write implementation move into `pipeline/semantic_faiss_backend.py`.
  - Runtime guardrail detection and backend selection helpers move into `pipeline/semantic_backend_runtime.py`.
  - `pipeline.semantic_index` remains the public compatibility facade and monkeypatch surface for existing callers and tests.
  - Semantic ranking, source-hash semantics, diagnostics, config defaults, FAISS retirement policy, and runtime guardrails remain unchanged.
- Why:
  - The prior semantic cleanup wave deliberately deferred backend extraction to avoid class-identity, singleton, and monkeypatch drift.
  - Keeping `pipeline.semantic_index` as a facade preserves imports from semantic tasks, semantic service code, scripts, and tests while letting each backend own its implementation details.
  - Pgvector, FAISS/NumPy, and runtime selection are separate orchestration domains, so extracting them sharpens boundaries without introducing a generic vector-backend framework.
- Affected boundaries:
  - `pipeline/semantic_index.py` remains the semantic backend facade and compatibility import surface.
  - `pipeline/semantic_backend_types.py` owns shared backend contracts and result types.
  - `pipeline/semantic_pgvector_backend.py` owns pgvector build and hybrid rerank behavior.
  - `pipeline/semantic_faiss_backend.py` owns FAISS/NumPy artifact and direct vector query behavior.
  - `pipeline/semantic_backend_runtime.py` owns runtime guardrail detection and backend selection helpers.
  - `pipeline/semantic_tasks.py` and `semantic_service/main.py` keep their existing public contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-26: Start task facade cleanup with extraction and vote support modules

- Status: Accepted
- Decision:
  - The first structural cleanup wave for `pipeline/tasks.py` extracts agenda-title parsing into `pipeline/task_agenda_titles.py`.
  - Text re-extraction task support moves into `pipeline/task_text_extraction.py`.
  - Vote-extraction task support moves into `pipeline/task_vote_extraction.py`.
  - Shared task reindex failure categories move into `pipeline/task_side_effects.py`.
  - `pipeline/tasks.py` remains the public Celery task facade and compatibility patch surface for task names, session/retry ownership, startup signal wiring, and existing tests.
  - Summary generation, agenda segmentation, lineage wrappers, and summary-backfill compatibility wrappers remain in `pipeline/tasks.py` for later, lower-risk waves.
- Why:
  - Celery task names and bound-task retry behavior are public worker contracts, so decorated task objects should remain stable while helper logic is split out.
  - Existing tests and scripts patch `pipeline.tasks` names directly, so wrappers continue passing patch-sensitive callables into the extracted helpers.
  - Summary generation and agenda segmentation have denser failure-status and side-effect coupling, so deferring them keeps this cleanup wave behavior-preserving.
- Affected boundaries:
  - `pipeline/tasks.py` remains the Celery facade and monkeypatch surface.
  - `pipeline/task_agenda_titles.py` owns deterministic agenda-title parsing.
  - `pipeline/task_text_extraction.py` owns text re-extraction helper flow.
  - `pipeline/task_vote_extraction.py` owns direct vote-extraction helper flow.
  - `pipeline/task_side_effects.py` owns shared task side-effect error categories.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-26: Extract agenda-segmentation task support

- Status: Accepted
- Decision:
  - The next structural cleanup wave for `pipeline/tasks.py` extracts the agenda-segmentation task family into `pipeline/task_agenda_segmentation.py`.
  - The extracted module owns segmentation status recording, post-segmentation vote extraction, failure-status persistence, and the segment-agenda helper flow.
  - `pipeline/tasks.py` keeps the `segment_agenda_task` Celery wrapper, retry/session ownership, and compatibility wrappers for existing tests and callers.
  - Summary generation, summary side effects, lineage wrappers, startup signal wiring, and summary-hydration compatibility wrappers remain in `pipeline/tasks.py`.
- Why:
  - Agenda segmentation is one coherent task family and is a larger boundary than the earlier title/text/vote support extraction.
  - Keeping task decorators and runtime dependency wiring in `pipeline.tasks` preserves task names, retry behavior, and monkeypatch seams.
  - Summary generation remains more coupled to freshness, grounding, agenda-summary payloads, embedding dispatch, and AI fallback behavior, so it stays deferred.
- Affected boundaries:
  - `pipeline/tasks.py` remains the Celery facade and monkeypatch surface.
  - `pipeline/task_agenda_segmentation.py` owns agenda-segmentation task support.
  - `pipeline/agenda_resolver.py`, `pipeline/agenda_service.py`, and `pipeline/vote_extractor.py` keep their domain responsibilities.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-28: Finish task-family extraction with summary generation support

- Status: Accepted
- Decision:
  - The final task-family implementation cluster in `pipeline/tasks.py` moves into `pipeline/task_summary_generation.py`.
  - The extracted module owns summary generation, agenda-summary routing, low-signal and grounding gates, summary persistence assembly, and post-commit summary side effects.
  - `pipeline/tasks.py` remains the Celery facade for task decorators, task names, session/retry ownership, worker signal registration, and compatibility wrappers.
  - Summary hydration wrappers remain in `pipeline/tasks.py` because scripts and tests still import and patch those names through the facade.
- Why:
  - Summary generation was the last large inline task-family implementation after text extraction, vote extraction, and agenda segmentation were extracted.
  - Keeping task decorators and runtime dependency wiring in `pipeline.tasks` preserves Celery task identity and existing monkeypatch seams.
  - Moving the summary implementation makes `pipeline/tasks.py` an entrypoint and compatibility surface instead of a mixed implementation module.
- Affected boundaries:
  - `pipeline/tasks.py` remains the Celery facade and retry/session boundary.
  - `pipeline/task_summary_generation.py` owns summary-generation task support.
  - `pipeline/summary_backfill.py` continues to own summary hydration and backfill orchestration.
  - `pipeline/agenda_summary_maintenance.py` continues to own deterministic agenda-summary bundle and persistence helpers.
- Supersedes:
  - Earlier task-cleanup ADR language that described `pipeline/tasks.py` as already finished is now clarified by this final summary-generation extraction.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-29: Extract shared topic-generation support

- Status: Accepted
- Decision:
  - Topic-generation implementation moves into `pipeline/topic_generation.py`.
  - `pipeline/enrichment_tasks.py` remains the Celery facade for `enrichment.generate_topics`, retry/session ownership, and single-catalog patch seams.
  - `pipeline/topic_worker.py` remains the CLI/backfill facade for topic hydration selection, progress logging, and compatibility exports.
  - Single-catalog task generation and batch topic tagging now share sanitation, stop-word handling, small-corpus fallback, TF-IDF extraction, persistence semantics, and post-commit reindex behavior.
- Why:
  - `pipeline/enrichment_tasks.py` had become a mixed task wrapper plus implementation module.
  - `pipeline/topic_worker.py` carried overlapping topic sanitation and TF-IDF behavior for batch runs.
  - Keeping both existing facades stable preserves Celery task identity, API enqueue behavior, CLI invocation, and existing test monkeypatch seams while removing duplicated implementation logic.
- Affected boundaries:
  - `pipeline/topic_generation.py` remains the topic-generation compatibility boundary.
  - `pipeline/enrichment_tasks.py` owns the Celery task boundary and runtime service wiring.
  - `pipeline/topic_worker.py` owns CLI/backfill entrypoints.
  - `api/task_routes.py` and `pipeline/run_batch_enrichment.py` keep existing caller-facing contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-29: Split inference provider implementation behind the existing facade

- Status: Accepted
- Decision:
  - `pipeline/llm_provider.py` becomes the public compatibility facade for provider imports, test monkeypatch seams, config overrides, and metric recorder patch paths.
  - `pipeline/inference_provider_contract.py` owns the provider protocol, operation labels, Ollama response-field constants, and typed provider errors.
  - `pipeline/http_inference_provider.py` owns HTTP/Ollama transport, timeout selection, retry-budget policy, response validation, and fail-fast provider error mapping.
  - `pipeline/inprocess_inference_provider.py` owns the in-process llama adapter and model-call reset behavior.
  - `pipeline/provider_telemetry.py` owns token metric parsing and provider telemetry recording helpers.
- Why:
  - Provider transport code had become a mixed contract, HTTP client, in-process runtime, telemetry, and compatibility module.
  - Keeping `pipeline.llm_provider` as the facade preserves existing imports and monkeypatch paths used by tests, maintenance scripts, and `pipeline.llm`.
  - Splitting implementation behind the facade reduces coupling without changing runtime defaults, timeout budgets, retry budgets, telemetry names, or local-first/fail-fast policy.
- Affected boundaries:
  - `pipeline/llm_provider.py` remains the public provider facade.
  - `pipeline/http_inference_provider.py` owns remote/local HTTP inference transport behavior.
  - `pipeline/inprocess_inference_provider.py` owns in-process llama provider behavior.
  - `pipeline/provider_telemetry.py` owns provider metric parsing and recording support.
  - `pipeline/llm.py` continues to own orchestration and interpretation of typed provider failures.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-05-03: Split batch pipeline orchestration behind patch-safe facade

- Status: Accepted
- Decision:
  - `pipeline/run_pipeline.py` remains the CLI entrypoint, public compatibility facade, and test monkeypatch surface.
  - `pipeline/run_pipeline_steps.py` owns subprocess/callable step profiling and failure mapping.
  - `pipeline/run_pipeline_onboarding.py` owns onboarding run-window scope helpers.
  - `pipeline/run_pipeline_selectors.py` owns extraction and entity-backfill catalog selection.
  - `pipeline/run_pipeline_extraction.py` owns extraction chunk DB retry, per-catalog commit, and extraction-state repair.
  - `pipeline/run_pipeline_parallel.py` owns chunking, worker-count selection, and process-pool scheduling.
- Why:
  - The batch pipeline module had become a mixed CLI, selector, worker, metrics, onboarding, and process-pool implementation file.
  - Existing tests, scripts, and batch enrichment code import or patch names through `pipeline.run_pipeline`, so the facade must continue to resolve runtime dependencies from that module.
  - Splitting implementation behind the facade reduces review risk without changing CLI commands, env vars, batch policy, extraction behavior, or telemetry names.
- Affected boundaries:
  - `pipeline/run_pipeline.py` owns compatibility wrappers and high-level stage order.
  - `pipeline/run_batch_enrichment.py`, `pipeline/backfill_entities.py`, `pipeline/profile_manifest.py`, and `scripts/profile_pipeline.py` keep their existing imports.
  - Guardrails track the new batch pipeline module family under the 300-line cleanup target.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/PIPELINE.md](PIPELINE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)
