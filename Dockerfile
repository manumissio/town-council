# syntax=docker/dockerfile:1

# Stage 1: Builder
# This stage installs build-time dependencies and compiles Python packages.
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirement files
COPY council_crawler/requirements.txt ./council_crawler_requirements.txt
COPY pipeline/requirements.txt ./pipeline_requirements.txt
COPY api/requirements.txt ./api_requirements.txt

# OPTIMIZATION: Unified dependency resolution in a single pip wheel command.
# This prevents conflicting versions of sub-dependencies (like cloudpathlib).
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /app/wheels \
    -r council_crawler_requirements.txt \
    -r pipeline_requirements.txt \
    -r api_requirements.txt \
    ghostscript \
    rapidfuzz \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0.tar.gz


# Stage 2: Runtime
FROM python:3.12-slim-bookworm

# Security: Create a restricted non-root user.
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data
ENV PYTHONPATH=/app

WORKDIR /app

# Install runtime system libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy pre-compiled wheels from the builder.
COPY --from=builder /app/wheels /wheels

# Use --find-links to install from the local wheels directory.
# This allows pip to perform final resolution and ensures only one version per package is installed.
RUN pip install --no-cache-dir --find-links=/wheels /wheels/* && rm -rf /wheels

# Copy source code with correct permissions.
COPY --chown=appuser:appgroup . .

RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# --------------------------------------------------------------------------------
# PERFORMANCE & SECURITY: Model Baking
# --------------------------------------------------------------------------------
# 1. We store models in /models to prevent them from being hidden by the /app volume.
# 2. We download them now (Build Time) so the container starts instantly (Runtime).
ENV HF_HOME=/models
RUN mkdir -p /models && chown -R appuser:appgroup /models

USER appuser

# Download the specific AI brain used by our Similarity Engine.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

CMD ["python"]