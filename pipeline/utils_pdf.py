from __future__ import annotations

import logging
from typing import Final, TypedDict


logger = logging.getLogger(__name__)

COORDINATE_ROUNDING_PRECISION: Final = 2


class PdfCoordinate(TypedDict):
    page: int
    x: float
    y: float
    width: float
    height: float


def find_text_coordinates(pdf_path: str, search_text: str) -> list[PdfCoordinate]:
    """
    Finds the exact page and (x, y) coordinates of search_text in a PDF.

    Why this is needed:
    To create 'Deep Links' that scroll exactly to the vote/action block.
    """
    import pymupdf

    try:
        doc = pymupdf.open(pdf_path)
        locations: list[PdfCoordinate] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # search_for returns a list of Rect objects.
            found_areas = page.search_for(search_text)

            for rect in found_areas:
                locations.append(
                    {
                        "page": page_num + 1,
                        "x": round(rect.x0, COORDINATE_ROUNDING_PRECISION),
                        "y": round(rect.y0, COORDINATE_ROUNDING_PRECISION),
                        "width": round(rect.width, COORDINATE_ROUNDING_PRECISION),
                        "height": round(rect.height, COORDINATE_ROUNDING_PRECISION),
                    }
                )

        doc.close()
        return locations
    except (OSError, ValueError, RuntimeError) as exc:
        # PDF coordinate finding errors: What can fail when searching PDFs?
        # - OSError: PDF file not found, corrupted, or locked
        # - ValueError: Invalid PDF structure or malformed page
        # - RuntimeError: PyMuPDF library error (unsupported PDF version)
        # Why return empty list? Caller can handle gracefully (no coordinates = no verification)
        logger.error("Error finding coordinates in %s: %s", pdf_path, exc)
        return []
