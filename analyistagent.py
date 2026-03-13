# 👨‍🔧👨‍🔧  new analyst
from groq import AsyncGroq
import json
from state import StartupState


async def analyst_agent(state: StartupState):

    print("📊 Analyst Agent is calculating financial metrics...")

    client = AsyncGroq(api_key="")

    max_retries = 3
    attempt = 0
    feedback = ""
    reflection_history = []

    state_json = state.model_dump_json()

    extraction_prompt = """
You are a financial data extraction agent.

Your job is ONLY to extract missing numeric fields from the dossier.

Return JSON with these fields:

- headcount
- total_funding
- annual_revenue
- latest_valuation
- hiring_status
- is_public

Rules:
- Return numbers only (not strings)
- If unknown return 0
- Do NOT perform financial math

### ⚠️ SENTIMENT ADJUSTMENT PROTOCOL:
    You must factor in the following 'Community Vibe' data into your financial modeling:
    - Sentiment: {state.community_sentiment}
    - Vibe Score: {state.vibe_score}/10
    - Top Complaint: {state.top_complaint}

    **ADJUSTMENT RULES:**
    1. If Sentiment is 'Negative' or Vibe Score < 4.0:
       - Increase the 'Estimated Monthly Burn' by 15% (Account for 'Technical Debt' and 'Emergency Support').
       - Add a 'Sentiment Risk' note to your analysis.
    2. If Sentiment is 'Positive' or Vibe Score > 8.5:
       - Decrease the 'CAC' (Customer Acquisition Cost) assumption by 10% due to organic word-of-mouth.
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
                        "content": f"""
Extract financial fields from this state:

{state_json}

Reflection feedback:
{feedback}
"""
                    }
                ],
                response_format={"type": "json_object"}
            )

            extracted = json.loads(response.choices[0].message.content)

            # --------------------------------
            # NUMERIC SANITIZATION
            # --------------------------------

            for k, v in extracted.items():
                if isinstance(v, str):
                    try:
                        extracted[k] = float(v)
                    except:
                        pass

            # --------------------------------
            # MERGE EXTRACTED DATA
            # --------------------------------

            for key, value in extracted.items():

                if hasattr(state, key):

                    if value and value != 0 and value != 0.0:
                        setattr(state, key, value)

            # --------------------------------
            # PYTHON FINANCIAL ENGINE
            # --------------------------------

            if not state.is_public:

                headcount = getattr(state, "headcount", 0)
                funding = getattr(state, "total_funding", 0)
                revenue = getattr(state, "annual_revenue", 0)

                monthly_burn = 0

                if headcount > 0:
                    monthly_burn = headcount * 15000

                if getattr(state, "hiring_status", "") == "Aggressive":
                    monthly_burn *= 1.2

                if getattr(state, "hiring_status", "") == "Freeze":
                    monthly_burn *= 0.9
                
                state.estimated_monthly_burn = round(monthly_burn, 2)

                if funding > 0 and funding < 1000: # It's likely in Millions (e.g. 46.1)
                    funding_actual = funding * 1_000_000
                else: # It's already a full number or 0
                    funding_actual = funding

                if monthly_burn > 0:
                    state.runway_months = round(funding_actual / monthly_burn, 2)

                if monthly_burn > 0 and funding > 0:
                    runway = (funding * 1_000_000) / monthly_burn
                    state.runway_months = round(runway, 2)

                base_score = 0
                
                # 1. Financial Health (Max 40 pts)
                runway = getattr(state, "runway_months", 0)
                if runway >= 24: base_score += 40
                elif runway >= 12: base_score += 25
                elif runway >= 6: base_score += 10
                
                # 2. Market Traction (Max 40 pts)
                # Scoring based on revenue/valuation ratio or hiring
                if state.annual_revenue > 0: base_score += 20
                if state.hiring_status == "Aggressive": base_score += 20
                elif state.hiring_status == "Stable": base_score += 10
                
                # 3. Community Vibe (Max 20 pts)
                # Convert 10-point vibe to 20-point scale
                base_score += (state.vibe_score * 2)

                state.investment_score = round(base_score, 1)

                if state.latest_valuation == 0 and revenue > 0:
                    state.latest_valuation = revenue * 20

            # --------------------------------
            # VALIDATION CHECKS
            # --------------------------------

            if state.total_funding > 0 and not state.is_public:

                if getattr(state, "runway_months", 0) <= 0:
                    raise ValueError("Runway calculation failed")

            if getattr(state, "monthly_burn", 0) < 0:
                raise ValueError("Burn cannot be negative")

            if getattr(state, "latest_valuation", 0) < 0:
                raise ValueError("Valuation cannot be negative")

            # --------------------------------
            # LLM NARRATIVE EXPLANATION
            # --------------------------------

            explanation_prompt = """
You are a VC financial analyst.

Explain the financial calculations based on the given structured data.

Do NOT recompute the numbers.
Only explain them professionally.
"""

            explanation = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": explanation_prompt},
                    {
                        "role": "user",
                        "content": f"State data:\n{state.model_dump_json()}"
                    }
                ],
            )

            narrative = explanation.choices[0].message.content

            state.manager_notes += "\n\nAnalyst Explanation:\n" + narrative

            print(f"✅ Analyst passed validation on attempt {attempt + 1}")

            state.manager_notes += f"\nReflection history: {reflection_history}"

            return state

        except Exception as e:

            error_message = str(e)

            reflection_history.append(
                {
                    "attempt": attempt + 1,
                    "error": error_message
                }
            )

            feedback += f"\nAttempt {attempt+1}: {error_message}"

            print(f"⚠️ Analyst Reflection: {error_message}. Retrying...")

            attempt += 1

    # --------------------------------
    # SAFE PIPELINE FALLBACK
    # --------------------------------

    print("❌ Max retries reached. Returning existing state.")

    state.manager_notes += f"\nAnalyst reflection failures: {reflection_history}"

    return state