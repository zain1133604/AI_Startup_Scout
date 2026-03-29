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

# Expanded reject list — add any company names you keep seeing incorrectly grabbed
REJECT_NAMES = {
    "unknown", "pending", "pitch deck", "confidential", "presentation",
    "overview", "business plan", "series", "seed", "inc", "llc", "ltd",
    "klickly", "introduction", "agenda", "appendix", "summary", "table",
    "contents", "disclaimer", "proprietary", "investors", "investment"
}

def extract_company_name(summary: str):
    # Step 1: Trust the explicit COMPANY_NAME tag first (most reliable)
    match = re.search(r"COMPANY_NAME:\s*(.+)", summary, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        if name.lower() not in REJECT_NAMES and len(name) > 2:
            return name

    # Step 2: Try pattern-based extraction
    patterns = [
        r"Company Name[:\-\s]+(.+)",
        r"Startup Name[:\-\s]+(.+)",
        r"Company[:\-\s]+([A-Z][A-Za-z0-9&\-\s]{2,50})",
    ]
    for pattern in patterns:
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name.lower() not in REJECT_NAMES and len(name) > 2:
                return name

    # Step 3: Fallback — scan first 10 non-empty lines of summary
    lines = [l.strip() for l in summary.split("\n") if l.strip()]
    for line in lines[:10]:
        # Must start with capital, reasonable length, not in reject list
        if (re.match(r"^[A-Z][A-Za-z0-9&\-\s]{2,50}$", line)
                and line.lower() not in REJECT_NAMES
                and not line.startswith("**")   # skip markdown bold headers
                and len(line.split()) <= 5):     # company names are rarely 6+ words
            return line

    return None


async def summarizer_node(state: ScoutState) -> ScoutState:
    logger.info("Node: Summarizer | Analyzing pitch deck...")

    # Focus on cover page (first 3000 chars) + team slide (last 1000 chars)
    # This prevents client/case-study names from polluting the summary
    raw = state["raw_deck_text"]
    focused_text = raw[:3000] + "\n...[middle omitted]...\n" + raw[-1000:]

    summary = await sumarizer(focused_text)
    state["startup"].manager_notes = summary or ""

    # Try extracting from summary first
    found_name = extract_company_name(summary)

    # If summary failed, fall back to raw cover page text only (first 1500 chars)
    if not found_name or found_name.lower() in REJECT_NAMES:
        logger.warning("⚠️ Summary extraction failed, falling back to raw cover text...")
        found_name = smart_extract_from_raw(raw[:1500])  # cover page only

    # Final validation
    if found_name and found_name.lower() not in REJECT_NAMES:
        state["startup"].company_name = found_name
    else:
        logger.error("❌ Could not determine company name. Setting to Pending.")
        state["startup"].company_name = "Pending"

    # Add trace
    state["trace"].append({
        "node": "summarizer",
        "status": "success" if state["startup"].company_name != "Pending" else "name_extraction_failed",
        "company_found": state["startup"].company_name,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })

    logger.info(f"🎯 Summarizer set company: {state['startup'].company_name}")
    return state

async def primary_research_node(state: ScoutState) -> ScoutState:
    retries = state["retry_stats"].get("researcher", 0)
    if retries > 0:
        await asyncio.sleep(2)

    # Save the confirmed name BEFORE researcher overwrites it
    confirmed_name = state["startup"].company_name

    try:
        result = await researcher_agent(
            state["startup"].manager_notes,
            confirmed_company_name=confirmed_name  # lock the name
        )
        # Only accept researcher's name if ours is still Pending
        if confirmed_name and confirmed_name != "Pending":
            result.company_name = confirmed_name  # restore confirmed name
        state["startup"] = result
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