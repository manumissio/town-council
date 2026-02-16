# City Metadata

This folder contains the canonical city seed file used by the pipeline.

## How This Is Used
- `pipeline/seed_places.py` reads `city_metadata/list_of_cities.csv` and seeds `place` records.
- Crawler and pipeline flows depend on these place records for city normalization and filtering.
- For provenance/history context, see `README.md` -> `Project History`.

## CSV Schema
Current header in `city_metadata/list_of_cities.csv`:

`city,state,country,display_name,ocd_division_id,city_council_url,hosting_services`

Field descriptions:
- `city`: city or municipality name (slug-friendly, lowercase).
- `state`: two-letter state or territory code (for example `ca`).
- `country`: country code (currently `us` for seeded rows).
- `display_name`: canonical key used across the app (for example `ca_cupertino`).
- `ocd_division_id`: Open Civic Data division identifier.
- `city_council_url`: primary council meetings/agenda landing page.
- `hosting_services`: pipe-delimited platform/services hints (for example `granicus|legistar|city`).

## Updating Cities
When adding or changing city rows, follow:
- `docs/CONTRIBUTING_CITIES.md` for ingestion workflow and validation checks.
