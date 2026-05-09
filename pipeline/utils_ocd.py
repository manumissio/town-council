from __future__ import annotations

import re
import uuid
from typing import Final


OCD_ID_PATTERN: Final = re.compile(
    r"^ocd-[a-z]+/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def validate_ocd_id(ocd_id: str) -> bool:
    """
    Strict Validation: Checks if an ID follows the OCD standard.
    Format: ocd-[type]/[uuid]
    """
    return bool(OCD_ID_PATTERN.match(ocd_id))


def generate_ocd_id(entity_type: str) -> str:
    """
    Generates a standardized Open Civic Data (OCD) identifier.

    Why this is needed:
    Following the OCD standard ensures our data is interoperable with
    other civic projects. Standard format: ocd-[type]/[uuid]

    Args:
        entity_type (str): The type of entity (e.g., 'event', 'person', 'organization', 'agendaitem')

    Returns:
        str: A unique OCD-compliant identifier.
    """
    unique_id = str(uuid.uuid4())
    # OCD-IDs are lowercase and use hyphens.
    return f"ocd-{entity_type.lower()}/{unique_id}"
