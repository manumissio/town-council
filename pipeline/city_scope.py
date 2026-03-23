from __future__ import annotations


def source_aliases_for_city(city: str) -> set[str]:
    aliases = {city}
    legacy_aliases = {
        "san_mateo": {"san mateo"},
        "san_leandro": {"san leandro"},
        "mtn_view": {"mountain view"},
    }
    aliases.update(legacy_aliases.get(city, set()))
    return aliases


def ordered_hydration_cities() -> list[str]:
    # Why this order:
    # smaller cities validate the staged hydrator cheaply, while san_mateo's
    # dominant backlog is isolated as a dedicated long-tail batch.
    return ["hayward", "sunnyvale", "berkeley", "cupertino", "san_mateo"]
