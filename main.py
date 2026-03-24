from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import os
import shutil
import uuid
from textextractor import text_extractor
from graph_manager import run_scout_workflow # Import our new function
import logging

logger  = logging.getLogger("Scout.Main")
app = FastAPI(title="The Startup Scout API")

@app.get("/")
def home():
    return {"status": "Scout is Online"}

@app.post("/analyze")
async def analyze_startup(
    file: UploadFile = File(...), 
    mode: str = Form("normal") # Allows "normal" or "hard" from a dropdown/form
):
    # 1. Create a unique temp file to avoid collisions
    job_id = str(uuid.uuid4())[:8]
    temp_path = f"temp_{job_id}_{file.filename}"
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 2. Extract Text
        logger.info(f"📁 Processing upload: {file.filename}")
        text = await text_extractor(temp_path)
        
        if not text:
            raise HTTPException(status_code=400, detail="PDF extraction failed.")

        # 3. Run the Full LangGraph Workflow
        result_state = await run_scout_workflow(text, mode)

        # 4. Clean up
        os.remove(temp_path)
        
        # 5. Return the result (FastAPI converts Pydantic objects to JSON automatically)
        return result_state

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return {"error": str(e)}