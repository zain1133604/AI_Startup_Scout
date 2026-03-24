from google import genai
from researchertools import web_search_tool , hiring_pulse_tool
from dotenv import load_dotenv
import os
from state import StartupState, parse_financial_string
import sys
import asyncio
import re
import json
import logging
logger = logging.getLogger("Scout.Searcher")


load_dotenv()
gemini_key = os.environ.get("GEMINI_KEY")



async def researcher_agent(missing_info_list):
    client = genai.Client(api_key=os.environ.get("GEMINI_KEY"))
    logger.info("🕵️  Researcher Agent is starting work...")


    max_attempts = 6
    wait_time = 20
    for attempt in range(1, max_attempts + 1):
        try: 
            chat = client.chats.create(
                model='gemini-2.5-flash',
                config={
                    'tools': [web_search_tool, hiring_pulse_tool ],
                    'automatic_function_calling': {'disable': False} 
                }
            )
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
                    logger.warning("🛑 MAX RETRIES REACHED. The Gemini API is currently unavailable.")
                    # Hard stop: This will stop the execution of the script
                    import sys
                    sys.exit("System terminated: API Quota exhausted after 6 attempts.")
            else: 
                logger.error(f"❌ Unexpected Error: {e}")
                raise e
    # 1. 🔍 QUICK ID: Just get the name first so we don't lose the "Target"
    id_check = chat.send_message(f"Based on this report: {missing_info_list}, what is the name of the startup? Return ONLY the name.")
    found_name = id_check.text.strip()
    logger.info(f"🛰️ Target Identified: {found_name}")

    prompt = f"""
        You are a Senior Investment Researcher and Data Synthesizer. 
        Your mission is to take the initial 'Manager's Report' and expand it into a single, high-density 'Unified Investment Dossier' specifically for **{found_name}**.

        ### 📂 BASE CONTEXT (FROM MANAGER):
        {missing_info_list} 

        ### 🎯 YOUR MISSION:
        1. **Identity & Data Integration:** Confirm **{found_name}** as the target.
        2. **Web Research (Dynamic Target Lock):** Use 'web_search_tool'. 
            - 🛑 **CRITICAL:** You are researching **{found_name}** specifically in the **[Identify Industry]** space. 
            - DO NOT pull data for companies with the same name in different industries. 
            - For every search query, append the industry name to the company name (e.g., "{found_name} [Industry] funding").
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
        - **Primary Search:** Use site:reddit.com "{found_name}" + [identified industry] + review OR bug.
        - **Secondary Search:** Search `"{found_name} [Industry] reviews" OR "{found_name} [Industry] scam"`.
        - **Verification:** If the search results describe a product that does NOT match the startup's purpose (e.g. you find a music app but the target is a dating app), DISCARD THEM.


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
    
        NOTE: If you find multiple sources, use the most recent or reliable one (e.g., Crunchbase, Reuters, or Official Company Site).
    """
    


    # -------------------------------
    # 🧠 HELPER: JSON EXTRACTOR
    # -------------------------------
    def extract_json(content: str):
        try:
            # 1. Try proper markdown JSON block
            match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                return json.loads(match.group(1))

            # 2. Fallback: any JSON-like object
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))

        except Exception:
            return None

        return None


    # -------------------------------
    # 🚀 REFLECTION LOOP (FIXED)
    # -------------------------------
    response = None
    content = ""
    data = None
    ref_wait_time = 20

    for reflection_attempt in range(2):
        await asyncio.sleep(ref_wait_time)
        ref_wait_time = ref_wait_time + 10
        logger.info(f"📡 Researcher Attempt {reflection_attempt + 1}...")

        response = chat.send_message(prompt)
        content = response.text

        data = extract_json(content)

        # ✅ QUALITY CHECK (REAL SYSTEM)
        if data:
            try:
                validated = StartupState.model_validate(data)

                # Optional stronger check
                if validated.total_funding > 0:
                    print("✅ Valid structured data found")
                    break

            except Exception as e:
                print(f"⚠️ Validation failed: {e}")

        # 🔁 Reflection retry
        if reflection_attempt == 0:
            logger.warning("⚠️ Reflection: Invalid or missing structured data. Retrying...")

            prompt += f"""

    🚨 REFLECTION FEEDBACK:
    Your previous response was invalid.

    FIX:
    - Return ONLY valid JSON
    - Ensure 'total_funding' is correct and NOT 0
    - Ensure company_name and industry are filled
    """
        else:
            logger.warning("⚠️ Reflection failed twice. Continuing with best effort.")


    # -------------------------------
    # 🏗️ STATE CREATION
    # -------------------------------
    state = StartupState(
        company_name=found_name,
        industry="Identified in Dossier",
        manager_notes=content
    )


    # -------------------------------
    # 🧱 STRUCTURED DATA PARSING
    # -------------------------------
    try:
        if data:
            state = StartupState.model_validate({**state.model_dump(), **data})

            if "sources" in data:
                state.sources.update(data["sources"])

            logger.info(f"✅ Structured Data Applied for {state.company_name}")
        else:
            logger.warning("⚠️ No valid JSON found. Using raw text only.")

    except Exception as e:
        logger.error(f"⚠️ Final Parsing Error: {e}")


    # -------------------------------
    # 🚀 RETURN
    # -------------------------------
    return state




