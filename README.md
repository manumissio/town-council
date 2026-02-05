# Town Council
Tools to scrape and centralize the text of meeting agendas & minutes from local city governments.

## Project Description
Engagement in local government is limited by physical access and electronic barriers, including difficult-to-navigate portals and non-searchable scanned PDF documents. This project provides a **publicly available database that automatically scrapes, extracts text (OCR), and indexes city council agendas and minutes** for transparency and cross-city trend analysis.

## Project Status (Modernized 2026)
This project was originally a Data4Democracy pilot (2017). It has since been **extensively modernized, secured, and scaled**.

**Key Updates:**
- **Production Stack:** Upgraded to Python 3.12+, Scrapy 2.11+, and SQLAlchemy 2.0+.
- **PostgreSQL Migration:** Migrated from SQLite to PostgreSQL for high-performance concurrent data access.
- **Full-Text Search:** Integrated **Meilisearch** for instant, typo-tolerant search across extracted text.
- **Automated Extraction & OCR:** Integrated **Apache Tika** to automatically extract text and perform OCR on downloaded PDFs.
- **Security Hardening:** 
    - Protected against **Path Traversal** vulnerabilities.
    - Patched **Requests .netrc credential leakage** (CVE-2024-3651).
    - Implemented **Bot Etiquette** (Rate limiting, descriptive User-Agents, and robots.txt compliance).
- **Performance:** Parallelized document downloading and text extraction using multi-threading.

## Getting Started

The easiest way to run the project is using **Docker Compose**.

### 1. Build and Start Infrastructure
```bash
docker-compose build
docker-compose up -d postgres tika meilisearch
```

### 2. Run a Scraper
Scrape meeting metadata for a city (e.g., Belmont, CA):
```bash
docker-compose run crawler scrapy crawl belmont
```

### 3. Download Documents
Download the associated PDFs (parallelized):
```bash
docker-compose run pipeline python downloader.py
```

### 4. Extract Text and Index for Search
Process the PDFs through OCR/extraction and sync them to the search engine:
```bash
# Extract text (requires 'tika' service)
docker-compose run extractor python extractor.py

# Index into Meilisearch
docker-compose run pipeline python indexer.py
```

### 5. Access the API and UI
- **Search UI (Web):** `http://localhost:3000`
- **Search API (Backend):** `http://localhost:8000/search?q=zoning`
- **Interactive API Docs:** `http://localhost:8000/docs`

## Architecture
- **`crawler`**: Scrapy spiders that extract meeting schedules and document links.
- **`pipeline`**: Handles database records and secure, parallelized PDF downloading.
- **`extractor`**: Uses Apache Tika to turn raw documents into searchable text.
- **`indexer`**: Synchronizes the processed text into Meilisearch.
- **`api`**: Modern FastAPI backend serving data to users.
- **`frontend`**: Next.js 14 web interface with typo-tolerant search and highlights.

## Development & Contributing

### Security First
When adding new scrapers or modules, always prioritize security:
- Use `is_safe_path()` when handling file paths.
- Ensure all `Requests` sessions use `trust_env=False`.
- Mimic existing bot etiquette settings in `settings.py`.

### Project History
Originally led by @chooliu and @bstarling in 2017. Modernized in 2026 to ensure the project remains a viable tool for civic transparency.
