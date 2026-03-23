# 👨‍🔧👨‍🔧 new main 
import asyncio
import json
import re
from textextractor import text_extractor
from summarizer import sumarizer
from searcher import researcher_agent
from analyistagent import analyst_agent
from critic import critic_agent

# --- 🛠️ HELPER: PORTFOLIO FORMATTER ---
def portfolio_format(label, value, prefix="$", suffix=""):
    """
    Portfolio-grade formatter:
    1. Handles N/A data.
    2. Detects 'naked' millions (e.g., 46.1 -> $46.1M).
    3. Scales large raw numbers (e.g., 46100000 -> $46.1M).
    """
    if value is None or value == 0:
        return f"  • {label:22}: [Data Not Found]"
    
    # 1. Handle Billions (Raw: 1,000,000,000+)
    if value >= 1_000_000_000:
        return f"  • {label:22}: {prefix}{value / 1_000_000_000:,.1f}B{suffix}"
    
    # 2. Handle Millions (Raw: 1,000,000+)
    if value >= 1_000_000:
        return f"  • {label:22}: {prefix}{value / 1_000_000:,.1f}M{suffix}"
    
    # 3. Handle 'Naked' Millions/Billions (Researcher found 46.1 or 7.0)
    # We assume if it's a financial metric (prefix=$) and under 1000, it's already scaled to Millions
    if prefix == "$" and 0 < value < 1000:
        return f"  • {label:22}: {prefix}{value:,.1f}M{suffix}"

    # 4. Handle Thousands
    if value >= 1_000:
        return f"  • {label:22}: {prefix}{value / 1_000:,.1f}K{suffix}"
    
    # 5. Fallback for raw small numbers (like 10.2 months or small integer counts)
    return f"  • {label:22}: {prefix}{value:,.2f}{suffix}"

