import gradio as gr
import asyncio
from graph_manager import run_scout_workflow
import os
from PyPDF2 import PdfReader

async def scout_ui_bridge(pdf_file, mode):
    if not pdf_file:
        return {"error": "No file uploaded"}, []

    # 1. Extract Text from PDF (Properly)
    try:
        # Use the name attribute to get the file path
        reader = PdfReader(pdf_file.name)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        return {"error": f"Failed to read PDF: {str(e)}"}, []

    # 2. Run the LangGraph Workflow
    try:
        result = await run_scout_workflow(text, mode)
        
        # 3. Format output for Gradio
        startup_data = result.get("startup", {})
        execution_trace = result.get("trace", [])
        
        return startup_data, execution_trace
    except Exception as e:
        return {"error": f"Workflow failed: {str(e)}"}, []

# --- 🎨 THE UI DESIGN ---
# Added api_open=False to stop the 500 error during FastAPI mounting
with gr.Blocks(
    theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"), 
    delete_cache=(60, 3600),
    analytics_enabled=False
) as demo:
    gr.Markdown("# 🛡️ The Startup Scout")
    gr.Markdown("### Autonomous Multi-Agent VC Due Diligence")
    
    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(label="Upload Pitch Deck (PDF)", file_types=[".pdf"])
            mode_input = gr.Dropdown(choices=["normal", "hard"], label="Analysis Rigor", value="normal")
            run_btn = gr.Button("🚀 Dispatch Scout Squad", variant="primary")
            
            gr.Markdown("""
            **How it works:**
            1. **Summarizer** parses the deck.
            2. **Researcher** hits the live web via Tavily.
            3. **Analyst** calculates burn and valuation.
            4. **Critic** looks for red flags.
            """)
            
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.TabItem("📊 Final Verdict"):
                    output_json = gr.JSON(label="Detailed Analysis Results")
                with gr.TabItem("🕵️ Execution Trace"):
                    trace_display = gr.JSON(label="Agent Timeline / Logs")

    # Connect the button to the function
    run_btn.click(
        fn=scout_ui_bridge,
        inputs=[file_input, mode_input],
        outputs=[output_json, trace_display],
        api_name=False # CRITICAL: Disables internal API route that causes the 500 error
    )

if __name__ == "__main__":
    # For local testing
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))