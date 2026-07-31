import json
import orjson
import re

# --------------------------------------------------------------------------
# NOVICE DEVELOPER NOTE:
# This file contains "Benchmarking" tests. Unlike normal tests that check 
# if the code is CORRECT, these tests check if the code is FAST.
# We use the 'benchmark' fixture to run the same code many times and 
# calculate the average speed.
# --------------------------------------------------------------------------

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
