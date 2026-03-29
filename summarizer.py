import os
from google import genai
from textextractor import text_extractor
from dotenv import load_dotenv
import os
import asyncio
import logging 

logger = logging.getLogger("Scout.Summarizer")


load_dotenv()
gemini_key = os.environ.get("GEMINI_KEY")



async def sumarizer(pitch_deck_text):
    client = genai.Client(api_key=os.environ.get("GEMINI_KEY"))
    logger.info("\n👔 Summarizer is analyzing the briefing...")

    prompt = f"""
    You are a Senior Investment Analyst. Read this extracted pitch deck text carefully.

    ⚠️ CRITICAL RULE: The company presenting this pitch deck is the OWNER of this deck.
    - It is the company asking for investment
    - It is NOT a client, case study, partner, or competitor mentioned in the deck
    - It is usually mentioned on the FIRST page / cover slide

    TASKS:
    1. **Company Name**: The startup that CREATED and is PRESENTING this deck.
    - Look at the very first lines of the text — cover page is usually there
    - If multiple company names appear, the PRESENTER is the one asking for funding
    - DO NOT pick a client name, case study company, or example brand

    2. **Founders**: Names of the founding team and their education.
    3. **Valuation/Ask**: Current valuation or funding ask amount.
    4. **Margins & Projections**: Current and projected margins/revenue.
    5. **Moat**: Their unfair advantage.
    6. **Spendings**: Monthly burn rate.
    7. **Executive Summary**: 2-sentence value proposition.

    PITCH DECK DATA (first part is usually the cover/title):
    {pitch_deck_text}

    IMPORTANT: At the very end, provide 'MISSING_DATA_LIST' with bulleted missing items.

    IMPORTANT: Return company name STRICTLY in this format on its own line:
    COMPANY_NAME: <name here>
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
                    logger.warning(f"⏳ Gemini is busy (Attempt {attempt}/{max_attempts}). Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    # Double the wait time for the next attempt
                    wait_time += 20 
                else:
                    logger.info("🛑 MAX RETRIES REACHED. The Gemini API is currently unavailable.")
                    # Hard stop: This will stop the execution of the script
                    import sys
                    sys.exit("System terminated: API Quota exhausted after 6 attempts.")
            else: 
                logger.error(f"❌ Unexpected Error: {e}")
                raise e

    return response.text

