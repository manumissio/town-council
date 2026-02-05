# Stage 1: Builder
# This stage installs build-time dependencies and compiles Python packages.
FROM python:3.12-slim-bookworm AS builder

# Prevent Python from writing .pyc files and ensure logs are flushed immediately.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies (compilers and headers for psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirement files first to leverage Docker's layer caching.
# If these files don't change, Docker will skip this expensive step.
COPY council_crawler/requirements.txt ./council_crawler_requirements.txt
COPY pipeline/requirements.txt ./pipeline_requirements.txt
COPY api/requirements.txt ./api_requirements.txt

# Install dependencies into a wheels directory to keep the final image clean.
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels \
    -r council_crawler_requirements.txt \
    -r pipeline_requirements.txt \
    -r api_requirements.txt \
    ghostscript

# Download the SpaCy model as a wheel as well.
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0.tar.gz


# Stage 2: Runtime
# This is the final, minimal image that will be used in production.
FROM python:3.12-slim-bookworm

# Security: Create a non-root user to run the application.
# Running as root is a security risk if the container is compromised.
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Set environment variables for runtime.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data

WORKDIR /app

# Install runtime system dependencies.
# We keep 'ghostscript' and 'libpq5' (runtime for postgres) here.
# 'libgl1' and 'libglib2.0-0' are required for OpenCV/SpaCy/Camelot dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy wheels from the builder stage and install them.
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy the application source code.
COPY --chown=appuser:appgroup . .

# Create the data directory and ensure the non-root user can write to it.
RUN mkdir -p /app/data && chown -R appuser:appgroup /app/data

# Switch to the non-root user.
USER appuser

# Default command (usually overridden in docker-compose.yml).
CMD ["python"]