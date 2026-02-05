import os
import subprocess
import sys

def run_step(name, command, cwd=None):
    """
    Executes a single step in the pipeline.
    
    Args:
        name: A friendly name for the step (e.g., "Downloader").
        command: The shell command to run as a list (e.g., ["python", "script.py"]).
        cwd: Optional directory to run the command in.
    
    Returns:
        True if the command succeeded, False if it failed.
    """
    print(f"\n>>> Starting Pipeline Step: {name}")
    print(f"Running: {' '.join(command)}")
    
    try:
        # Run the command and wait for it to finish.
        # check=True will raise an error if the command fails (non-zero exit code).
        result = subprocess.run(
            command, 
            cwd=cwd, 
            check=True,
            text=True,
            capture_output=False # Stream output directly to the console so we can see progress.
        )
        print(f"<<< Finished Step: {name} (Success)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! Error in Step: {name} (Exit Code: {e.returncode})")
        return False

def main():
    """
    Runs the entire data processing pipeline from start to finish.
    
    This script coordinates:
    1. Seeding the database with city data.
    2. Promoting crawled data to production.
    3. Downloading documents.
    4. Extracting text, tables, and entities.
    5. Generating AI summaries.
    6. Indexing everything for search.
    """
    
    # 0. SETUP & PROMOTION
    # First, make sure our database knows about all the cities we support.
    run_step("Seed Places", ["python", "seed_places.py"])
    
    # Move any new meetings found by the crawler into the main database tables.
    run_step("Promote Staged Events", ["python", "promote_stage.py"])

    # 1. DOWNLOAD
    # Download the PDF files for any new meetings.
    if not run_step("Downloader", ["python", "downloader.py"]):
        # Stop if downloading fails, as subsequent steps depend on these files.
        sys.exit(1)

    # 2. EXTRACT TEXT
    # Use Apache Tika to turn the PDF documents into plain text.
    if not run_step("Extractor", ["python", "extractor.py"]):
        sys.exit(1)

    # 3. EXTRACT TABLES
    # Identify and extract data tables (like budgets) from the PDFs.
    if not run_step("Table Extraction", ["python", "table_worker.py"]):
        sys.exit(1)

    # 4. TOPIC MODELING
    # Analyze the text to find common themes (e.g., "Housing", "Traffic").
    if not run_step("Topic Modeling", ["python", "topic_worker.py"]):
        sys.exit(1)

    # 5. NLP ENTITIES
    # Find names of people, organizations, and locations in the text.
    if not run_step("NLP Entity Extraction", ["python", "nlp_worker.py"]):
        sys.exit(1)

    # 6. AI SUMMARIZATION
    # Use Google Gemini to generate a short 3-bullet summary of the meeting.
    if not run_step("AI Summarization", ["python", "summarizer.py"]):
        sys.exit(1)

    # 7. INDEX TO MEILISEARCH
    # Finally, upload the processed data to the search engine so it can be searched.
    if not run_step("Search Indexing", ["python", "indexer.py"]):
        sys.exit(1)

    print("\n✅ Full Pipeline Execution Complete.")

if __name__ == "__main__":
    main()