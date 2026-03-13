import asyncio
import logging
import json
import re
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
    summary = await sumarizer(state["raw_deck_text"])
    state["startup"].manager_notes = summary
    return state

async def primary_research_node(state: ScoutState) -> ScoutState:
    retries = state["retry_stats"].get("researcher", 0)
    logger.info(f"Node: Primary Research | Attempt: {retries + 1}")

    if retries > 0:
        await asyncio.sleep(5)

    # 1. Get raw response from researcher
    # We expect researcher_agent to now return a Pydantic object or a clean Dict
    try:
        updated_startup = await researcher_agent(state["startup"].manager_notes)
        
        # 2. If researcher_agent returns a Dict, validate it into our StartupState
        if isinstance(updated_startup, dict):
            state["startup"] = StartupState(**updated_startup)
        else:
            state["startup"] = updated_startup
            
        logger.info(f"✅ Structured Data Validated for {state['startup'].company_name}")
        
    except Exception as e:
        logger.error(f"Structured Parsing Failed: {e}")
        state["retry_stats"]["researcher"] = retries + 1
        
    return state

async def analyst_node(state: ScoutState) -> ScoutState:
    logger.info("Node: Financial Analyst | Processing unit economics...")
    try:
        updated_startup = await analyst_agent(state["startup"])
        
        # Ensure boolean fields are actually booleans to stop the Pydantic warning
        if isinstance(updated_startup.is_public, str):
            updated_startup.is_public = updated_startup.is_public.lower() == 'true'
            
        state["startup"] = updated_startup
        return state
    except Exception as e:
        logger.error(f"Analyst Node Failure: {e}")
        return state

async def critic_node(state: ScoutState) -> ScoutState:
    mode = state["metadata"].get("mode", "normal")
    logger.info(f"Node: Critic | Reviewing in {mode.upper()} mode...")
    
    # Run the agent
    verdict_text = await critic_agent(state["startup"], mode)
    
    # 1. Update the verdict text immediately
    state["startup"].critic_verdict = verdict_text
    
    # 2. Robust Score Extraction (Looking for ANY number associated with score)
    # This searches for "Score: 85", "85/100", or "Score is 85"
    score_match = re.search(r"(?:score[:\s*]*|(\d+)/100)(\d+\.?\d*)", verdict_text, re.IGNORECASE)
    
    if score_match:
        # Extract the numeric group
        extracted_score = float(score_match.group(1) or score_match.group(2))
        state["startup"].investment_score = extracted_score
        logger.info(f"Successfully extracted score: {extracted_score}")
    else:
        # Emergency Fallback: If no score found, don't leave it at 0.0
        # Check if Analyst had a score first
        if state["startup"].investment_score == 0:
            state["startup"].investment_score = 50.0 # Neutral baseline
            logger.warning("No score found in Critic verdict. Setting neutral baseline.")
            
    return state
# --- 🚦 ROUTER ---

def validate_research_quality(state: ScoutState) -> Literal["analyst", "researcher", "__end__"]:
    s = state["startup"]
    retries = state["retry_stats"].get("researcher", 0)

    # Big company validation logic
    if (not s.company_name or s.total_funding == 0) and retries < 2:
        logger.warning("⚠️ Validation Failed: Missing core data. Retrying...")
        state["retry_stats"]["researcher"] = retries + 1
        return "researcher"
    
    if not s.company_name and retries >= 2:
        logger.error("❌ Critical data missing after max retries.")
        return "__end__"

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
    print("🚀 AI-SCOUT 2026 : ENTERPRISE GRAPH ORCHESTRATOR")
    print("═"*60)
    
    # --- RESTORED INPUT LOGIC ---
    print("[1] Normal Standard Due Diligence (Balanced)")
    print("[2] Hard Stress-Test (High-Skepticism)")
    vibe_choice = input("Select Execution Mode: ")
    critic_vibe = "hard" if vibe_choice == "2" else "normal"
    
    print(f"\n📂 Initializing pipeline in {critic_vibe.upper()} mode...")
    
    # Trigger extraction
    deck_text = await text_extractor() 
    
    if not deck_text:
        logger.error("No text extracted. Shutting down.")
        return

    # Pass choice into metadata
    initial_state: ScoutState = {
        "startup": StartupState(company_name="Pending"),
        "raw_deck_text": deck_text,
        "metadata": {"mode": critic_vibe}, 
        "retry_stats": {"researcher": 0},
        "error_log": []
    }

    engine = build_elite_scout_graph()
    
    logger.info("Invoking Graph Engine...")
    final_output = await engine.ainvoke(initial_state)
    
    res = final_output["startup"]
    
    # Final Visual Output
    print("\n" + "═"*60)
    print(f"📊 FINAL INVESTMENT DOSSIER: {res.company_name.upper()}")
    print("═"*60)
    print(f"🎯 SCORE: {res.investment_score}/100")
    print(f"🧐 CRITIC'S SUMMARY: {res.critic_verdict}...")
    print("═"*60 + "\n")

if __name__ == "__main__":
    asyncio.run(main_orchestrator())