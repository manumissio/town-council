# Town Council
Tools to scrape and centralize the text of meeting agendas & minutes from local city governments.

## Project Description
Engagement in local government is limited by physical access and electronic barriers, including difficult-to-navigate portals and scanned, non-searchable PDF documents. This project aims to provide a **publicly available database that automatically scrapes and aggregates the text from city council agendas and minutes**, promoting transparency and enabling trend analysis across municipalities.

## Project Status (Modernized 2026)
This project was originally a Data4Democracy pilot (2017). It has since been **modernized and secured** to run on modern infrastructure.

**Key Updates:**
- **Modern Stack:** Upgraded to Python 3.12+, Scrapy 2.11+, and SQLAlchemy 2.0+.
- **Containerized:** Full Docker and Docker Compose support for easy setup.
- **Performance:** Parallelized document downloading using multi-threading.
- **Security:** Protected against path traversal and implemented bot etiquette (rate limiting, descriptive User-Agents).
- **Portability:** Dynamic database path resolution for shared SQLite storage.

## Getting Started

The easiest way to run the project is using **Docker**.

### 1. Build the environment
```bash
docker-compose build
```

### 2. Run a Scraper
To scrape a specific city (e.g., Belmont, CA), use the `crawler` service:
```bash
docker-compose run crawler scrapy crawl belmont
```
*The metadata will be stored in the shared `test_db.sqlite` database.*

### 3. Download Documents
Once metadata is scraped, use the `pipeline` service to download the PDFs:
```bash
docker-compose run pipeline python downloader.py
```
*Documents are saved to the `./data` directory, organized by country/state/city.*

### 4. Extract and Search
After downloading, extract the text and index it for searching:
```bash
# Extract text (requires 'tika' service to be running: docker-compose up -d tika)
docker-compose run extractor python extractor.py

# Sync data to the search engine
docker-compose run pipeline python indexer.py
```

### 5. Access the API
The API is available at `http://localhost:8000`. 
- **Search:** `http://localhost:8000/search?q=zoning`
- **Documentation:** `http://localhost:8000/docs` (interactive Swagger UI)

## Architecture
A visualization of the original infrastructure is shown [here](./design_doc.png).

- **`council_crawler/`**: Scrapy project containing city-specific spiders and generic templates (e.g., Legistar).
- **`pipeline/`**: Downloader module that processes staged URLs, handles deduplication (via MD5 hashes), and stores files.
- **`city_metadata/`**: Curated metadata for pilot cities.

## Development & Contributing

### Manual Setup (No Docker)
If you prefer to run locally, ensure you have Python 3.12+ installed:
1. Install dependencies:
   ```bash
   pip install -r council_crawler/requirements.txt
   pip install -r pipeline/requirements.txt
   ```
2. Run commands from their respective directories.

### Project History
Originally led by @chooliu and @bstarling in 2017. For historical context, see the original [Project Status](./README.md#legacy-status).

## Related Work
- [Open Civic Data](http://opencivicdata.readthedocs.io/en/latest/)
- [Councilmatic](https://www.councilmatic.org/)
- [Open States Project](https://openstates.org/)