import time
import os
from prometheus_client import start_http_server, Gauge
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from models import db_connect

# Define Prometheus Metrics
DOCUMENTS_TOTAL = Gauge('tc_documents_total', 'Total number of documents in the catalog')
EVENTS_TOTAL = Gauge('tc_events_total', 'Total number of meeting events scraped')
DOCUMENTS_PROCESSED = Gauge('tc_documents_processed_text', 'Number of documents with extracted text')
DOCUMENTS_SUMMARIZED = Gauge('tc_documents_summarized', 'Number of documents with AI summaries')
LAST_CRAWL_TIMESTAMP = Gauge('tc_last_crawl_timestamp', 'Unix timestamp of the most recent event recorded')

def update_metrics():
    """
    Queries the database and updates the Prometheus metrics.
    Runs in a loop to provide real-time monitoring data.
    """
    try:
        engine = db_connect()
        # Use a raw connection for simple stats queries to avoid ORM overhead
        with engine.connect() as conn:
            
            # Count total documents
            result = conn.execute(text("SELECT COUNT(*) FROM catalog")).scalar()
            DOCUMENTS_TOTAL.set(result)

            # Count extracted documents
            result = conn.execute(text("SELECT COUNT(*) FROM catalog WHERE content IS NOT NULL AND content != ''")).scalar()
            DOCUMENTS_PROCESSED.set(result)

            # Count summarized documents
            result = conn.execute(text("SELECT COUNT(*) FROM catalog WHERE summary IS NOT NULL")).scalar()
            DOCUMENTS_SUMMARIZED.set(result)

            # Count total events
            result = conn.execute(text("SELECT COUNT(*) FROM event")).scalar()
            EVENTS_TOTAL.set(result)

            # Check freshness (When was the last meeting added?)
            result = conn.execute(text("SELECT MAX(scraped_datetime) FROM event")).scalar()
            if result:
                timestamp = result.timestamp()
                LAST_CRAWL_TIMESTAMP.set(timestamp)
                
                # Simple Alerting Logic (Log to console, could be email/slack)
                # If data is older than 7 days, warn the admin.
                if time.time() - timestamp > (7 * 24 * 60 * 60):
                    print("ALERT: No new scraping data detected in the last 7 days!")

        print(f"Metrics updated. Total Docs: {DOCUMENTS_TOTAL._value.get()}")

    except Exception as e:
        print(f"Error updating metrics: {e}")

if __name__ == '__main__':
    # Start the Prometheus metrics server on port 8000
    start_http_server(8000)
    print("Monitor service started on port 8000")

    # Update metrics every 60 seconds
    while True:
        update_metrics()
        time.sleep(60)
