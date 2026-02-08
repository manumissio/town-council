import pytest
import os
from pipeline.utils import find_text_coordinates

def test_find_text_coordinates_real_pdf():
    """
    Test spatial search using a real PDF if available.
    """
    pymupdf = pytest.importorskip("pymupdf")

    # Look for any PDF in the data directory to use as a test case
    pdf_path = None
    for root, dirs, files in os.walk("data"):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                break
        if pdf_path: break
        
    if not pdf_path:
        pytest.skip("No real PDF found in data/ directory for spatial test")
        
    # Get some text from the first page to search for
    doc = pymupdf.open(pdf_path)
    page_text = doc[0].get_text()
    doc.close()
    
    if not page_text.strip():
        pytest.skip("Found PDF but it has no text (image-based)")
        
    # Use a stable search term: first reasonably long readable line.
    lines = [line.strip() for line in page_text.split('\n') if line.strip()]
    if not lines:
        pytest.skip("No readable lines in PDF")

    candidate_line = next((line for line in lines if len(line) >= 20), lines[0])
    search_term = candidate_line[:20]
    
    results = find_text_coordinates(pdf_path, search_term)
    
    assert len(results) > 0
    assert "page" in results[0]
    assert "x" in results[0]
    assert "y" in results[0]
