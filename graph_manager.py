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
    # Use operator.add or a custom merger to ensure retries don't reset
    retry_stats: Annotated[Dict[str, int], operator.ior] 
    error_log: Annotated[List[str], operator.add]
    trace: Annotated[List[Dict[str, Any]], operator.add]

# --- ⚡ NODE IMPLEMENTATIONS ---

async def summarizer_node(state: ScoutState) -> Dict[str, Any]:
    logger.info("Node: Summarizer | Analyzing pitch deck...")
    summary = await sumarizer(state["raw_deck_text"])
    
    startup_obj = state["startup"]
    startup_obj.manager_notes = summary or ""
    
    # NEW: Try to extract the name immediately so the Researcher doesn't have to guess
    # Simple logic: Look for "Company Name: [Name]" in the summary
    import re
    name_match = re.search(r"Company Name:\s*([^\n]+)", summary, re.IGNORECASE)
    if name_match:
        startup_obj.company_name = name_match.group(1).strip()
        logger.info(f"🎯 Summarizer identified company: {startup_obj.company_name}")

    trace_entry = {
        "node": "summarizer",
        "agent": "Summarizer",
        "action": "Pitch Deck Text Analysis",
        "status": "Success",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }
    return {"startup": startup_obj, "trace": [trace_entry]}

async def primary_research_node(state: ScoutState) -> Dict[str, Any]:
    # 1. Get current retries
    current_retries = state.get("retry_stats", {}).get("researcher", 0)
    
    if current_retries > 0:
        logger.info(f"⏳ Throttling for Quota... Waiting 45s. (Attempt {current_retries + 1})")
        await asyncio.sleep(45) 
    
    try:
        # Pass the notes to the agent
        updated_startup = await researcher_agent(state["startup"].manager_notes)
        
        # FIX: We MUST increment the counter even on 'Success' (which might be a 'Pending' success)
        # because the router needs to know this attempt is OVER.
        new_stats = {"researcher": current_retries + 1}
        
        trace_entry = {
            "node": "researcher",
            "agent": "Market Researcher",
            "action": f"Web Search (Attempt {current_retries + 1})",
            "found_company": updated_startup.company_name,
            "status": "Completed",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        
        return {
            "startup": updated_startup, 
            "retry_stats": new_stats, # This updates the global counter
            "trace": [trace_entry]
        }
        
    except Exception as e:
        logger.error(f"Researcher Node Crashed: {e}")
        trace_entry = {
            "node": "researcher",
            "agent": "Market Researcher",
            "status": "Crashed",
            "error": str(e),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        return {
            "retry_stats": {"researcher": current_retries + 1}, 
            "trace": [trace_entry]
        }

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

def validate_research_quality(state: ScoutState) -> Literal["analyst", "researcher", "__end__"]:
    s = state["startup"]
    # Look at the actual retry count from state
    retries = state.get("retry_stats", {}).get("researcher", 0)
    
    logger.info(f"Checking Quality... Attempt: {retries}, Company: {s.company_name}")

    # BUG FIX: If we see "API Error" in the notes or name is "Pending", 
    # and we've already tried, STOP FOREVER.
    if s.company_name == "Pending" or "Quota Exhausted" in s.manager_notes:
        if retries >= 1:
            logger.error("🛑 Hard Stop: Quota exhausted and retry limit reached.")
            return "__end__"
        return "researcher"

    # If data is thin but we already retried, move to analyst anyway
    has_metrics = (s.total_funding > 0 or s.annual_revenue > 0)
    if not has_metrics:
        if retries >= 1:
            return "analyst" # Move on with what we have
        return "researcher"

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