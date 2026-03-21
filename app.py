import os
import asyncio
import gradio as gr
import nest_asyncio

from graph_manager import (
    ScoutState,
    summarizer_node,
    primary_research_node,
    analyst_node,
    critic_node,
)

from state import StartupState
from textextractor import LlamaParse
from langgraph.graph import StateGraph, END

nest_asyncio.apply()

# ---------------------------------------------------
# CSS
# ---------------------------------------------------

css = """
body{
background:#0b0f14;
}

.gradio-container{
background:#0b0f14 !important;
}

.panel{
background:#111827;
border-radius:12px;
padding:18px;
border:1px solid #1f2937;
}

#terminal textarea{
background:#020617 !important;
color:#00ff9c !important;
font-family:monospace !important;
}

#deploy-btn{
background:linear-gradient(90deg,#16a34a,#22c55e) !important;
border:none !important;
font-weight:600;
}

.header-title{
font-size:28px;
font-weight:700;
color:white;
}

.header-sub{
color:#9ca3af;
}
"""

# ---------------------------------------------------
# CORE PIPELINE
# ---------------------------------------------------

async def run_autonomous_squad(pdf_file, mode, gemini_key):

    if pdf_file is None:
        return "### ❌ STATUS: SOURCE_MISSING", "[ERROR] No PDF uploaded."
    
    if not gemini_key:
        return "### ❌ STATUS: AUTH_REQUIRED", "[ERROR] User Gemini API Key is required."

    log = []
    log.append("[SYSTEM] Initializing pipeline")

    # Injecting keys into Environment
    # Private keys must be set in Hugging Face Settings -> Secrets
    os.environ["GEMINI_API_KEY"] = gemini_key
    os.environ["LLAMA_PARSE_KEY"] = os.getenv("LLAMA_PARSE_KEY", "")
    os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
    os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY", "")

    try:
        file_path = pdf_file.name if hasattr(pdf_file, "name") else pdf_file

        log.append("[EXTRACTOR] Starting LlamaParse with System Secret")

        parser = LlamaParse(
            api_key=os.environ["LLAMA_PARSE_KEY"],
            result_type="markdown",
        )

        documents = await parser.aload_data(file_path)
        raw_text = documents[0].text

        log.append(f"[DATA] Extracted {len(raw_text)} characters")

        # -----------------------
        # BUILD GRAPH
        # -----------------------

        log.append("[SQUAD] Building agent graph")

        workflow = StateGraph(ScoutState)

        workflow.add_node("summarizer", summarizer_node)
        workflow.add_node("researcher", primary_research_node)
        workflow.add_node("analyst", analyst_node)
        workflow.add_node("critic", critic_node)

        workflow.set_entry_point("summarizer")

        workflow.add_edge("summarizer", "researcher")
        workflow.add_edge("researcher", "analyst")
        workflow.add_edge("analyst", "critic")
        workflow.add_edge("critic", END)

        graph = workflow.compile()

        log.append("[SQUAD] Agents analyzing startup")

        initial_state = {
            "startup": StartupState(company_name="IDENTIFYING"),
            "raw_deck_text": raw_text,
            "metadata": {"mode": mode.lower()},
            "retry_stats": {},
            "error_log": [],
        }

        final_state = await graph.ainvoke(initial_state)

        startup = final_state["startup"]

        log.append(f"[SUCCESS] Analysis complete for {startup.company_name}")

        report = f"""
# 📊 Startup Intelligence Report

## {startup.company_name}

{startup.critic_verdict}

---

### Manager Notes

{startup.manager_notes}
"""

        return report, "\n".join(log)

    except Exception as e:
        log.append(f"[CRITICAL] {str(e)}")
        return "### ⚠️ SYSTEM FAILURE", "\n".join(log)


# ---------------------------------------------------
# UI
# ---------------------------------------------------

with gr.Blocks(css=css, theme=gr.themes.Base()) as demo:

    gr.Markdown(
        """
<div class="header-title">🛰️ AI-Scout Command Center</div>
<div class="header-sub">Autonomous Startup Intelligence System</div>
"""
    )

    with gr.Row():

        # LEFT PANEL
        with gr.Column(scale=1):

            with gr.Group(elem_classes="panel"):

                gr.Markdown("### 📂 Configuration")

                gemini_input = gr.Textbox(
                    label="User Gemini API Key",
                    placeholder="Enter your AIza... key",
                    type="password"
                )

                pdf_input = gr.File(
                    label="Upload Pitch Deck",
                    file_types=[".pdf"],
                    file_count="single",
                )

                mode_input = gr.Radio(
                    ["Normal", "Hard"],
                    value="Normal",
                    label="Analysis Mode",
                )

                run_btn = gr.Button(
                    "🚀 Deploy Scout",
                    elem_id="deploy-btn",
                )

        # RIGHT PANEL
        with gr.Column(scale=2):

            with gr.Group(elem_classes="panel"):

                gr.Markdown("### 📊 Analysis Output")

                output_report = gr.Markdown(
                    "Awaiting deployment..."
                )

            with gr.Group(elem_classes="panel"):

                gr.Markdown("### 🖥 System Monitor")

                status_terminal = gr.Textbox(
                    lines=12,
                    interactive=False,
                    elem_id="terminal",
                )

    run_btn.click(
        fn=run_autonomous_squad,
        inputs=[pdf_input, mode_input, gemini_input],
        outputs=[output_report, status_terminal],
    )


# ---------------------------------------------------
# LAUNCH
# ---------------------------------------------------

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860
    )