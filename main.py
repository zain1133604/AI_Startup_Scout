from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import os
import shutil
import uuid
import logging
import gradio as gr # <--- Add this
from textextractor import text_extractor
from graph_manager import run_scout_workflow
from app_gui import demo # <--- Add this (make sure app_gui.py is in the same folder)

logger = logging.getLogger("Scout.Main")
app = FastAPI(title="The Startup Scout API")

# --- 🚀 MOUNT GRADIO GUI ---
# This makes the GUI available at your-url.app/gui
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