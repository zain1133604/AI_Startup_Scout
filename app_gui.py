import gradio as gr
import asyncio
import os

from graph_manager import run_scout_workflow
from textextractor import text_extractor
from report_generator import generate_report


# -------------------------------
# 🚀 CORE BRIDGE FUNCTION
# -------------------------------
async def scout_ui_bridge(pdf_file, mode):
    if not pdf_file:
        return {"error": "No file uploaded"}, [], None

    try:
        # Step 1: Extract text
        text = await text_extractor(pdf_file.name)
        if not text:
            return {"error": "PDF extraction failed"}, [], None

        # Step 2: Run agent pipeline
        result = await run_scout_workflow(text, mode)
        startup_data = result.get("startup", {})

        # Convert Pydantic → dict
        output_dict = (
            startup_data.model_dump()
            if hasattr(startup_data, "model_dump")
            else startup_data
        )

        # Step 3: Generate PDF report
        report_path = f"/tmp/scout_{output_dict.get('company_name','report').replace(' ','_')}.pdf"
        generate_report(startup_data, report_path)

        return output_dict, result.get("trace", []), report_path

    except Exception as e:
        return {"error": str(e)}, [], None


# -------------------------------
# 🎨 UI
# -------------------------------
with gr.Blocks(
    theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
    delete_cache=(60, 3600),
    analytics_enabled=False
) as demo:

    gr.Markdown("# 🛡️ The Startup Scout")
    gr.Markdown("### Autonomous Multi-Agent VC Due Diligence")

    with gr.Row():

        # LEFT PANEL
        with gr.Column(scale=1):
            file_input = gr.File(
                label="Upload Pitch Deck (PDF)",
                file_types=[".pdf"]
            )

            mode_input = gr.Dropdown(
                choices=["normal", "hard"],
                label="Analysis Rigor",
                value="normal"
            )

            run_btn = gr.Button(
                "🚀 Dispatch Scout Squad",
                variant="primary"
            )

            gr.Markdown("""
            **How it works:**
            1. **Summarizer** parses the deck  
            2. **Researcher** hits the live web  
            3. **Analyst** calculates metrics  
            4. **Critic** audits everything  
            """)

        # RIGHT PANEL
        with gr.Column(scale=2):

            with gr.Tabs():
                with gr.TabItem("📊 Final Verdict"):
                    output_json = gr.JSON(label="Detailed Analysis Results")

                with gr.TabItem("🕵️ Execution Trace"):
                    trace_display = gr.JSON(label="Agent Timeline / Logs")

            # ✅ PDF download
            report_file = gr.File(label="📄 Download PDF Report")

    # -------------------------------
    # 🔗 CONNECT BUTTON
    # -------------------------------
    run_btn.click(
        fn=scout_ui_bridge,
        inputs=[file_input, mode_input],
        outputs=[output_json, trace_display, report_file],
        api_name=False  # avoids internal API issues
    )


# -------------------------------
# ▶️ LAUNCH
# -------------------------------
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860))
    )