async def run_scout_squad():
    print("🚀 Welcome to AI-Scout 2026")
    print("[1] Normal Standard Due Diligence (Balanced Opportunity/Risk)")
    print("[2] Hard Stress-Test (High-Skepticism / Red Flag Focus)")
    vibe_choice = input("Choose: ")

    critic_vibe = "hard" if vibe_choice == "2" else "normal"
    print(f"✅ System initialized with {critic_vibe.upper()} mode.\n")

    # 1. Extract Text from PDF
    deck_text = await text_extractor()
    if not deck_text: 
        print("❌ Script stopped: No text was extracted.")
        return

    # 2. Manager's Initial Scan
    manager_report = await sumarizer(deck_text)
    print("\n👔 MANAGER'S INITIAL REPORT COMPLETE.")

    # 3. Researcher (Structured Output)
    print("\n🛰️ Starting Researcher (Filling Structured State)...")
    state = None
    max_retries = 3
    retry_delay = 20  # Seconds to wait between fails

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"🔄 Retry Attempt {attempt}/{max_retries}... Waiting {retry_delay}s")
                await asyncio.sleep(retry_delay)
            else:
                await asyncio.sleep(1) # Initial small breath            
            # --- THE CORE AGENT CALL ---
            state = await researcher_agent(manager_report)            
            # --- 🛡️ SYNC STEP ---
            state = state.model_validate(state.model_dump()) 
            
            print(f"✅ Data found for: {state.company_name}")
            break  # <--- SUCCESS! Break the loop and move to Analyst.
        except Exception as e:
            print(f"⚠️ Researcher Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("❌ Researcher failed permanently after 3 attempts.")
                return # Stop the script
    print(f"DEBUG: Researcher found Funding: {state.total_funding}, Headcount: {state.headcount}")


    traction_score = (state.total_funding > 0) + (state.headcount > 0) + (state.annual_revenue > 0)
    
    # Check if we have a real industry (not just 'Identified in Dossier' or 'Unknown')
    valid_industries = ["saas", "tech", "ai", "software", "medical", "fintech", "robotics"] # add more if needed
    is_real_industry = any(word in state.industry.lower() for word in valid_industries) if state.industry else False

    if traction_score == 0 and not is_real_industry:
        print("\n🚫 [GATEKEEPER]: DATA INSUFFICIENT")
        print("❌ The Researcher only found a name but NO financial or industry traction.")
        print(f"🛰️  Target '{state.company_name}' appears too generic or has no public footprint.")
        print("💡 Suggestion: Run it again but use a specific name like 'Artisan AI' or 'Artisan.co'.")
        return
 
 
    # 4. Analyst (Financial Refinement)
    print("\n📊 Calling Financial Analyst (Groq)...")    
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"🔄 Analyst Retry Attempt {attempt}/{max_retries}... Waiting {retry_delay}s")
                await asyncio.sleep(retry_delay)            
            print("📊 Analyst Agent is calculating financial metrics...")           
            # --- THE CORE AGENT CALL ---
            state = await analyst_agent(state)            
            print(f"✅ Math complete. Estimated Runway: {state.runway_months:.1f} months.")
            break  # <--- SUCCESS! Move to Critic.
        except Exception as e:
            print(f"⚠️ Analyst Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("❌ Analyst failed permanently after 3 attempts.")



# 5. Critic (The Skeptic with 3-Try Resilience)
    print("\n🧐 The Devil's Advocate is reviewing the case...")    
    
    # 🌟 STEP 1: Initialize 'verdict' as an empty string to kill the yellow line
    verdict = "" 

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"🔄 Critic Retry Attempt {attempt}/{max_retries}... Waiting {retry_delay}s")
                await asyncio.sleep(retry_delay)            
            
            print("🧐 The Devil's Advocate is looking for red flags...")            
            
            # 🌟 STEP 2: Call the agent and get the UPDATED STATE object
            updated_result = await critic_agent(state, critic_vibe)
            
            # 🌟 STEP 3: Extract the STRING verdict from that object
            # This prevents the circular reference error!
            verdict = str(updated_result.critic_verdict)
            
            # Sync the main state with the results
            state.critic_verdict = verdict
            state.investment_score = updated_result.investment_score
            
            print("\n🔥 THE CRITIC'S VERDICT:")
            print(verdict)
            break  
            
        except Exception as e:
            print(f"⚠️ Critic Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                verdict = "Critic analysis unavailable."
                state.critic_verdict = verdict

    # Now 'verdict' is guaranteed to be a string here
    match = re.search(r"FINAL SCOUT SCORE[:\* \s]*(\d+\.?\d*)", verdict)


    # 6. FINAL EXPORT
    export_name = state.company_name if state and state.company_name else "unknown_startup"
    filename = f"{export_name.lower().replace(' ', '_')}_memo.json"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(state.model_dump_json(indent=4))

    print("\n🔗 DATA VERIFICATION SOURCES:")
    if hasattr(state, 'sources') and state.sources:
        for field, url in state.sources.items():
            # Clean up the name (e.g., total_funding -> Total Funding)
            label = field.replace("_", " ").title()
            print(f"  • {label:20}: {url}")
    else:
        print("  • No source links captured.")

    print("\n" + "="*60)    

    # --- 🚀 PROFESSIONAL PORTFOLIO DISPLAY ---
    print("\n" + "="*60)
    print(f"📊 FINAL INVESTMENT DOSSIER: {state.company_name.upper()}")
    print("="*60)

    status = "🏛️ PUBLIC" if state.is_public else "🚀 PRIVATE STARTUP"
    print(f"Status: {status} | Industry: {state.industry}")
    if state.ticker: print(f"Ticker: {state.ticker}")

    print("\n💰 CORE FINANCIALS:")
    if state.is_public:
        print(portfolio_format("Net Profit", state.net_profit))
        print(portfolio_format("Basic EPS", state.eps_basic))
    else:
        print(portfolio_format("Total Funding", state.total_funding))
        print(portfolio_format("Latest Valuation", state.latest_valuation))
        print(portfolio_format("Est. Monthly Burn", state.estimated_monthly_burn))
        print(portfolio_format("Cash Runway", state.runway_months, prefix="", suffix=" Months"))

    print(portfolio_format("Annual Revenue (ARR)", state.annual_revenue))

    print("\n📈 UNIT ECONOMICS:")
    if state.cac > 0:
        print(f"  • CAC: ${state.cac:,.2f} | Payback: {state.payback_period} Months")
    else:
        print("  • Unit Economics: [Metrics Not Publicly Disclosed]")

    print("\n🧐 CRITIC'S FINAL VERDICT:")
    print(f"{state.critic_verdict}")
    print("\n" + "="*60)
    print(f"""
    ============================================================
    📊 FINAL INVESTMENT DOSSIER: {state.company_name}
    ============================================================
    ...
    📈 COMMUNITY VIBE CHECK:
    • Sentiment      : {state.community_sentiment}
    • Vibe Score     : {state.vibe_score}/10
    • Top Complaint   : {state.top_complaint}
    • Social Signal  : {state.reddit_signal}
    ...
    """)

    # --- 🔍 THE FIX: UPDATE STATE IMMEDIATELY ---
    # We look for the "60.0" inside the "verdict" string
    match = re.search(r"FINAL SCOUT SCORE[:\* \s]*(\d+\.?\d*)", verdict)
    if match:
        # This OVERWRITES the Analyst's 70.0 with the Critic's 60.0
        state.investment_score = float(match.group(1)) 
    
    # --- 🚀 NOW CREATE THE VISUALIZER ---
    # Now 'score' will correctly be 60.0
    score = state.investment_score 
    bar_length = 20
    filled_length = int(bar_length * score / 100)
    bar = "█" * filled_length + "-" * (bar_length - filled_length)
    
    print(f"\n🎯 SCOUT INVESTMENT SCORE: [{bar}] {score}/100")
    
    if score >= 80:
        print("💡 RECOMMENDATION: 🚀 STRONGLY CONSIDER / BUY")
    elif score >= 55:
        print("💡 RECOMMENDATION: 🧐 WATCHLIST")
    else:
        print("💡 RECOMMENDATION: ❌ DO NOT BUY / HIGH RISK")
    print(f"🚀 SQUAD MISSION COMPLETE! Full dossier saved to {filename}")


if __name__ == "__main__":
    asyncio.run(run_scout_squad())