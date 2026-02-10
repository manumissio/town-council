# Council Crawler (Scrapy)

This folder contains the Scrapy project that discovers meeting metadata and document URLs for supported municipalities.

The crawler writes to staging tables. The downstream pipeline promotes and processes those staged rows (download, OCR, NLP, indexing).

## Docker Quickstart (Recommended)
From the repo root:

```bash
# Crawl Berkeley, CA
docker compose run --rm crawler scrapy crawl berkeley

# Crawl Cupertino, CA (Legistar API)
docker compose run --rm crawler scrapy crawl cupertino
```

Notes:
* The crawler uses `DATABASE_URL` (set in `docker-compose.yml`) to write to Postgres.
* The repo root `README.md` documents the end-to-end runbook (crawler + pipeline).

## Where Crawler Data Goes
The crawler persists via Scrapy item pipelines (not a standalone `pipeline.py` file):
* Pipelines: `council_crawler/council_crawler/pipelines.py`
* Staging tables (SQLAlchemy models): `council_crawler/council_crawler/models.py`

Staging tables:
* `event_stage`: one row per discovered meeting
* `url_stage`: one row per discovered document link (agenda, minutes, etc.)

## DB Configuration (Postgres vs SQLite)
The crawler database target is configured in `council_crawler/council_crawler/settings.py`:
* Docker: `DATABASE_URL` is set, so the crawler uses Postgres.
* Non-Docker: if `DATABASE_URL` is not set, it falls back to a local SQLite file (`test_db.sqlite` in the repo root).

## Spider Structure
Helpful Scrapy references:
* Scrapy architecture: https://docs.scrapy.org/en/latest/topics/architecture.html
* Items: https://docs.scrapy.org/en/latest/topics/items.html
* Item pipelines: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

Each municipality has a spider under `council_crawler/council_crawler/spiders/`.

Goal: each spider should yield a consistent `Event` item (see `council_crawler/council_crawler/items.py`) with:
* required meeting metadata
* a list of discovered documents (URLs + category)

## Item Contract (What the Pipelines Enforce)
This project follows Open Civic Data conventions where practical, but uses a smaller schema focused on meeting discovery.

Required fields (see `ValidateRequiredFields` in `council_crawler/council_crawler/pipelines.py`):
* `_type`: always `"event"`
* `name`: meeting title
* `ocd_division_id`: place identifier (from the canonical city list in `city_metadata/list_of_cities.csv`)
* `scraped_datetime`: when the crawler ran
* `record_date`: meeting date (must be a Python `datetime.date` object or the item is dropped)
* `source_url`: landing page where the item was discovered
* `source`: spider name

Documents:
* `documents` is a list of dicts.
* Each dict must include:
  * `url`: absolute URL to the resource
  * `category`: for example `"agenda"` or `"minutes"`
* Most spiders also include `url_hash` so the staging layer can dedupe links consistently.

Example output (illustrative, not exact field types):

```json
{
  "_type": "event",
  "ocd_division_id": "ocd-division/country:us/state:ca/place:cupertino",
  "name": "Cupertino, CA City Council Regular Meeting",
  "record_date": "2026-02-04",
  "source": "cupertino",
  "source_url": "https://cupertino.legistar.com/Calendar.aspx",
  "meeting_type": "Regular Meeting",
  "documents": [
    {
      "url": "https://legistar.granicus.com/cupertino/meetings/2026/2/....pdf",
      "url_hash": "02f4a611b6e0f1b6087196354955e11b",
      "category": "agenda"
    }
  ]
}
```

## Developing a Spider Without Docker (Optional)
If you have Scrapy installed locally, you can run a spider from `council_crawler/`:

```bash
scrapy crawl cupertino -o test.json
```

If you want this run to write to Postgres, export `DATABASE_URL` first. Otherwise, it will write to SQLite via the `STORAGE_ENGINE` default.
