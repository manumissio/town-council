import pytest
import json
import orjson
import re
from pipeline.utils import find_best_person_match

# --------------------------------------------------------------------------
# NOVICE DEVELOPER NOTE:
# This file contains "Benchmarking" tests. Unlike normal tests that check 
# if the code is CORRECT, these tests check if the code is FAST.
# We use the 'benchmark' fixture to run the same code many times and 
# calculate the average speed.
# --------------------------------------------------------------------------

class MockPerson:
    def __init__(self, name):
        self.name = name

def test_benchmark_fuzzy_matching(benchmark):
    """
    Measures how quickly we can compare names to find duplicates.
    Why: If this is slow, the nightly pipeline will hang.
    """
    # Create a pool of 200 "Officials"
    base_names = ["Jesse Arreguin", "Rashi Kesarwani", "Terry Taplin", "Sophie Hahn", "Ben Bartlett"]
    existing_people = [MockPerson(name + str(i)) for i, name in enumerate(base_names * 40)]
    
    # We ask the benchmark tool to measure this specific function
    result = benchmark(find_best_person_match, "Jesse Arreguin", existing_people)
    assert result is not None

def test_benchmark_regex_extraction(benchmark):
    """
    Measures the speed of our fallback agenda parser.
    Why: Large documents (50k+ chars) can be slow to parse with complex Regex.
    """
    # Create a dummy large document (approx 50,000 characters)
    large_text = """TITLE: Item 1
DESC: This is a description of an item.

""" * 500
    
    def run_extraction():
        # We simulate the regex part of the extraction logic
        pattern = r"TITLE:\s*(.*?)\s*DESC:\s*(.*?)(?=TITLE:|$)"
        return re.findall(pattern, large_text, re.IGNORECASE | re.DOTALL)

    result = benchmark(run_extraction)
    assert len(result) == 500

def test_benchmark_standard_json_serialization(benchmark):
    """Measures speed of standard Python json library."""
    data = {"hits": [{"id": i, "content": "text " * 100} for i in range(100)]}
    benchmark(json.dumps, data)

def test_benchmark_orjson_serialization(benchmark):
    """Measures speed of Rust-powered orjson library."""
    data = {"hits": [{"id": i, "content": "text " * 100} for i in range(100)]}
    benchmark(orjson.dumps, data)