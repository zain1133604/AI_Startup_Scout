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
    api_key = os.environ.get("GROQ_API_KEY", "")
    client = AsyncGroq(api_key=api_key)

    state_json = state.model_dump_json()

    # --- SHARED CROSS-EXAMINATION LOGIC ---
    vibe_logic = f"""
    ### 🕵️ THE VIBE VS. MATH CROSS-EXAMINATION:
    1. Community Sentiment: {state.community_sentiment}
    2. Vibe Score: {state.vibe_score}/10
    3. Top User Complaint: {state.top_complaint}
    4. Reddit Signal: {state.reddit_signal}
    5. Analyst Base Score: {state.investment_score}/100

    ### 🎯 SCORE ADJUSTMENT PROTOCOL:
    - If you find CRITICAL RED FLAGS: Deduct 10-30 points.
    - If you find UNFAIR ADVANTAGES: Add 5-10 points.
    - MANDATORY: You MUST output the final adjusted score at the very end in this EXACT format:
      FINAL SCOUT SCORE: [number]
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