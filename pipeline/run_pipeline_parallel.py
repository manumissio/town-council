import logging
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Protocol, TypeAlias

from pipeline.profiling import profile_span


GLOBAL_PROCESSING_MODE = "global"
ONBOARDING_PROCESSING_MODE = "onboarding_scoped"
EXTRACT_PARALLEL_PHASE = "extract_parallel"
PIPELINE_COMPONENT = "pipeline"

class DbSessionContext(Protocol):
    def __enter__(self) -> object: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool | None: ...


class ExecutorContext(Protocol):
    def __enter__(self) -> "ExecutorContext": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool | None: ...

    def submit(
        self,
        func: Callable[[Sequence[int], bool | None], int],
        chunk: Sequence[int],
        ocr_fallback_enabled: bool | None,
    ) -> Future[int]: ...


DbSessionFactory: TypeAlias = Callable[[], DbSessionContext]
CatalogSelector: TypeAlias = Callable[[object], list[int]]
ChunkProcessor: TypeAlias = Callable[[Sequence[int], bool | None], int]
ExecutorFactory: TypeAlias = Callable[..., ExecutorContext]
FutureIterator: TypeAlias = Callable[[Iterable[Future[int]]], Iterable[Future[int]]]
CpuCountFunc: TypeAlias = Callable[[], int]


@dataclass(frozen=True, slots=True)
class ParallelProcessingSettings:
    mode: str
    chunk_size: int
    workers_override: int | None
    ocr_fallback_enabled: bool


@dataclass(frozen=True, slots=True)
class ParallelProcessingRuntime:
    onboarding_city: str
    onboarding_started_at_utc: str
    max_workers: int
    cpu_fraction: float


@dataclass(frozen=True, slots=True)
class ParallelProcessingDependencies:
    db_session_factory: DbSessionFactory
    catalog_selector: CatalogSelector
    chunk_processor: ChunkProcessor
    executor_factory: ExecutorFactory
    future_iterator: FutureIterator
    cpu_count: CpuCountFunc
    logger: logging.Logger


def resolve_parallel_processing_settings(
    *,
    document_chunk_size: int,
    tika_ocr_fallback_enabled: bool,
    onboarding_city: str,
    onboarding_document_chunk_size: int,
    onboarding_max_workers: int,
) -> ParallelProcessingSettings:
    chunk_size = document_chunk_size
    workers_override = None
    mode = GLOBAL_PROCESSING_MODE

    if onboarding_city:
        mode = ONBOARDING_PROCESSING_MODE
        if onboarding_document_chunk_size > 0:
            chunk_size = onboarding_document_chunk_size
        if onboarding_max_workers > 0:
            workers_override = onboarding_max_workers

    return ParallelProcessingSettings(
        mode=mode,
        chunk_size=chunk_size,
        workers_override=workers_override,
        ocr_fallback_enabled=tika_ocr_fallback_enabled,
    )


def _chunk_catalog_ids(catalog_ids: Sequence[int], chunk_size: int) -> list[list[int]]:
    return [list(catalog_ids[index : index + chunk_size]) for index in range(0, len(catalog_ids), chunk_size)]


def _worker_count(settings: ParallelProcessingSettings, runtime: ParallelProcessingRuntime, cpu_count: CpuCountFunc) -> int:
    cpu_limit = int(cpu_count() * runtime.cpu_fraction)
    workers = max(1, min(cpu_limit, runtime.max_workers))
    if settings.workers_override is not None:
        workers = max(1, min(settings.workers_override, runtime.max_workers))
    return workers


def _select_catalog_ids(dependencies: ParallelProcessingDependencies) -> list[int]:
    with dependencies.db_session_factory() as db:
        return dependencies.catalog_selector(db)


def _log_parallel_start(
    *,
    settings: ParallelProcessingSettings,
    runtime: ParallelProcessingRuntime,
    catalog_count: int,
    chunk_count: int,
    logger: logging.Logger,
) -> None:
    logger.info(
        "Starting parallel processing mode=%s city=%s documents=%s chunks=%s "
        "chunk_size=%s onboarding_started_at=%s ocr_fallback_enabled=%s",
        settings.mode,
        runtime.onboarding_city or "-",
        catalog_count,
        chunk_count,
        settings.chunk_size,
        runtime.onboarding_started_at_utc or "-",
        settings.ocr_fallback_enabled,
    )


def _run_process_pool(
    *,
    chunks: Sequence[Sequence[int]],
    settings: ParallelProcessingSettings,
    dependencies: ParallelProcessingDependencies,
    workers: int,
    catalog_count: int,
) -> None:
    with dependencies.executor_factory(max_workers=workers) as executor:
        futures = {
            executor.submit(
                dependencies.chunk_processor,
                chunk,
                settings.ocr_fallback_enabled,
            ): chunk
            for chunk in chunks
        }

        completed_docs = 0
        for future in dependencies.future_iterator(futures):
            count = future.result()
            if count:
                completed_docs += count
                dependencies.logger.info("Progress: %s/%s", completed_docs, catalog_count)


def run_parallel_processing(
    *,
    settings: ParallelProcessingSettings,
    runtime: ParallelProcessingRuntime,
    dependencies: ParallelProcessingDependencies,
) -> None:
    catalog_ids = _select_catalog_ids(dependencies)
    if not catalog_ids:
        dependencies.logger.info("No documents need processing.")
        return

    chunks = _chunk_catalog_ids(catalog_ids, settings.chunk_size)
    _log_parallel_start(
        settings=settings,
        runtime=runtime,
        catalog_count=len(catalog_ids),
        chunk_count=len(chunks),
        logger=dependencies.logger,
    )

    workers = _worker_count(settings, runtime, dependencies.cpu_count)
    dependencies.logger.info("Parallel processing worker_count=%s", workers)

    with profile_span(
        phase=EXTRACT_PARALLEL_PHASE,
        component=PIPELINE_COMPONENT,
        metadata={
            "catalog_count": len(catalog_ids),
            "chunk_count": len(chunks),
            "worker_count": workers,
        },
    ):
        _run_process_pool(
            chunks=chunks,
            settings=settings,
            dependencies=dependencies,
            workers=workers,
            catalog_count=len(catalog_ids),
        )
