from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
import os
import shutil
import uuid
import logging
import gradio as gr
from textextractor import text_extractor
from graph_manager import run_scout_workflow
from app_gui import demo


# Set up a named logger to distinguish system logs from agent logs
logger = logging.getLogger("Scout.Main")
app = FastAPI(title="The Startup Scout API")

# ── PDF DOWNLOAD ROUTE ──
@app.get("/download/{filename}")
async def download_report(filename: str):
    path = f"/tmp/gradio/{filename}"
    if os.path.exists(path):
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=filename
        )
    return {"error": "File not found"}

# --- 🚀 MOUNT GRADIO GUI ---
# Mounts the Gradio Dashboard onto the FastAPI server instance.
# This allows the API and the UI to run on a single port.
app = gr.mount_gradio_app(app, demo, path="/gui")

@app.get("/")
def home():
    """Root endpoint to verify server health."""
    return {"status": "Scout is Online. Visit /gui for the dashboard."}

@app.post("/analyze")
async def analyze_startup(
    file: UploadFile = File(...), 
    mode: str = Form("normal") 
):
    
    """
    Main Entry Point for Startup Analysis.
    1. Generates a unique Job ID to prevent file collisions.
    2. Persists the uploaded PDF to disk temporarily.
    3. Triggers the Agentic RAG Pipeline (LlamaParse -> LangGraph).
    4. Performs cleanup of temporary files post-analysis.
    """

    # 1. Unique Identification: Avoids overwriting if two users upload 'pitch.pdf' simultaneously
    job_id = str(uuid.uuid4())[:8]
    temp_path = f"temp_{job_id}_{file.filename}"
    
    # 2. Binary Buffer: Streams the file from memory to a physical 'wb' (write-binary) file
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        logger.info(f"📁 Processing upload: {file.filename}")
        # 3. Text Extraction Stage: Uses LlamaParse to convert PDF layout into Markdown
        text = await text_extractor(temp_path)
        
        if not text:
            raise HTTPException(status_code=400, detail="PDF extraction failed.")
        # 4. Agent Orchestration: Hands the text to the LangGraph (Summarizer -> Researcher -> Analyst -> Critic)
        result_state = await run_scout_workflow(text, mode)

        # 5. Cleanup: Removes the temporary file to preserve server disk space
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Returns the final Pydantic-validated State object
        return result_state

    except Exception as e:
        # Emergency Cleanup: Ensure the file is deleted even if the AI pipeline crashes
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return {"error": str(e)}