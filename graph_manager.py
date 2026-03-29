import asyncio
import logging
import operator
from datetime import datetime
from typing import Dict, Any, TypedDict, Literal, List, Annotated
import re
import os
import asyncio
from google import genai
from langgraph.graph import StateGraph, END

# --- Your core mission modules ---
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
    retry_stats: Annotated[Dict[str, int], operator.ior] 
    error_log: Annotated[List[str], operator.add]
    trace: Annotated[List[Dict[str, Any]], operator.add]

# --- 🧠 SMART COMPANY NAME EXTRACTION ---
def extract_company_name(summary: str):
    match = re.search(r"COMPANY_NAME:\s*(.+)", summary, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    patterns = [r"Company Name[:\-\s]+(.+)", r"Startup Name[:\-\s]+(.+)"]
    for pattern in patterns:
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    lines = [l.strip() for l in summary.split("\n") if l.strip()]
    for line in lines[:10]:
        if re.match(r"^[A-Z][A-Za-z0-9&\-\s]{2,50}$", line):
            return line

    return None

def smart_extract_from_raw(raw_text: str):
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    bad_keywords = ["pitch deck", "confidential", "series", "seed", "presentation", "overview", "business plan"]
    candidates = []
    for line in lines[:15]:
        clean = line.lower()
        if any(bad in clean for bad in bad_keywords): continue
        if len(line) > 60: continue
        if re.match(r"^[A-Z][A-Za-z0-9&\-\s]{2,50}$", line):
            candidates.append(line)
    return candidates[0] if candidates else None

# --- NODE: COMPANY LOCK ---


async def company_lock_node(state: ScoutState) -> ScoutState:
    client = genai.Client(api_key=os.environ.get("GEMINI_KEY"))
    prompt = f"Based on the manager notes:\n{state['startup'].manager_notes}\nReturn ONLY the company name."

    # Wrap the sync call in a thread so we can 'await' it safely
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    )

    state["startup"].company_name = response.text.strip() or "UNKNOWN"
    return state

# --- NODE: SUMMARIZER ---
async def summarizer_node(state: ScoutState) -> Dict[str, Any]:
    logger.info("Node: Summarizer | Analyzing pitch deck...")
    summary = await sumarizer(state["raw_deck_text"])
    startup_obj = state["startup"]
    startup_obj.manager_notes = summary or ""

    found_name = extract_company_name(summary)
    if not found_name or found_name.lower() in ["unknown", "pending", ""]:
        found_name = smart_extract_from_raw(state["raw_deck_text"])

    bad_names = ["unknown", "pending", "pitch deck", "confidential"]
    if found_name and found_name.lower() not in bad_names:
        startup_obj.company_name = found_name
        logger.info(f"🎯 Summarizer identified company: {found_name}")
    else:
        startup_obj.company_name = "Pending"
        logger.warning(f"⚠️ Summarizer could not find a valid company name. Using fallback: Pending")

    trace_entry = {
        "node": "summarizer",
        "agent": "Summarizer",
        "action": "Pitch Deck Text Analysis",
        "status": "Success",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }

    return {"startup": startup_obj, "trace": [trace_entry]}

# --- NODE: RESEARCHER ---
async def primary_research_node(state: ScoutState) -> Dict[str, Any]:
    current_retries = state.get("retry_stats", {}).get("researcher", 0)
    if current_retries > 0:
        logger.info(f"⏳ Throttling for Quota... Waiting 45s. (Attempt {current_retries + 1})")
        await asyncio.sleep(45)

    try:
        updated_startup = await researcher_agent(state["startup"].manager_notes)
        new_stats = {**state.get("retry_stats", {}), "researcher": current_retries + 1}
        trace_entry = {
            "node": "researcher",
            "agent": "Market Researcher",
            "action": f"Web Search (Attempt {current_retries + 1})",
            "found_company": updated_startup.company_name,
            "status": "Completed",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        return {"startup": updated_startup, "retry_stats": new_stats, "trace": [trace_entry]}
    except Exception as e:
        logger.error(f"Researcher Node Crashed: {e}")
        trace_entry = {
            "node": "researcher",
            "agent": "Market Researcher",
            "status": "Crashed",
            "error": str(e),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        new_stats = {**state.get("retry_stats", {}), "researcher": current_retries + 1}
        return {"retry_stats": new_stats, "trace": [trace_entry]}

# --- NODE: ANALYST ---
async def analyst_node(state: ScoutState) -> Dict[str, Any]:
    logger.info("Node: Financial Analyst | Processing unit economics...")
    try:
        updated_startup = await analyst_agent(state["startup"])
        trace_entry = {
            "node": "analyst",
            "agent": "Financial Analyst",
            "action": "Unit Economics Calculation",
            "status": "Success",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        return {"startup": updated_startup, "trace": [trace_entry]}
    except Exception as e:
        logger.error(f"Analyst Node Failure: {e}")
        trace_entry = {
            "node": "analyst",
            "agent": "Financial Analyst",
            "status": "Failed",
            "error": str(e),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        return {"trace": [trace_entry]}

# --- NODE: CRITIC ---
async def critic_node(state: ScoutState) -> Dict[str, Any]:
    mode = state["metadata"].get("mode", "normal")
    logger.info(f"Node: Critic | Reviewing in {mode.upper()} mode...")
    analyst_draft_score = state["startup"].investment_score
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
    return {"startup": updated_startup, "trace": [trace_entry]}

# --- QUALITY CHECK ---
def validate_research_quality(state: ScoutState) -> Literal["analyst", "researcher", "__end__"]:
    s = state["startup"]
    retries = state.get("retry_stats", {}).get("researcher", 0)
    logger.info(f"Checking Quality... Attempt: {retries}, Company: {s.company_name}")

    if s.company_name == "Pending" or "Quota Exhausted" in s.manager_notes:
        if retries >= 1:
            logger.error("🛑 Hard Stop: Quota exhausted and retry limit reached.")
            return "__end__"
        return "researcher"

    has_metrics = (s.total_funding > 0 or s.annual_revenue > 0)
    if not has_metrics:
        if retries >= 1:
            return "analyst"
        return "researcher"

    return "analyst"

# --- BUILD GRAPH ---
def build_elite_scout_graph():
    workflow = StateGraph(ScoutState)

    workflow.add_node("company_lock", company_lock_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("researcher", primary_research_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("critic", critic_node)

    workflow.set_entry_point("company_lock")
    workflow.add_edge("company_lock", "summarizer")
    workflow.add_edge("summarizer", "researcher")

    workflow.add_conditional_edges(
        "researcher",
        validate_research_quality,
        {"researcher": "researcher", "analyst": "analyst", "__end__": END}
    )

    workflow.add_edge("analyst", "critic")
    workflow.add_edge("critic", END)

    return workflow.compile()

# --- RUN WORKFLOW ---
async def run_scout_workflow(deck_text: str, mode: str = "normal"):
    initial_state: ScoutState = {
        "startup": StartupState(company_name="Pending"),
        "raw_deck_text": deck_text,
        "metadata": {"mode": mode}, 
        "retry_stats": {"researcher": 0},
        "error_log": [],
        "trace": []
    }

    engine = build_elite_scout_graph()
    logger.info("🚀 Agent Squad Dispatched via API...")
    final_output = await engine.ainvoke(initial_state)
    return final_output

if __name__ == "__main__":
    pass