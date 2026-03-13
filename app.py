import streamlit as st
import pandas as pd
import json
import os
import asyncio
import io
import contextlib
from manager import run_scout_squad 
import sys

# --- CONFIG ---
st.set_page_config(page_title="AI-Scout 2026", layout="wide", page_icon="🛰️")
REGISTRY_PATH = "scout_registry.json"
UPLOAD_DIR = "uploads" 

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- HELPER FUNCTIONS ---
def load_data():
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_to_registry(new_entry):
    registry = load_data()
    # Check if we already have this entry to avoid double-saves
    registry = [item for item in registry if item['file_name'] != new_entry['file_name']]
    registry.append(new_entry)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, indent=4)

def delete_from_registry(file_name):
    registry = load_data()
    registry = [item for item in registry if item['file_name'] != file_name]
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, indent=4)

# --- UI HEADER ---
st.title("🛰️ AI-Scout: Venture Intelligence")
st.write("Monitor agent terminal output directly in the dashboard.")

# --- SIDEBAR: UPLOAD & PROCESS ---
with st.sidebar:
    st.header("📥 Upload Center")
    uploaded_file = st.file_uploader("Drag and drop PDF", type="pdf")
    
    analysis_mode = st.selectbox(
        "⚖️ Analysis Strategy",
        options=["Normal Standard", "Hard Stress-Test"]
    )
    mode_value = 1 if "Normal" in analysis_mode else 2
    
    if st.button("🚀 Process Startup", use_container_width=True):
        if uploaded_file:
            save_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # 1. Setup the Capture Buffer
            output_capture = io.StringIO()
            
            try:
                with st.spinner(f"🕵️ Agents active... Reading terminal stream..."):
                    # 2. REDIRECT: Everything printed in manager.py goes to output_capture
                    with contextlib.redirect_stdout(output_capture):
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        # We call it, knowing it returns nothing
                        loop.run_until_complete(run_scout_squad(save_path, mode_value)) 
                
                # 3. Capture the full text block from the terminal
                full_terminal_output = output_capture.getvalue()
                
                # 4. Save to Registry (Since manager returns nothing, we save the logs as the primary data)
                new_data = {
                    "company": uploaded_file.name.replace(".pdf", "").title(),
                    "logs": full_terminal_output,
                    "mode": analysis_mode,
                    "file_name": uploaded_file.name,
                    "status": "✅ Complete"
                }
                save_to_registry(new_data)
                
                st.success(f"✅ Mission Complete for {uploaded_file.name}!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error during processing: {e}")
        else:
            st.error("Please upload a PDF file first!")

# --- MAIN: THE STREAMING LOGS ---
st.subheader("🏆 Processed Startups")
data = load_data()

if data:
    # We display a simple list of processed files
    df = pd.DataFrame(data)
    st.dataframe(df[["company", "mode", "status"]], use_container_width=True, hide_index=True)

    st.divider()
    
    # Selection for viewing the "Terminal Mirror"
    selected_file = st.selectbox("🔍 Select Startup to View Terminal Dossier", df["company"].tolist())
    
    if selected_file:
        startup_detail = next(item for item in data if item["company"] == selected_file)
        
        col_text, col_del = st.columns([4, 1])
        with col_text:
            st.markdown(f"### 🖥️ Terminal Output: {selected_file}")
        with col_del:
            if st.button("🗑️ Delete Data"):
                delete_from_registry(startup_detail["file_name"])
                st.rerun()

        # THE BIG WOW: Displaying the terminal output in a code box
        # This keeps the formatting (spacing/dashes) exactly like the terminal
        st.code(startup_detail["logs"], language="text")
        
        # Download button for the text dossier
        st.download_button(
            label="📂 Download Full Terminal Report",
            data=startup_detail["logs"],
            file_name=f"{selected_file}_dossier.txt",
            mime="text/plain"
        )
else:
    st.info("No startups analyzed yet. Use the sidebar to upload your first deck!")