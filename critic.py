from groq import AsyncGroq
import os
import re
from state import StartupState

async def critic_agent(state: StartupState, critic_vibe: str): 
    """
    Receives the final StartupState, performs a brutal logic audit, 
    and updates the state with a final score and verdict.
    """
    print(f"🧐 The Devil's Advocate ({critic_vibe} mode) is looking for red flags...")
    
    # Use environment variable or your specific key
    api_key = os.environ.get("GROK_KEY")
    client = AsyncGroq(api_key=api_key)

    state_json = state.model_dump_json()

    # --- SHARED CROSS-EXAMINATION LOGIC ---
    vibe_logic = f"""
    ### 🕵️ AUDIT DATA INPUTS:
    - Base Investment Score: {state.investment_score}/100
    - Community Vibe Score: {state.vibe_score}/10
    - Sentiment Analysis: {state.community_sentiment}
    - Critical Signals: {state.top_complaint} | {state.reddit_signal}

    ### 🎯 SCORE ADJUSTMENT AUDIT (STRICT DETERMINISTIC)
    As a Senior Auditor, apply these EXACT adjustments to the Base Score. Do not guess.
    
    1. PLATFORM RISK: If a ban (LinkedIn, Google, Meta) is confirmed: -15 pts. Else: 0.
    2. CHURN RISK: If Churn > 50% or "High Churn" is explicitly mentioned: -10 pts. Else: 0.
    3. MOAT BOOST: If 'Proprietary Database', 'Patent', or 'Unique Dataset' exists: +5 pts. Else: 0.
    
    4. VIBE MULTIPLIER (Final Step): 
       - If Vibe Score < 3.0: Result = (Base + Adjustments) * 0.8
       - If Vibe Score > 8.0: Result = (Base + Adjustments) * 1.1
       - Otherwise: Result = (Base + Adjustments) * 1.0

    ### 📋 REQUIRED OUTPUT FORMAT
    (Note: Do not show your math. Only output the sections below.)

    **VERDICT:** [Should Buy / Watchlist / Don't Buy]

    **OPPORTUNITIES/RED FLAGS:**
    - [Specific Bullet Point 1]
    - [Specific Bullet Point 2]
    
    **STRATEGIC NARRATIVE:**
    [One clean, professional paragraph summarizing the audit findings.]

    FINAL SCOUT SCORE: [Final Calculated Number]
    """

    if critic_vibe == "hard":
        instruction = f"""
        You are a 'Skeptical Venture Capital Partner' and 'Devil's Advocate'. 
        Mission: Find the "Hidden Deaths" (Data conflicts, Moat reality, Capital Traps).
        
        TONE: Professional but Brutally Honest.
        OUTPUT:
        - VERDICT: (Should Buy / Watchlist / Don't Buy)
        - RED FLAGS: (Bullet points)
        - FAILURE NARRATIVE: (1 paragraph)
        {vibe_logic}
        """
    else:
        instruction = f"""
        You are a 'Pragmatic Venture Capital Associate'.
        Mission: Find the "Path to Scale" (Growth dynamics, Moat potential, Valuation benchmarks).
        
        TONE: Objective and Data-Driven.
        OUTPUT:
        - VERDICT: (Should Buy / Watchlist / Don't Buy)
        - OPPORTUNITIES: (Bullet points)
        - SUCCESS NARRATIVE: (1 paragraph)
        {vibe_logic}
        """

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": f"Audit this startup state: {state_json}"}
        ]
    )

    verdict_text = response.choices[0].message.content

    # --- 🛡️ THE STATE SYNC ---
    # We use regex to grab the score from the text and put it back into the Python object
    try:
        score_match = re.search(r"FINAL SCOUT SCORE:\s*(\d+\.?\d*)", verdict_text)
        if score_match:
            final_score = float(score_match.group(1))
            state.investment_score = final_score
            print(f"⚖️ Critic Final Score: {final_score}")
    except Exception as e:
        print(f"⚠️ Score extraction failed: {e}")

    # Store the full text in our state for the final report
    state.critic_verdict = verdict_text
    
    return state