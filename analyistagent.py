from groq import AsyncGroq
import json
import os
from state import StartupState
import logging

logger = logging.getLogger("Scout.Analyist")

async def analyst_agent(state: StartupState):
    logger.info("📊 Analyst Agent is calculating financial metrics...")

    api_key = os.environ.get("GROK_KEY")
    client = AsyncGroq(api_key=api_key)

    max_retries = 3
    attempt = 0
    feedback = ""

    extraction_prompt = f"""
    You are a Senior VC Financial Auditor. Extract numeric data AND qualitative signals.
    ### TARGET SIGNALS:
    1. Founder backgrounds (Ex-FAANG, Ivy League, Serial Founder, YC).
    2. Market/Moat (High-threat competitors, Patents, proprietary tech).
    Return ONLY a valid JSON object.
    """

    while attempt < max_retries:
        try:
            logger.info(f"🔁 Analyst attempt {attempt + 1}")
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0,
                messages=[
                    {"role": "system", "content": extraction_prompt},
                    {"role": "user", "content": f"Extract data from this dossier: {state.manager_notes}\n\nFeedback: {feedback}"}
                ],
                response_format={"type": "json_object"}
            )

            extracted = json.loads(response.choices[0].message.content)
            updated_data = {**state.model_dump(), **extracted}
            state = StartupState.model_validate(updated_data)

            notes_lower = state.manager_notes.lower()

            # --- 📈 SCORING ENGINE ---
            if not state.is_public:
                headcount = max(state.headcount, 0)  # FIX: treat -1 as 0
                funding = state.total_funding
                revenue = state.annual_revenue

                # 1. Monthly Burn Logic
                monthly_burn = headcount * 15000 if headcount > 0 else 50000
                if state.hiring_status == "Aggressive": monthly_burn *= 1.25
                elif state.hiring_status == "Freeze": monthly_burn *= 0.85
                if state.vibe_score < 4.0: monthly_burn *= 1.15
                state.estimated_monthly_burn = round(monthly_burn, 2)

                # 2. Runway Calculation — FIX: funding is in millions, burn is in dollars
                funding_dollars = funding * 1_000_000  # e.g. 36.5 → $36,500,000
                if monthly_burn > 0 and funding_dollars > 0:
                    raw_runway = funding_dollars / monthly_burn
                    state.runway_months = round(min(raw_runway, 60.0), 2)  # FIX: cap at 60 months (5 years)
                else:
                    state.runway_months = 0.0

                # 3. PILLAR SCORING
                score = 0.0

                # Pillar A: Financial Health (Max 30)
                if state.runway_months >= 24: score += 30
                elif state.runway_months >= 12: score += 15
                elif state.runway_months >= 6: score += 5
                else: score -= 20

                # Pillar B: Traction & Scale (Max 30)
                if revenue > 0:
                    score += 15
                    if state.hiring_status == "Aggressive": score += 15
                else:
                    if state.hiring_status == "Aggressive": score -= 10

                # Valuation Logic
                latest_round_amount = 0.0
                if state.funding_history:
                    latest_round_amount = state.funding_history[-1].amount

                if state.latest_valuation <= latest_round_amount or state.latest_valuation == 0:
                    logger.info(f"⚖️ Adjusting Valuation: Reported ${state.latest_valuation}M vs Raised ${latest_round_amount}M")
                    revenue_multiple = (state.annual_revenue * 15.0) if state.annual_revenue > 0 else 0
                    funding_multiple = latest_round_amount * 5.0
                    state.latest_valuation = round(max(revenue_multiple, funding_multiple), 2)
                    state.manager_notes += f"\n\n[SYSTEM: Valuation adjusted to ${state.latest_valuation}M based on 15x ARR / 5x Round Dilution Benchmarks.]"

                elif "ai" in notes_lower and state.annual_revenue > 0:
                    fair_val = state.annual_revenue * 20.0
                    fair_val = min(fair_val, 500.0)  # FIX: cap at $500M, prevents $1000M bug
                    if fair_val > state.latest_valuation:
                        state.latest_valuation = round(fair_val, 2)

                # Pillar C: Team & Pedigree (Max 20)
                pedigree_signals = ["ex-", "founder", "serial", "stanford", "mit", "y-combinator", "yc", "google", "meta", "openai"]
                found_signals = sum(2 for signal in pedigree_signals if signal in notes_lower)
                score += min(20, found_signals)

                # Pillar D: Moat & Vibe (Max 20)
                vibe_contribution = (state.vibe_score / 10) * 10
                score += vibe_contribution
                if "patent" in notes_lower or "first mover" in notes_lower: score += 10
                elif "high threat" in notes_lower: score -= 5

                # Pillar E: Revenue Gate
                if revenue == 0:
                    score = min(score, 80.0)

                state.investment_score = min(100.0, max(0.0, round(score, 1)))

                # Final valuation fallback
                if state.latest_valuation == 0 and revenue > 0:
                    multiplier = 25 if "ai" in notes_lower else 15
                    state.latest_valuation = min(revenue * multiplier, 500.0)  # FIX: cap here too

            # --- ANALYST VERDICT ---
            explanation_prompt = """
            You are a Senior VC Partner. You MUST follow this EXACT format. 
            If a value is 0 or missing, state 'Data not available'.
            
            ### 👔 ANALYST VERDICT
            **Finance:** [Score]/10 - [Brief 1-sentence reason]
            **Traction:** [Score]/10 - [Brief 1-sentence reason]
            **Team:** [Score]/10 - [Brief 1-sentence reason]
            **Moat:** [Score]/10 - [Brief 1-sentence reason]
            """

            explanation = await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0,
                messages=[
                    {"role": "system", "content": explanation_prompt},
                    {"role": "user", "content": f"Summarize this data:\n{state.model_dump_json()}"}
                ],
            )

            state.manager_notes += f"\n\n{explanation.choices[0].message.content}"
            return state

        except Exception as e:
            logger.warning(f"⚠️ Analyst Reflection: {e}. Retrying...")
            feedback = str(e)
            attempt += 1

    return state