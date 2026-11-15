import os
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="Health Prediction App", page_icon="🩺")
st.title("Health Prediction Application")
st.caption("Phase 1 foundation — patient data is managed by the FastAPI backend.")

if st.button("Check backend connection", type="primary"):
    try:
        response = httpx.get(f"{BACKEND_API_URL}/api/health", timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as error:
        st.error(f"Could not reach the backend at {BACKEND_API_URL}: {error}")
    else:
        st.success(f"Backend is healthy: {response.json().get('status', 'unknown')}")

st.subheader("Patients")
try:
    response = httpx.get(f"{BACKEND_API_URL}/api/patients", timeout=5.0)
    response.raise_for_status()
except httpx.HTTPError as error:
    st.info("Start the backend to load patient records.")
    st.caption(str(error))
else:
    patients = response.json()
    if patients:
        st.dataframe(patients, use_container_width=True, hide_index=True)
    else:
        st.info("No patient records yet.")
