from google import genai
from researchertools import web_search_tool , hiring_pulse_tool
from dotenv import load_dotenv
import os
from state import StartupState, parse_financial_string
import sys
import asyncio
load_dotenv()
gemini_key = os.environ.get("GEMINI_KEY")

# FIX 1: Pass the actual variable to the client
client = genai.Client(api_key=gemini_key)

async def researcher_agent(missing_info_list):
    print("🕵️  Researcher Agent is starting work...")


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
    # 1. 🔍 QUICK ID: Just get the name first so we don't lose the "Target"
    id_check = chat.send_message(f"Based on this report: {missing_info_list}, what is the name of the startup? Return ONLY the name.")
    found_name = id_check.text.strip()
    print(f"🛰️ Target Identified: {found_name}")

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
        --- START RAW DATA ---
        company_name: {found_name}
        industry: [Identify Industry]
        is_public: [True/False]
        
        total_funding: [Float, e.g. 46.1]
        funding_source: https://x.com/search_found
        
        latest_valuation: [If not found, estimate 4x the total funding. e.g. 40.0]
        valuation_source: https://x.com/search_found
        
        annual_revenue: [Float, e.g. 7.0]
        revenue_source: https://x.com/search_found
        
        headcount: [Integer, e.g. 88]
        headcount_source: https://x.com/search_found
        
        hiring_status: [Aggressive/Maintain/Freeze]
        open_roles: [Integer, e.g. 24]
        cac: [Float, e.g. 5000.0]
        payback_period: [Float, e.g. 2.6]

        community_sentiment: [Positive/Neutral/negative]
        top_complaint: [Most common bug or user complaint found on Reddit]
        vibe_score: [Float 1.0 to 10.0 based on community mood]
        reddit_signal: [One sentence summary of Reddit threads]
        --- END RAW DATA ---

        *MANDATORY: Section VII is for the Python backend. Use ONLY numbers. If data is not found, use 0.0.*
        

        NOTE: If you find multiple sources, use the most recent or reliable one (e.g., Crunchbase, Reuters, or Official Company Site).
    """
    


# 1. Send the full master prompt
    response = None
    content = ""
    
    for reflection_attempt in range(2): # Give it 2 chances to get the data right
        print(f"📡 Researcher Attempt {reflection_attempt + 1}...")
        
        response = chat.send_message(prompt)
        content = response.text 

        # --- THE QUALITY GATE ---
        # 1. Did it forget the block?
        # 2. Did it find $0 funding? (Usually means it found the wrong 'Artisan')
        has_block = "--- START RAW DATA ---" in content
        is_empty = "total_funding: 0.0" in content or "total_funding: 0" in content
        
        if has_block and not is_empty:
            break  # ✅ SUCCESS: It found real data!
        
        if reflection_attempt == 0: # Only nudge if it's the first fail
            print("⚠️ Reflection: Data looks empty or malformed. Sending a 'Nudge'...")
            # We update the prompt for the next loop iteration
            prompt += f"\n\n🚨 REFLECTION FEEDBACK: You returned 0.0 funding for {found_name}. This is likely wrong. Use the web_search_tool specifically for '{found_name} startup funding' and RE-WRITE the RAW DATA BLOCK."
        else:
            print("⚠️ Reflection failed twice. Moving forward with what we have.")

    # --- (The rest of your code remains 100% the same) ---
    
    # 2. Initialize the State object
    state = StartupState(
        company_name=found_name, 
        industry="Identified in Dossier",
        manager_notes=content 
    )

    # 3. FILL THE HOUSE (Parsing Logic)
    try:
        if "--- START RAW DATA ---" in content and "--- END RAW DATA ---" in content:
            raw_section = content.split("--- START RAW DATA ---")[1].split("--- END RAW DATA ---")[0]

            # List of keys that MUST be strings
            string_keys = [
                "community_sentiment", "top_complaint", "reddit_signal", 
                "company_name", "industry", "hiring_status", "is_public"
            ]

            for line in raw_section.strip().split("\n"):
                if ":" in line:
                    parts = line.split(":", 1)
                    # Clean the key: remove bullets, spaces, and make lowercase
                    key = parts[0].replace("*", "").strip().lower() 
                    value = parts[1].strip()
                    
                    # A. Capture Source URLs
                    if key.endswith("_source"):
                        field_name = key.replace("_source", "")
                        state.sources[field_name] = value 
                    
                    # B. Handle Strings
                    elif key in string_keys:
                        setattr(state, key, str(value))

                    # C. Handle Vibe Score Specifically (The Fix)
                    elif key == "vibe_score":
                        # Only take the first part if Gemini writes "7.5/10"
                        clean_val = "".join(c for c in value.split('/')[0] if c.isdigit() or c == '.')
                        if clean_val:
                            state.vibe_score = float(clean_val)

                    # D. Handle Other Numeric Data
                    elif hasattr(state, key):
                        clean_val = "".join(c for c in value if c.isdigit() or c == '.')
                        if clean_val:
                            try:
                                val = float(clean_val) if "." in clean_val else int(clean_val)
                                setattr(state, key, val)
                            except:
                                pass
            print(f"✅ Researcher found {len(state.sources)} source links and vibe metrics.")
        else:
            print("⚠️ RAW DATA BLOCK not found in Gemini response!")

    except Exception as e:
        print(f"⚠️ Parsing Error: {e}")

    # 4. SHIP THE HOUSE (Make sure you are returning the 'state' object itself)
    return state



