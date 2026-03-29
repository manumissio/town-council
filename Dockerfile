# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS python-build-base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY council_crawler/requirements.txt ./council_crawler_requirements.txt
COPY pipeline/requirements.txt ./pipeline_requirements.txt
COPY api/requirements.txt ./api_requirements.txt
COPY semantic_service/requirements.txt ./semantic_service_requirements.txt
COPY docker/semantic-cpu-constraints.txt ./semantic_cpu_constraints.txt

FROM python-build-base AS venv-crawler
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install \
    -r council_crawler_requirements.txt

FROM python-build-base AS venv-api
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install \
    -r api_requirements.txt

FROM python-build-base AS venv-semantic
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install \
    -c semantic_cpu_constraints.txt \
    -r semantic_service_requirements.txt

FROM python-build-base AS venv-worker
RUN apt-get update && apt-get install -y --no-install-recommends cmake \
    && rm -rf /var/lib/apt/lists/*

# Compile llama.cpp with conservative CPU flags so the worker image stays portable.
ENV CMAKE_ARGS="-DGGML_NEON=ON -DGGML_NATIVE=OFF"
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install \
    -c semantic_cpu_constraints.txt \
    -r pipeline_requirements.txt \
    ghostscript \
    rapidfuzz \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0.tar.gz

FROM python:3.12-slim-bookworm AS python-runtime-base

RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data
ENV PYTHONPATH=/app
ENV GIT_PYTHON_REFRESH=quiet
ENV HF_HOME=/models/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/models/sentence-transformers

WORKDIR /app

COPY --chown=appuser:appgroup . .
RUN mkdir -p /app/data /models && chown -R appuser:appgroup /app/data /models

USER appuser

CMD ["python", "-c", "import sys; print('No default service command is configured for this image. Supply a service-specific command via docker compose.', file=sys.stderr); sys.exit(1)"]

FROM python-runtime-base AS python-crawler
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=venv-crawler /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
USER appuser

FROM python-runtime-base AS python-api
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=venv-api /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
USER appuser

# SECURITY: Add a health check to ensure the API container is running correctly.
# Use Python stdlib instead of wget so the check works on slim images without extra packages.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

FROM python-runtime-base AS python-worker
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=venv-worker /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
USER appuser

FROM python-runtime-base AS python-semantic
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgomp1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=venv-semantic /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
USER appuser
