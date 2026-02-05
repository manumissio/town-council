import os
import time
import google.generativeai as genai
from sqlalchemy.orm import sessionmaker
from models import Catalog, db_connect, create_tables

# Get the API key securely from the environment variables.
# Never hardcode API keys in the source code!
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def summarize_documents():
    """
    Uses Google's Gemini AI to read meeting minutes and write short summaries.
    
    How it works:
    1. It finds documents in the database that have text but no summary yet.
    2. It sends the text to Gemini with a specific instruction to write 3 bullet points.
    3. It saves the AI-generated summary back to the database.
    """
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set. Skipping summarization.")
        return

    # Set up the connection to Google's AI service.
    genai.configure(api_key=GEMINI_API_KEY)
    
    # We use 'gemini-1.5-flash' because it's fast, cheap, and can handle very long documents.
    model = genai.GenerativeModel('gemini-1.5-flash')

    # Hallucination Mitigation:
    # We set temperature to 0.0 to make the AI more deterministic and "literal".
    # This prevents the AI from getting "creative" and making up facts.
    generation_config = genai.types.GenerationConfig(
        temperature=0.0,
        max_output_tokens=500,
    )

    engine = db_connect()
    create_tables(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find valid documents that haven't been summarized yet.
    to_process = session.query(Catalog).filter(
        Catalog.content != None,
        Catalog.content != "",
        Catalog.summary == None
    ).all()

    print(f"Found {len(to_process)} documents to summarize.")

    for record in to_process:
        print(f"Summarizing: {record.filename}...")
        
        try:
            # Grounding Instructions:
            # We explicitly tell the AI to ONLY use the provided text and to say
            # "No significant decisions found" if it can't find anything certain.
            prompt = (
                "You are a helpful assistant for civic transparency. "
                "Read the following town council meeting minutes and provide a summary. "
                "IMPORTANT: ONLY use information explicitly stated in the provided text. "
                "Do not use outside knowledge or make assumptions. "
                "If the text is unclear or missing key details, simply summarize what is present. "
                "Format your response as 3 clear, concise bullet points highlighting the most important decisions or discussions. "
                "Do not include preamble or fluff.

"
                f"TEXT: {record.content[:100000]}..." # Increased context window to 100k chars for better accuracy.
            )

            # Ask Gemini to generate the summary with our strict config.
            response = model.generate_content(prompt, generation_config=generation_config)
            
            if response and response.text:
                record.summary = response.text.strip()
                session.commit()
                print("Summary generated and saved.")
            else:
                print("Gemini returned empty response.")

            # Pause for 4 seconds between requests.
            # This is "Rate Limiting" - it prevents us from hitting the API too fast and getting blocked.
            time.sleep(4)

        except Exception as e:
            print(f"Error summarizing {record.filename}: {e}")
            session.rollback()

    session.close()
    print("Summarization process complete.")

if __name__ == "__main__":
    summarize_documents()