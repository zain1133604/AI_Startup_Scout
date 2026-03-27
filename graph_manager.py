import asyncio
import logging
import operator
from datetime import datetime
from typing import Dict, Any, TypedDict, Literal, List, Annotated

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
    # 🔥 The Recruiter Magnet: Structured Trace
    trace: Annotated[List[Dict[str, Any]], operator.add]

# --- ⚡ NODE IMPLEMENTATIONS ---

async def summarizer_node(state: ScoutState) -> Dict[str, Any]:
    logger.info("Node: Summarizer | Analyzing pitch deck...")
    summary = await sumarizer(state["raw_deck_text"])
    
    # Update the local object
    startup_obj = state["startup"]
    startup_obj.manager_notes = summary or "" # Fallback to empty string
    
    trace_entry = {
        "node": "summarizer",
        "agent": "Summarizer",
        "action": "Pitch Deck Text Analysis",
        "status": "Success",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }
    # 🔥 ONLY return the keys you changed
    return {"startup": startup_obj, "trace": [trace_entry]}

async def primary_research_node(state: ScoutState) -> Dict[str, Any]:
    retries = state["retry_stats"].get("researcher", 0)
    
    if retries > 0:
        logger.info(f"⏳ Throttling for Quota... Waiting 45s.")
        await asyncio.sleep(45) 
    
    try:
        # Pass the notes to the agent
        updated_startup = await researcher_agent(state["startup"].manager_notes)
        
        trace_entry = {
            "node": "researcher",
            "agent": "Market Researcher",
            "action": f"Web Search (Attempt {retries + 1})",
            "found_company": updated_startup.company_name,
            "status": "Success",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        return {"startup": updated_startup, "trace": [trace_entry]}
        
    except Exception as e:
        logger.error(f"Researcher Node Failed: {e}")
        # Update retry count in state
        new_retries = retries + 1
        trace_entry = {
            "node": "researcher",
            "agent": "Market Researcher",
            "status": "Failed",
            "error": str(e),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        return {"retry_stats": {"researcher": new_retries}, "trace": [trace_entry]}

async def analyst_node(state: ScoutState) -> Dict[str, Any]:
    logger.info("Node: Financial Analyst | Processing unit economics...")
    try:
        # 1. Run agent and get the UPDATED StartupState object
        updated_startup = await analyst_agent(state["startup"])
        
        trace_entry = {
            "node": "analyst",
            "agent": "Financial Analyst",
            "action": "Unit Economics Calculation",
            "status": "Success",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        # 2. Return ONLY the changes. LangGraph merges this for you.
        return {"startup": updated_startup, "trace": [trace_entry]}
        
    except Exception as e:
        logger.error(f"Analyst Node Failure: {e}")
        # Even if it fails, return a trace so the UI shows the error
        trace_entry = {
            "node": "analyst",
            "agent": "Financial Analyst",
            "status": "Failed",
            "error": str(e),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        return {"trace": [trace_entry]}

async def critic_node(state: ScoutState) -> Dict[str, Any]:
    mode = state["metadata"].get("mode", "normal")
    logger.info(f"Node: Critic | Reviewing in {mode.upper()} mode...")
    
    analyst_draft_score = state["startup"].investment_score
    
    # 1. Run agent
    updated_startup = await critic_agent(state["startup"], mode)
    
    logger.info(f"✅ Final Score (Critic Override): {updated_startup.investment_score}")
    
    trace_entry = {
        "node": "critic",
        "agent": "Venture Critic",
        "action": f"Final Scoring ({mode} mode)",
        "draft_score": analyst_draft_score,
        "final_score": updated_startup.investment_score,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }
    
    # 2. Return ONLY the changes
    return {"startup": updated_startup, "trace": [trace_entry]}

# --- 🚦 ROUTER ---
def validate_research_quality(state: ScoutState) -> Literal["analyst", "researcher", "__end__"]:
    """
    Professional Router: Optimizes for the 20-request/day Free Tier limit.
    Prioritizes 'moving forward' over 'perfect data' to prevent quota exhaustion.
    """
    s = state["startup"]
    # Tracking retries is good, but we must be extremely stingy
    retries = state.get("retry_stats", {}).get("researcher", 0)

    # --- LEVEL 1: NAME CHECK ---
    # If we don't even have a name, we can't do anything.
    if not s.company_name or s.company_name in ["Pending", "Unknown", ""]:
        # Only retry if it's the absolute FIRST attempt.
        if retries < 1:
            logger.warning(f"🕵️ Target missing. Attempting one-time recovery...")
            return "researcher"
        
        # If still no name after 1 retry, stop the graph to save remaining quota.
        logger.error("🛑 Unrecoverable: No startup identified. Ending flow.")
        return "__end__"

    # --- LEVEL 2: DATA SUFFICIENCY (Free Tier Logic) ---
    # In the Free Tier, 'Thin Data' is better than 'No Quota'.
    # We check if the research was a total 'blackout'.
    has_basic_metrics = (s.total_funding > 0 or s.annual_revenue > 0 or s.headcount > 0)
    
    if not has_basic_metrics:
        # PROFESSIONAL LOGIC: We only retry if we have ZERO metrics AND ZERO retries.
        # But honestly, for a 20req/day limit, it's safer to just move to Analyst.
        if retries < 1:
            logger.info(f"🛰️ Data for {s.company_name} is minimal. Attempting one deep-dive retry...")
            return "researcher"
        
        # If it's already been retried, or we want to be safe, move to Analyst.
        # The Analyst is smart enough to explain 'why' data might be missing.
        logger.warning(f"⚠️ Moving to Analysis with limited data for {s.company_name}.")
        return "analyst"

    # --- LEVEL 3: SUCCESS PATH ---
    # If we have a name and at least one metric, go straight to Analyst.
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
    initial_state: ScoutState = {
        "startup": StartupState(company_name="Pending"),
        "raw_deck_text": deck_text,
        "metadata": {"mode": mode}, 
        "retry_stats": {"researcher": 0},
        "error_log": [],
        "trace": [] # 👈 Initializing the trace
    }

    engine = build_elite_scout_graph()
    logger.info("🚀 Agent Squad Dispatched via API...")
    
    final_output = await engine.ainvoke(initial_state)
    
    # Return everything so you can see the trace in your API response
    return final_output

if __name__ == "__main__":
    pass