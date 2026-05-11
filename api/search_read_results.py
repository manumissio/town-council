from __future__ import annotations

PEOPLE_METADATA_MAX_ITEMS = 10


def truncate_people_metadata(results: dict[str, object]) -> None:
    for hit in results["hits"]:
        if not isinstance(hit, dict):
            continue
        truncate_hit_people_metadata(hit)


def truncate_hit_people_metadata(hit: dict[str, object]) -> None:
    if "people_metadata" in hit and isinstance(hit["people_metadata"], list):
        hit["people_metadata"] = hit["people_metadata"][:PEOPLE_METADATA_MAX_ITEMS]
    formatted_hit = hit.get("_formatted")
    if isinstance(formatted_hit, dict) and isinstance(formatted_hit.get("people_metadata"), list):
        formatted_hit["people_metadata"] = formatted_hit["people_metadata"][:PEOPLE_METADATA_MAX_ITEMS]
