import os
import time
import google.generativeai as genai
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

# Configure the Gemini API using the environment variable
# SECURITY: Never hardcode API keys. Rely on Docker/Env injection.
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def summarize_documents():
    """
    Finds documents that have extracted text but no summary,
    and uses Google Gemini to generate a concise summary.
    """
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set. Skipping summarization.")
        return

    # Configure the Gemini client
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Use Gemini 1.5 Flash for speed and efficiency
    # It has a massive context window (1M tokens) perfect for long minutes
    model = genai.GenerativeModel('gemini-1.5-flash')

    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find documents that have text content but no summary yet
    to_process = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != "",
        Catalog.summary == None
    ).all()

    print(f"Found {len(to_process)} documents to summarize.")

    for record in to_process:
        print(f"Summarizing: {record.filename}...")
        
        try:
            # We construct a prompt that asks for specific, structured output
            prompt = (
                "You are a helpful assistant for civic transparency. "
                "Read the following town council meeting minutes and provide a summary. "
                "Format your response as 3 clear, concise bullet points highlighting the most important decisions or discussions. "
                "Do not include preamble or fluff.

"
                f"TEXT: {record.content[:30000]}..." # Send first 30k chars to be safe, though Flash can handle much more
            )

            # Generate content
            response = model.generate_content(prompt)
            
            if response and response.text:
                record.summary = response.text.strip()
                session.commit()
                print("Summary generated and saved.")
            else:
                print("Gemini returned empty response.")

            # Performance/Etiquette: Sleep briefly to respect API rate limits (Free tier is ~15 RPM)
            time.sleep(4)

        except Exception as e:
            print(f"Error summarizing {record.filename}: {e}")
            session.rollback()

    session.close()
    print("Summarization process complete.")

if __name__ == "__main__":
    summarize_documents()
