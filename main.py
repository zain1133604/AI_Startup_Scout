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
app = gr.mount_gradio_app(app, demo, path="/gui")

@app.get("/")
def home():
    return {"status": "Scout is Online. Visit /gui for the dashboard."}

@app.post("/analyze")
async def analyze_startup(
    file: UploadFile = File(...), 
    mode: str = Form("normal") 
):
    job_id = str(uuid.uuid4())[:8]
    temp_path = f"temp_{job_id}_{file.filename}"
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        logger.info(f"📁 Processing upload: {file.filename}")
        text = await text_extractor(temp_path)
        
        if not text:
            raise HTTPException(status_code=400, detail="PDF extraction failed.")

        result_state = await run_scout_workflow(text, mode)

        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return result_state

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return {"error": str(e)}