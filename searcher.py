from google import genai
from researchertools import web_search_tool, hiring_pulse_tool
from dotenv import load_dotenv
import os
from state import StartupState
import asyncio
import re
import json
import logging

logger = logging.getLogger("Scout.Searcher")
load_dotenv()

async def researcher_agent(missing_info_list, raw_deck_text=None):
    client = genai.Client(api_key=os.environ.get("GEMINI_KEY"))
    logger.info("🕵️ Researcher Agent is starting work...")

    # --- 1. INITIALIZE SESSION ---
    max_attempts = 3 
    wait_time = 15
    chat = None

    for attempt in range(1, max_attempts + 1):
        try: 
            chat = client.chats.create(
                model='gemini-2.5-flash-lite',
                config={
                    'tools': [web_search_tool, hiring_pulse_tool],
                    'automatic_function_calling': {'disable': False} 
                }
            )
            break 
        except Exception as e:
            if any(code in str(e) for code in ["429", "503", "resource_exhausted"]):
                if attempt < max_attempts:
                    logger.warning(f"⏳ API Busy. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    wait_time += 15
                else:
                    logger.error("🛑 API Quota Exhausted.")
                    return StartupState(company_name="Pending", manager_notes="API Error: Quota Exhausted")
            else:
                raise e

    # --- 2. THE PROMPT ---
    # Note: I added a instruction to find the name FIRST since we removed the separate ID call.
# We remove the separate id_check call and let the prompt handle it.
    full_prompt = f"""
    You are a Senior Investment Researcher. Your job has TWO phases.

    === PHASE 1: RESEARCH & NARRATIVE ===

    BASE CONTEXT (from manager summary):
    {missing_info_list}

    STEP 1 - IDENTIFY: What is the startup's name and industry?
    STEP 2 - WEB RESEARCH: Use web_search_tool. 
        - SUBSIDIARY RULE: If the target is a subsidiary, research IT DIRECTLY. 
        Do NOT switch to the parent company.
        - Append industry to every search: "[Company Name] [Industry] funding 2025"
        - Find: founders, funding rounds, valuation, ARR, headcount
        - For EVERY number found, write: FACT: [value] SOURCE: [url]

    STEP 3 - HIRING PULSE: Use hiring_pulse_tool for the TARGET company name only.
        - Count exact number of open roles from the results
        - If 10+ jobs: "Aggressive", 1-9: "Maintain", 0: "Freeze"

    STEP 4 - COMPETITORS: Find 3-5 direct competitors with threat levels.

    STEP 5 - VIBE CHECK: Search site:reddit.com "[Company Name]" reviews
        - Score sentiment 1-10 (1=very negative, 5=neutral, 10=very positive)
        - If no Reddit data found, score is 5.0

    ## I. Executive Summary
    ## II. Founder Profiles  
    ## III. Funding & Financials (with FACT/SOURCE tags)
    ## IV. Hiring Pulse Results
    ## V. Competitor Matrix
    ## VI. Moat Assessment
    ## VII. Vibe Check Results

    === PHASE 2: JSON EXTRACTION ===

    NOW, look back at everything you wrote above and extract the numbers into this JSON.
    If a value was mentioned anywhere in Phase 1, it MUST appear here — not 0.0.
    If truly unknown, use -1.0 for numbers and "Unknown" for strings.
    NEVER use 0.0 unless the actual value is literally zero.
    ```json
    {{
        "company_name": "exact name from deck",
        "industry": "specific industry",
        "is_public": false,
        "total_funding": <number in millions, e.g. 46.1 for $46.1M>,
        "latest_valuation": <number in millions>,
        "annual_revenue": <number in millions>,
        "headcount": <integer, exact count>,
        "hiring_status": "Aggressive|Maintain|Freeze",
        "open_roles": <integer, count from hiring tool>,
        "vibe_score": <float 1.0-10.0>,
        "community_sentiment": "one sentence summary",
        "founders": [
            {{"name": "Full Name", "role": "CEO", "bio": "2 sentence bio", "linkedin": "url or Not Found"}}
        ],
        "competitors": [
            {{"name": "Company", "description": "what they do", "threat_level": "High|Medium|Low"}}
        ],
        "funding_history": [
            {{"round_name": "Series A", "amount": 25.0, "date": "April 2025"}}
        ],
        "sources": {{
            "total_funding": "url",
            "latest_valuation": "url", 
            "annual_revenue": "url",
            "headcount": "url"
        }}
    }}
    ```

SELF-CHECK before finishing:
- Did I put 0.0 anywhere? If yes, go back and check Phase 1 — was it actually mentioned?
- Are founders/competitors arrays populated if I found them in Phase 1?
- Is open_roles an actual count from the hiring tool?
"""

    # --- 3. REFLECTION LOOP ---
    content = ""
    data = None
    
    for reflection_attempt in range(2):
        logger.info(f"📡 Researcher Execution (Attempt {reflection_attempt + 1})...")
        await asyncio.sleep(30)
        
        try:
            # FIXED: Sending 'full_prompt'
            response = chat.send_message(full_prompt)
            content = response.text
            
            # Extract JSON safely
            json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            
            if json_match:
                raw_json = json_match.group(1)
            else:
                # Fallback: Look for anything between curly braces
                fallback_match = re.search(r"\{.*\}", content, re.DOTALL)
                raw_json = fallback_match.group(0) if fallback_match else "{}"

            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError:
                logger.error("Failed to decode JSON from Gemini response.")
                data = {}

            if data and data.get("company_name") and data.get("company_name") != "Pending":
                logger.info(f"✅ Quality Research Obtained for {data['company_name']}")
                break
        
        except Exception as e:
                    logger.warning(f"⚠️ Reflection {reflection_attempt + 1} failed: {e}")
                    
                    # Check for Quota/Rate limits in the error string
                    error_str = str(e).lower()
                    if any(x in error_str for x in ["429", "resource_exhausted", "quota"]):
                        return StartupState(
                            company_name="Pending", 
                            manager_notes="CRITICAL_QUOTA_ERROR: Search tool or API exhausted."
                        )
                    
                    if reflection_attempt == 0:
                        full_prompt += "\n\n🚨 ERROR: Your previous response was invalid. Please ensure you provide the Section VII JSON block."
                        continue

    # --- 4. STATE ASSEMBLY ---
    found_name = data.get("company_name", "Unknown") if data else "Unknown"
    
    state = StartupState(
        company_name=found_name,
        industry=data.get("industry", "Identified in Dossier") if data else "Identified in Dossier",
        manager_notes=content
    )

    if data:
        try:
            # Explicitly map lists if they exist in the LLM's JSON
            state.founders = data.get("founders", [])
            state.competitors = data.get("competitors", [])
            state.headcount = data.get("headcount", 0)
            
            # Then validate the rest
            state = StartupState.model_validate({**state.model_dump(), **data})
        except Exception as e:
            logger.error(f"⚠️ Validation Error: {e}")

    return state