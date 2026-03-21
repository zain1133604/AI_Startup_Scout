import os
from google import genai
from textextractor import text_extractor
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
gemini_key = os.environ.get("GEMINI_KEY")



async def sumarizer(pitch_deck_text):
    client = genai.Client(api_key=os.environ.get("GEMINI_KEY"))
    print("\n👔 Summarizer is analyzing the briefing...")

    prompt =f"""
    You are a Senior Investment Analyst. Read this extracted pitch deck text and provide a structured report.
    
    TASKS:
    1. **Company Name**: Identify the startup's name.
    2. **Founders**: List the names of the founding team and there education.
    3. **Valuation/Ask**: Identify the current valuation (if mentioned) or the "Ask" (how much money they are trying to raise).
    4. **Margins & Projections**: 
       - What are their current margins (Gross/Net)?
       - What are their projected future margins or revenue targets?
    5. **Moat** "What is their unfair advantage? Why can't a big company clone them tomorrow?"
    6. **Spendings** "Look for what is their current 'Burn Rate' (how much they spend per month)?"
    7. **Executive Summary**: A concise 2-sentence summary of their value proposition.


    PITCH DECK DATA:
    {pitch_deck_text} 
    note: IMPORTANT: At the very end of your response, provide a section called 'MISSING_DATA_LIST' 
    containing only a bulleted list of things you couldn't find (e.g., - Founder names, - Burn rate).

    """
    # Note: We only send first 5000 chars to save tokens for now.

    response = None
    max_attempts = 6
    wait_time = 20  # Initial wait time in seconds

    for attempt in range(1, max_attempts + 1):
        try:            
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )
            # If successful, break out of the loop
            break 

        except Exception as e:
            error_msg = str(e).lower()
            
            # Check for Rate Limit (429) or Server Overload (503)
            if "429" in error_msg or "503" in error_msg or "resource_exhausted" in error_msg:
                if attempt < max_attempts:
                    print(f"⏳ Gemini is busy (Attempt {attempt}/{max_attempts}). Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    # Double the wait time for the next attempt
                    wait_time += 20 
                else:
                    print("🛑 MAX RETRIES REACHED. The Gemini API is currently unavailable.")
                    # Hard stop: This will stop the execution of the script
                    import sys
                    sys.exit("System terminated: API Quota exhausted after 6 attempts.")
            else: 
                print(f"❌ Unexpected Error: {e}")
                raise e

    return response.text

# --- UPDATE YOUR MAIN BLOCK ---
if __name__ == "__main__":
    import asyncio
    
    # Step 1: Run your extractor
    deck_text = asyncio.run(text_extractor())
    
    # Step 2: Hand the text to the Manager
    if deck_text:
        analysis = asyncio.run(sumarizer(deck_text))
        print("\n📊 MANAGER'S INITIAL REPORT:")
        print(analysis)