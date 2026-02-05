# Town Council
Tools to scrape and centralize the text of meeting agendas & minutes from local city governments.

## Project Description
Engagement in local government is limited by physical access and electronic barriers, including difficult-to-navigate portals and non-searchable scanned PDF documents. This project provides a **publicly available database that automatically scrapes, extracts text (OCR), and indexes city council agendas and minutes** for transparency and cross-city trend analysis.

## Project Status (Modernized 2026)
This project was originally a Data4Democracy pilot (2017). It has since been **extensively modernized, secured, and scaled**.

**Key Updates:**
- **Production Stack:** Upgraded to Python 3.12+, Scrapy 2.11+, and SQLAlchemy 2.0+.
- **Containerization:** Fully Dockerized with **multi-stage builds** and **non-root user** security best practices.
- **PostgreSQL Migration:** Migrated from SQLite to PostgreSQL for high-performance concurrent data access.
- **Full-Text Search:** Integrated **Meilisearch** for instant, typo-tolerant search across extracted text.
- **AI Summarization:** Uses **Google Gemini 2.0 Flash** via the modern GenAI SDK to automatically generate 3-bullet point summaries. Implements **hallucination mitigation** via deterministic output (temp 0.0) and strict grounding instructions.
- **NLP Entity Extraction:** Integrated **SpaCy** to automatically identify Organizations and Locations within meeting minutes.
- **Robust Pipeline:** Consolidated the entire data flow (Download -> OCR -> NLP -> Summarize -> Index) into a fault-tolerant pipeline that handles PDF parsing errors gracefully.
- **Security Hardening:** 
    - Protected against **Path Traversal** vulnerabilities via absolute path validation.
    - Patched **Requests .netrc credential leakage** (CVE-2024-3651).
    - Implemented **CORS** protection on the API.
    - Implemented **Bot Etiquette** (Rate limiting, descriptive User-Agents).

## Getting Started

The easiest way to run the project is using **Docker Compose**.

### 1. Build and Start Infrastructure
```bash
docker-compose build
docker-compose up -d
```

### 2. Run a Scraper
Scrape meeting metadata for a city (e.g., Berkeley, CA):
```bash
docker-compose run crawler scrapy crawl berkeley
```

### 3. Run the Automated Pipeline
This single command handles downloading, OCR, AI analysis, and indexing.
*Note: To enable AI summaries, export your Gemini API key first.*
```bash
export GEMINI_API_KEY=your_key_here
docker-compose run pipeline python run_pipeline.py
```

### 4. Access the API and UI
- **Search UI (Web):** `http://localhost:3000`
- **Search API (Backend):** `http://localhost:8000/search?q=zoning`
- **Meilisearch Dashboard:** `http://localhost:7700` (Key: masterKey)

## Architecture
A detailed overview of the system design, including data flow diagrams and component descriptions, can be found in [ARCHITECTURE.md](ARCHITECTURE.md).

## Testing
The project includes a comprehensive suite of unit and integration tests to ensure data integrity and AI reliability.

Run the tests using **Docker Compose**:
```bash
docker-compose run pipeline pytest tests/
```

Test coverage includes:
- **Security:** Path traversal protection and credential safety.
- **Data:** Date parsing, URL hashing, and database promotion logic.
- **AI/NLP:** Mocked verification of summarization and entity extraction.

## Development & Contributing

### Security First
When adding new scrapers or modules, always prioritize security:
- Use `is_safe_path()` when handling file paths.
- Ensure all `Requests` sessions use `trust_env=False`.
- Mimic existing bot etiquette settings in `settings.py`.

### Project History
Originally led by @chooliu and @bstarling in 2017. Modernized in 2026 to ensure the project remains a viable tool for civic transparency.
