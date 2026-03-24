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

async def run_scout_workflow(deck_text: str, mode: str = "normal"):
    """
    This is the clean entry point for FastAPI. 
    It takes the text and mode, runs the graph, and returns the result.
    """
    # 1. State Initialization
    initial_state: ScoutState = {
        "startup": StartupState(company_name="Pending"),
        "raw_deck_text": deck_text,
        "metadata": {"mode": mode}, 
        "retry_stats": {"researcher": 0},
        "error_log": []
    }

    # 2. Build and Run
    engine = build_elite_scout_graph()
    logger.info("🚀 Agent Squad Dispatched via API...")
    
    final_output = await engine.ainvoke(initial_state)
    return final_output["startup"]

# Keep the 'if __name__ == "__main__":' block ONLY for local testing if you want
if __name__ == "__main__":
    # You can keep your old main_orchestrator logic here if you still want to run it via terminal
    pass