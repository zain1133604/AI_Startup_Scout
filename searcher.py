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

async def researcher_agent(missing_info_list):
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
        You are a Senior Investment Researcher and Data Synthesizer. 
        
        STEP 1: Identify the name of the startup from this report: {missing_info_list}
        STEP 2: Expand it into a single, high-density 'Unified Investment Dossier'.

        ### 📂 BASE CONTEXT (FROM MANAGER):
        {missing_info_list} 

        ### 🎯 YOUR MISSION:
        1. **Identity & Data Integration:** Confirm the identified startup as the target.
        2. **Web Research (Dynamic Target Lock):** Use 'web_search_tool'. 
            - 🛑 **CRITICAL:** You are researching the target specifically in its identified industry space. 
            - DO NOT pull data for companies with the same name in different industries. 
            - For every search query, append the industry name to the company name (e.g., "[Company Name] [Industry] funding").
            - Find: Founder backgrounds, recent 2025-2026 funding, valuation, and exact headcount.
        3. **Growth Signal Audit:** Use 'hiring_pulse_tool' to see if they are actually growing. 
                - Look at the snippets: If you see "20+ jobs", mark hiring_status as 'Aggressive'.
                - If you see "0 results" or "Closed", mark as 'Freeze'.
        4. **Financials:** Look for ARR/Revenue and Unit Economics (CAC/Payback).
        5. **SOURCE URL** PROVIDE THE SOURCE URL for every key metric.

        ### 🛑 CRITICAL DATA SCHEMA (ANALYST COMPATIBILITY V4.0):
        You MUST format these specific data points as a list of OBJECTS in Section VII. 
        1. **Founders (Objects):** {{"name": "Full Name", "role": "CEO", "bio": "...", "linkedin": "..."}}
        2. **Competitors (Objects):** {{"name": "...", "description": "...", "threat_level": "High/Med/Low"}}
        3. **Funding History (Objects):** {{"round_name": "Series A", "amount": 25.0, "date": "April 2025"}}

        ### 📝 OUTPUT STRUCTURE:
        ## I. Gaps Filled & Executive Summary
        ## II. Founder & Team Profiles 
        ## III. Funding & Financials 
        ## IV. IV. Operational Metrics (Hiring Pulse & Growth)
        - Summarize the hiring status: How many roles are open? What departments?
        ## V. Competitive Comparison Matrix
        ## VI. Technology & Moat Assessment
        ## When you find a value for funding, revenue, or headcount, you must return it in this format:
            FACT: [The Number]
            SOURCE: [The URL]
        
        5. 🕵️ **MANDATORY VIBE CHECK (The "Shadow Search"):**
        You MUST perform a deep-dive into community sentiment for the **specific industry product** mentioned above.
        - **Primary Search:** Use site:reddit.com "[Company Name]" + [identified industry] + review OR bug.
        - **Secondary Search:** Search `"[Company Name] [Industry] reviews" OR "[Company Name] [Industry] scam"`.
        - **Verification:** If the search results describe a product that does NOT match the startup's purpose, DISCARD THEM.

        ### 🧱 VII. RAW DATA BLOCK (FOR SYSTEM PARSING)
        You MUST provide the final data as a single JSON code block. 
        Ensure the keys match these exactly:
        {{
            "company_name": string,
            "industry": string,
            "is_public": boolean,
            "total_funding": float,
            "latest_valuation": float,
            "annual_revenue": float,
            "headcount": integer,
            "hiring_status": "Aggressive" | "Maintain" | "Freeze",
            "open_roles": integer,
            "vibe_score": float,
            "community_sentiment": string,
            "sources": {{
                "total_funding": "url",
                "latest_valuation": "url",
                "annual_revenue": "url",
                "headcount": "url"
            }}
        }}
        MANDATORY: Return ONLY the JSON inside the code block for this section. Use 0.0 for missing numbers.
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
            state = StartupState.model_validate({**state.model_dump(), **data})
            if "sources" in data:
                state.sources.update(data["sources"])
        except Exception as e:
            logger.error(f"⚠️ Validation Error: {e}")

    return state