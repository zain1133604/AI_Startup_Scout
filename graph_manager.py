import asyncio
import logging
from typing import Dict, Any, TypedDict, Literal, List

from langgraph.graph import StateGraph, END

# Import your core mission modules
from state import StartupState
from textextractor import text_extractor
from summarizer import sumarizer
from searcher import researcher_agent
from analyistagent import analyst_agent
from critic import critic_agent

# --- 🛰️ TELEMETRY CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ScoutOrchestrator")

# --- 🧠 GRAPH STATE DEFINITION ---
class ScoutState(TypedDict):
    startup: StartupState
    raw_deck_text: str 
    metadata: Dict[str, Any]
    retry_stats: Dict[str, int]
    error_log: List[str]

# --- ⚡ NODE IMPLEMENTATIONS ---

async def summarizer_node(state: ScoutState) -> ScoutState:
    logger.info("Node: Summarizer | Analyzing pitch deck...")
    # Extract summary from the raw PDF text
    summary = await sumarizer(state["raw_deck_text"])
    state["startup"].manager_notes = summary
    return state

async def primary_research_node(state: ScoutState) -> ScoutState:
    retries = state["retry_stats"].get("researcher", 0)
    
    # 🌟 THE FIX: Mandatory wait for Gemini Free Tier (30-60s)
    # This prevents the 429 error on the second and third attempts.
    if retries > 0:
        logger.info(f"⏳ Throttling for Quota... Waiting 45s before retry.")
        await asyncio.sleep(45) 
    
    logger.info(f"Node: Primary Research | Attempt: {retries + 1}")
    
    try:
        # Pass the notes to the agent
        state["startup"] = await researcher_agent(state["startup"].manager_notes)
        logger.info(f"✅ Research complete for: {state['startup'].company_name}")
        
    except Exception as e:
        logger.error(f"Researcher Node Failed: {e}")
        # Increment retries so the router knows when to stop
        state["retry_stats"]["researcher"] = retries + 1
        
    return state

async def analyst_node(state: ScoutState) -> ScoutState:
    logger.info("Node: Financial Analyst | Processing unit economics...")
    try:
        # analyst_agent now handles its own internal validation and returns StartupState
        state["startup"] = await analyst_agent(state["startup"])
        return state
    except Exception as e:
        logger.error(f"Analyst Node Failure: {e}")
        return state

async def critic_node(state: ScoutState) -> ScoutState:
    mode = state["metadata"].get("mode", "normal")
    logger.info(f"Node: Critic | Reviewing in {mode.upper()} mode...")
    
    # Capture the analyst's score before the critic starts (optional, for logging)
    analyst_draft_score = state["startup"].investment_score
    logger.info(f"⚖️ Analyst Draft Score: {analyst_draft_score}")

    # Run the critic agent
    # This will update state["startup"].investment_score with the FINAL score
    state["startup"] = await critic_agent(state["startup"], mode)
    
    # Force a final log to confirm the Critic's score is the one being shipped
    logger.info(f"✅ Final Score (Critic Override): {state['startup'].investment_score}")
    
    return state
# --- 🚦 ROUTER ---

def validate_research_quality(state: ScoutState) -> Literal["analyst", "researcher", "__end__"]:
    s = state["startup"]
    retries = state["retry_stats"].get("researcher", 0)

    # 🚨 Core identity check
    if not s.company_name or s.company_name == "Pending":
        if retries < 2:
            return "researcher"
        return "__end__"

    # 🚨 Data quality check (NEW)
    weak_data = (
        s.total_funding == 0 and
        s.annual_revenue == 0 and
        s.headcount == 0
    )

    if weak_data:
        if retries < 2:
            return "researcher"
        return "analyst"  # fallback, don't kill pipeline

    return "analyst"

# --- 🏗️ ARCHITECTURE ---

def build_elite_scout_graph():
    workflow = StateGraph(ScoutState)

    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("researcher", primary_research_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("critic", critic_node)

    workflow.set_entry_point("summarizer")
    workflow.add_edge("summarizer", "researcher")

    workflow.add_conditional_edges(
        "researcher",
        validate_research_quality,
        {
            "researcher": "researcher",
            "analyst": "analyst",
            "__end__": END
        }
    )
    
    workflow.add_edge("analyst", "critic")
    workflow.add_edge("critic", END)

    return workflow.compile()

# --- 🚀 EXECUTION ---

async def main_orchestrator():
    print("\n" + "═"*60)
    print("🚀 THE STARTUP SCOUT v2.0 : GRAPH ORCHESTRATOR")
    print("═"*60)
    
    print("[1] Balanced Due Diligence (Pragmatic)")
    print("[2] Hard Stress-Test (Brutal Skeptic)")
    vibe_choice = input("Select Execution Mode: ")
    critic_vibe = "hard" if vibe_choice == "2" else "normal"

    # file_path = input("Bro, paste the path to your PDF here: ")
    # print("\n🔍 Scout is reading the document... please wait.")
    
    # 1. Extraction Phase
    print("\n📂 Reading Pitch Deck...")
    deck_text = await text_extractor() 
    
    if not deck_text:
        logger.error("Extraction failed. Ensure deck.pdf is in the directory.")
        return

    # 2. State Initialization
    initial_state: ScoutState = {
        "startup": StartupState(company_name="Pending"),
        "raw_deck_text": deck_text,
        "metadata": {"mode": critic_vibe}, 
        "retry_stats": {"researcher": 0},
        "error_log": []
    }

    # 3. Graph Execution
    engine = build_elite_scout_graph()
    logger.info("Initializing Agent Squad...")
    final_output = await engine.ainvoke(initial_state)
    
    res = final_output["startup"]
    
    # 4. Final Result Presentation
    print("\n" + "█"*60)
    print(f"📊 FINAL INVESTMENT DOSSIER: {res.company_name.upper()}")
    print(f"💰 FUNDING: ${res.total_funding:,.0f} | 📈 VALUATION: ${res.latest_valuation:,.0f}")
    print(f"⏳ RUNWAY: {res.runway_months} months | 🔥 SCORE: {res.investment_score}/100")
    print("█"*60)
    print(f"\n🧐 CRITIC VERDICT:\n{res.critic_verdict}")
    print("\n" + "═"*60)

if __name__ == "__main__":
    asyncio.run(main_orchestrator()) 