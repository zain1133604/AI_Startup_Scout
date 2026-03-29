import asyncio
import logging
import re
import os
from datetime import datetime
from typing import Dict, Any, TypedDict, Literal, List

from langgraph.graph import StateGraph, END

# Core mission modules
from state import StartupState
from textextractor import text_extractor
from summarizer import sumarizer
from searcher import researcher_agent
from analyistagent import analyst_agent
from critic import critic_agent

# --- TELEMETRY CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ScoutOrchestrator")

# --- GRAPH STATE DEFINITION ---
class ScoutState(TypedDict):
    startup: StartupState
    raw_deck_text: str
    metadata: Dict[str, Any]
    retry_stats: Dict[str, int]
    error_log: List[str]
    trace: List[Dict[str, Any]]  # for keeping node traces

# --- HELPER FUNCTIONS FOR COMPANY EXTRACTION ---
def extract_company_name(summary: str):
    match = re.search(r"COMPANY_NAME:\s*(.+)", summary, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    patterns = [r"Company Name[:\-\s]+(.+)", r"Startup Name[:\-\s]+(.+)"]
    for pattern in patterns:
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    # fallback: first line with reasonable length
    lines = [l.strip() for l in summary.split("\n") if l.strip()]
    for line in lines[:10]:
        if re.match(r"^[A-Z][A-Za-z0-9&\-\s]{2,50}$", line):
            return line
    return None

def smart_extract_from_raw(raw_text: str):
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    bad_keywords = ["pitch deck", "confidential", "series", "seed", "presentation", "overview", "business plan"]
    for line in lines[:15]:
        clean = line.lower()
        if any(bad in clean for bad in bad_keywords): 
            continue
        if len(line) > 60: 
            continue
        if re.match(r"^[A-Z][A-Za-z0-9&\-\s]{2,50}$", line):
            return line
    return None

# --- NODE IMPLEMENTATIONS ---
async def summarizer_node(state: ScoutState) -> ScoutState:
    logger.info("Node: Summarizer | Analyzing pitch deck...")
    summary = await sumarizer(state["raw_deck_text"])
    state["startup"].manager_notes = summary or ""
    
    found_name = extract_company_name(summary)
    if not found_name or found_name.lower() in ["unknown", "pending", ""]:
        found_name = smart_extract_from_raw(state["raw_deck_text"])
    
    bad_names = ["unknown", "pending", "pitch deck", "confidential"]
    state["startup"].company_name = found_name if found_name and found_name.lower() not in bad_names else "Pending"
    
    # Add trace
    state["trace"].append({
        "node": "summarizer",
        "status": "success",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    logger.info(f"🎯 Summarizer set company: {state['startup'].company_name}")
    return state

async def primary_research_node(state: ScoutState) -> ScoutState:
    retries = state["retry_stats"].get("researcher", 0)
    if retries > 0:
        logger.info(f"⏳ Research retry backoff (Attempt {retries + 1})")
        await asyncio.sleep(2)
    
    try:
        state["startup"] = await researcher_agent(state["startup"].manager_notes)
        logger.info(f"✅ Research complete: {state['startup'].company_name}")
    except Exception as e:
        logger.error(f"Researcher failed: {e}")
        state["retry_stats"]["researcher"] = retries + 1
    
    state["trace"].append({
        "node": "researcher",
        "status": "completed",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    return state

async def analyst_node(state: ScoutState) -> ScoutState:
    logger.info("Node: Analyst | Calculating financials...")
    try:
        state["startup"] = await analyst_agent(state["startup"])
    except Exception as e:
        logger.error(f"Analyst failed: {e}")
    state["trace"].append({
        "node": "analyst",
        "status": "completed",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    return state

async def critic_node(state: ScoutState) -> ScoutState:
    mode = state["metadata"].get("mode", "normal")
    logger.info(f"Node: Critic | Mode: {mode.upper()}")
    analyst_score = state["startup"].investment_score
    try:
        state["startup"] = await critic_agent(state["startup"], mode)
    except Exception as e:
        logger.error(f"Critic failed: {e}")
    state["trace"].append({
        "node": "critic",
        "draft_score": analyst_score,
        "final_score": state["startup"].investment_score,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    logger.info(f"✅ Final Score: {state['startup'].investment_score}")
    return state

# --- CONDITIONAL ROUTER ---
def validate_research_quality(state: ScoutState) -> Literal["analyst", "researcher", "__end__"]:
    s = state["startup"]
    retries = state["retry_stats"].get("researcher", 0)
    if (s.company_name == "Pending" or not s.company_name) and retries < 2:
        logger.warning("⚠️ Research incomplete, retrying...")
        return "researcher"
    if s.company_name == "Pending" and retries >= 2:
        logger.error("❌ Max retries reached, ending workflow.")
        return "__end__"
    return "analyst"

# --- BUILD GRAPH ---
def build_elite_scout_graph():
    workflow = StateGraph(ScoutState)

    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("researcher", primary_research_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("critic", critic_node)

    workflow.set_entry_point("summarizer")
    workflow.add_edge("summarizer", "researcher")
    workflow.add_conditional_edges("researcher", validate_research_quality, {
        "researcher": "researcher",
        "analyst": "analyst",
        "__end__": END
    })
    workflow.add_edge("analyst", "critic")
    workflow.add_edge("critic", END)

    return workflow.compile()

# --- EXECUTION ENTRY POINT ---
async def run_scout_workflow(deck_text: str, mode: str = "normal") -> ScoutState:
    initial_state: ScoutState = {
        "startup": StartupState(company_name="Pending"),
        "raw_deck_text": deck_text,
        "metadata": {"mode": mode},
        "retry_stats": {"researcher": 0},
        "error_log": [],
        "trace": []
    }
    engine = build_elite_scout_graph()
    logger.info("🚀 Running Scout Workflow...")
    final_output = await engine.ainvoke(initial_state)
    return final_output

if __name__ == "__main__":
    async def main():
        print("📂 Extracting Pitch Deck...")
        deck_text = await text_extractor()
        if not deck_text:
            logger.error("No deck text found!")
            return
        final_state = await run_scout_workflow(deck_text)
        s = final_state["startup"]
        print(f"🏢 {s.company_name} | Score: {s.investment_score} | Funding: {s.total_funding}")
    asyncio.run(main())