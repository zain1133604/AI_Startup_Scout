from groq import AsyncGroq
import json
import os
from state import StartupState

async def analyst_agent(state: StartupState):
    print("📊 Analyst Agent is calculating financial metrics...")

    # Best practice: Load API key from env
    api_key = os.environ.get("GROQ_KEY", "")
    client = AsyncGroq(api_key=api_key)

    max_retries = 3
    attempt = 0
    feedback = ""
    reflection_history = []

    # System prompt optimized for extraction and structured output
    extraction_prompt = f"""
    You are a financial data extraction agent for a Venture Capital firm.
    Your job is to extract raw numeric data from the dossier provided.

    Rules:
    - Return ONLY a valid JSON object.
    - If a value is unknown, use 0.
    - Do NOT perform math; just extract.

    ### ⚠️ SENTIMENT ADJUSTMENT CONTEXT:
    Current Community Vibe: {state.community_sentiment}
    Vibe Score: {state.vibe_score}/10
    Top Complaint: {state.top_complaint}
    """

    while attempt < max_retries:
        try:
            print(f"🔁 Analyst attempt {attempt + 1}")

            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": extraction_prompt},
                    {
                        "role": "user",
                        "content": f"Extract data from this dossier: {state.manager_notes}\n\nFeedback: {feedback}"
                    }
                ],
                response_format={"type": "json_object"}
            )

            extracted = json.loads(response.choices[0].message.content)

            # --- 🔥 THE PREDANTIC MERGE ---
            # model_validate triggers all the financial string parsing and bool casting
            # defined in your state.py automatically.
            updated_data = {**state.model_dump(), **extracted}
            state = StartupState.model_validate(updated_data)

            # --- 📈 PYTHON FINANCIAL ENGINE (The "Brain") ---
            if not state.is_public:
                headcount = state.headcount
                funding = state.total_funding
                revenue = state.annual_revenue

                # 1. Base Monthly Burn ($15k per head standard)
                monthly_burn = headcount * 15000 if headcount > 0 else 0

                # 2. Hiring Multipliers
                if state.hiring_status == "Aggressive":
                    monthly_burn *= 1.2
                elif state.hiring_status == "Freeze":
                    monthly_burn *= 0.9

                # 3. SENTIMENT ADJUSTMENT PROTOCOL
                # If vibe is bad, we assume higher support costs and technical debt drag
                if state.community_sentiment.lower() == "negative" or state.vibe_score < 4.0:
                    monthly_burn *= 1.15
                    state.manager_notes += "\n[Analyst Note] Burn increased by 15% due to Sentiment Risk."

                state.estimated_monthly_burn = round(monthly_burn, 2)

                # 4. Runway Calculation
                # Handle millions (e.g., 46.1) vs full numbers
                funding_actual = funding * 1_000_000 if funding < 1000 and funding > 0 else funding
                
                if monthly_burn > 0:
                    state.runway_months = round(funding_actual / monthly_burn, 2)

                # 5. Strategic Scoring (Max 100)
                base_score = 0
                
                # Financial Health (40 pts)
                if state.runway_months >= 24: base_score += 40
                elif state.runway_months >= 12: base_score += 25
                elif state.runway_months >= 6: base_score += 10
                
                # Traction (40 pts)
                if revenue > 0: base_score += 20
                if state.hiring_status == "Aggressive": base_score += 20
                
                # Community Vibe (20 pts)
                # Apply 10% CAC discount logic to the score if positive
                vibe_pts = state.vibe_score * 2
                if state.vibe_score > 8.5:
                    vibe_pts *= 1.1 # 10% organic growth bonus
                base_score += vibe_pts

                state.investment_score = min(100.0, round(base_score, 1))

                # Valuation Estimate (20x Revenue if not provided)
                if state.latest_valuation == 0 and revenue > 0:
                    state.latest_valuation = revenue * 20

            # --- 📝 LLM NARRATIVE EXPLANATION ---
            explanation_prompt = "You are a VC financial analyst. Explain the current runway, burn, and investment score professionally."
            
            explanation = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": explanation_prompt},
                    {"role": "user", "content": f"Summarize this data:\n{state.model_dump_json()}"}
                ],
            )

            state.manager_notes += f"\n\n### 👔 ANALYST VERDICT\n{explanation.choices[0].message.content}"
            print(f"✅ Analyst passed validation on attempt {attempt + 1}")
            return state

        except Exception as e:
            error_message = str(e)
            reflection_history.append({"attempt": attempt + 1, "error": error_message})
            feedback = error_message
            print(f"⚠️ Analyst Reflection: {error_message}. Retrying...")
            attempt += 1

    return state