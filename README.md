# Town Council
Tools to scrape and centralize the text of meeting agendas & minutes from local city governments.

## Project Description
Engagement in local government is limited by physical access and electronic barriers, including difficult-to-navigate portals and non-searchable scanned PDF documents. This project provides a **publicly available database that automatically scrapes, extracts text (OCR), and indexes city council agendas and minutes** for transparency and cross-city trend analysis.

## Project Status (Modernized 2026)
This project has been modernized from its 2017 pilot into a production-ready platform.

**Key Updates:**
- **Modern Stack:** Python 3.12, Next.js 16, FastAPI, and PostgreSQL 15.
- **AI-Powered:** Automatic 3-bullet summaries using **Gemini 2.0 Flash** with hallucination mitigation.
- **Search:** Instant, typo-tolerant search powered by **Meilisearch**.
- **Security:** Hardened Docker containers (non-root), Path Traversal protection, and CORS-secured API.
- **Automated Pipeline:** Single-command orchestration for the entire data flow.

## Getting Started

### 1. Build and Start
Ensure you have Docker installed, then build the optimized multi-stage images:
```bash
docker-compose build
docker-compose up -d
```

### 2. Scrape a City
Gather meeting metadata and PDF links (e.g., Berkeley, CA):
```bash
docker-compose run crawler scrapy crawl berkeley
```

### 3. Process Data
Run the processing pipeline (Downloads, OCR, AI Summaries, Indexing). 
*Tip: Set your [Gemini API Key](https://aistudio.google.com/) first to enable summaries.*
```bash
export GEMINI_API_KEY=your_key_here
docker-compose run pipeline python run_pipeline.py
```

## Access Links
| Service | URL | Credentials |
| :--- | :--- | :--- |
| **Search UI** | [http://localhost:3000](http://localhost:3000) | N/A |
| **Backend API** | [http://localhost:8000/docs](http://localhost:8000/docs) | N/A |
| **Meilisearch** | [http://localhost:7700](http://localhost:7700) | `masterKey` |
| **Prometheus** | [http://localhost:9090](http://localhost:9090) | N/A |
| **Grafana** | [http://localhost:3001](http://localhost:3001) | `admin` / `admin` |

## Troubleshooting

### AI Summaries are missing?
The Gemini Free Tier allows ~15 requests per minute. If you scrape hundreds of meetings at once, you will hit a `429 Rate Limit` error. 
**Solution:** Wait a few minutes and re-run the summarizer:
```bash
docker-compose run -e GEMINI_API_KEY=your_key pipeline python summarizer.py
```

### Scraper returns 0 results?
Some city portals (like Legistar) use anti-bot protection. We have implemented modern User-Agents and rate-limiting, but if results are empty, check the `council_crawler/spiders` logs for 403 Forbidden errors.

## Architecture & Security
For a detailed deep-dive into the system flow and security model, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Testing
Run the comprehensive suite of 14+ unit tests:
```bash
docker-compose run pipeline pytest tests/
```