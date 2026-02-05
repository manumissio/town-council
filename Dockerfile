# Use a modern, slim Python image
FROM python:3.12-slim

# Install system dependencies for Scrapy, SQLAlchemy, and Camelot (Ghostscript)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ghostscript \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirement files first to leverage Docker cache
COPY council_crawler/requirements.txt ./council_crawler_requirements.txt
COPY pipeline/requirements.txt ./pipeline_requirements.txt
COPY api/requirements.txt ./api_requirements.txt

# Install all dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r council_crawler_requirements.txt && \
    pip install --no-cache-dir -r pipeline_requirements.txt && \
    pip install --no-cache-dir -r api_requirements.txt

# Download the SpaCy language model for NLP tasks
# We use a direct URL to ensure a reliable build and avoid version resolution errors
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.0/en_core_web_sm-3.7.0.tar.gz

# Copy the rest of the application
COPY . .

# Create the data directory for downloaded PDFs
RUN mkdir -p data

# Default command (can be overridden in docker-compose)
CMD ["python"]
