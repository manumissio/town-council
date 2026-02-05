# Use a modern, slim Python image
FROM python:3.12-slim

# Install system dependencies for Scrapy and SQLAlchemy
RUN apt-get update && apt-get install -y --no-install-recommends 
    build-essential 
    libpq-dev 
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirement files first to leverage Docker cache
COPY council_crawler/requirements.txt ./council_crawler_requirements.txt
COPY pipeline/requirements.txt ./pipeline_requirements.txt

# Install all dependencies
RUN pip install --no-cache-dir -r council_crawler_requirements.txt
RUN pip install --no-cache-dir -r pipeline_requirements.txt

# Copy the rest of the application
COPY . .

# Create the data directory for downloaded PDFs
RUN mkdir -p data

# Default command (can be overridden in docker-compose)
CMD ["python"]
