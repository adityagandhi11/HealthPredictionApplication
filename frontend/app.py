from datetime import date
import os
from pathlib import Path
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(
    page_title="Health Prediction System",
    page_icon="✚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --ink:#132a35; --muted:#71838b; --teal:#137c75; --mint:#e8f5f1; --line:#e4ece9; }
    .stApp { background:#f5f8f7; color:var(--ink); font-family:'Aptos','Segoe UI',sans-serif; }
    [data-testid="stSidebar"] { background:#102a35; border-right:0; }
    [data-testid="stSidebar"] * { color:#e7f2ef; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding:7px 10px; border-radius:9px; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover { background:#1b3c46; }
    .block-container { max-width:1420px; padding-top:2rem; padding-bottom:3rem; }
    h1,h2,h3 { color:#142f3a; font-family:'Aptos Display','Segoe UI',sans-serif; letter-spacing:-.035em; }
    h1 { font-weight:800; }
    h2,h3 { font-weight:700; }
    [data-testid="stMetric"] { background:white; border:1px solid var(--line); padding:18px 20px; border-radius:14px; box-shadow:0 3px 14px #173a3510; }
    [data-testid="stMetricLabel"] p { color:var(--muted); font-weight:600; }
    [data-testid="stMetricValue"] { color:var(--ink); font-family:'Aptos Display','Segoe UI',sans-serif; font-weight:800; }
    div.stButton > button, div.stFormSubmitButton > button { border-radius:9px; font-weight:650; min-height:42px; }
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] { background:#137c75; border-color:#137c75; }
    div[data-testid="stForm"] { background:white; border:1px solid var(--line); padding:20px; border-radius:14px; }
    [data-testid="stExpander"] { background:white; border:1px solid var(--line); border-radius:12px; }
    .hero { background:linear-gradient(115deg,#113a43,#176c68 60%,#39a18e); border-radius:20px; padding:32px 36px; color:white; margin-bottom:22px; box-shadow:0 14px 35px #12645c20; }
    .hero h1 { color:white; margin:4px 0 8px; font-size:2rem; }
    .hero p { color:#d5eeea; margin:0; max-width:680px; }
    .eyebrow { font-size:.72rem; text-transform:uppercase; letter-spacing:.13em; font-weight:700; color:#b5e3d9; }
    .section-note { color:#71838b; margin-top:-10px; margin-bottom:20px; }
    .status-pill { display:inline-block; padding:4px 10px; border-radius:20px; font-size:.78rem; font-weight:700; background:#edf2f2; color:#52646b; }
    .status-generated { background:#e5f5ec; color:#21734d; }
    .status-failed { background:#fff0eb; color:#a64e32; }
    .status-pending { background:#fff5da; color:#8b6817; }
    .disclaimer { background:#eef5f2; border-left:3px solid #318c79; padding:12px 15px; border-radius:5px 10px 10px 5px; color:#46615c; font-size:.88rem; }
    .sidebar-brand { font-family:'Aptos Display','Segoe UI',sans-serif; font-size:1.04rem; font-weight:800; color:white; padding:8px 0 0; }
    .sidebar-sub { color:#9cb7b8 !important; font-size:.78rem; margin-top:1px; }
    </style>
    """,
    unsafe_allow_html=True,
)


class BackendError(Exception):
    """A readable error returned by or encountered while calling the API."""


def _format_error_detail(detail: Any) -> str:
    if isinstance(detail, list):
        messages = []
        for item in detail:
            if isinstance(item, dict):
                field = str(item.get("field") or ".".join(map(str, item.get("loc", []))) or "Input")
                message = str(item.get("message") or item.get("msg") or "is invalid")
                messages.append(f"{field.replace('_', ' ').capitalize()}: {message}")
        return "  \n".join(messages) or "The submitted information is invalid."
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or "The request could not be completed.")
    return str(detail or "The request could not be completed.")


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        response = httpx.request(
            method,
            f"{BACKEND_API_URL}{path}",
            timeout=20.0,
            **kwargs,
        )
    except httpx.TimeoutException as error:
        raise BackendError("The backend did not respond in time. Check that it is running.") from error
    except httpx.HTTPError as error:
        raise BackendError(
            f"Could not connect to the backend at {BACKEND_API_URL}. Start FastAPI and try again."
        ) from error

    if not response.is_success:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise BackendError(_format_error_detail(detail) or f"Request failed ({response.status_code}).")
    if response.status_code == 204:
        return None
    try:
        return response.json()
    except ValueError as error:
        raise BackendError("The backend returned an unreadable response.") from error


def load_patients() -> list[dict[str, Any]]:
    result = api_request("GET", "/api/patients")
    if not isinstance(result, list):
        raise BackendError("The backend returned an unexpected patient list.")
    return result


def show_flash_message() -> None:
    message = st.session_state.pop("flash_message", None)
    if message:
        kind, text = message
        getattr(st, kind)(text)


def flash_and_rerun(kind: str, message: str) -> None:
    st.session_state["flash_message"] = (kind, message)
    st.rerun()


def navigate_to(page_name: str) -> None:
    st.session_state["active_page"] = page_name


def format_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d/%m/%Y")
    except ValueError:
        return value


def patient_payload(
    full_name: str,
    date_of_birth: date,
    email: str,
    glucose: float | None,
    haemoglobin: float | None,
    cholesterol: float | None,
) -> dict[str, Any]:
    return {
        "full_name": full_name,
        "date_of_birth": date_of_birth.strftime("%d/%m/%Y"),
        "email": email,
        "glucose": glucose,
        "haemoglobin": haemoglobin,
        "cholesterol": cholesterol,
    }


def status_label(value: str) -> str:
    labels = {
        "generated": "AI remarks ready",
        "failed": "AI needs retry",
        "pending": "AI pending",
    }
    return labels.get(value, "AI pending")


with st.sidebar:
    st.markdown('<div class="sidebar-brand">✚ Healthwise</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">PATIENT CARE WORKSPACE</div>', unsafe_allow_html=True)
    st.divider()
    page = st.radio(
        "WORKSPACE",
        ["Overview", "Patient records", "Add patient", "Assessment data"],
        label_visibility="visible",
        key="active_page",
    )
    st.divider()
    st.caption("Local development build")
    st.caption("FastAPI  ·  SQLite  ·  Groq")

show_flash_message()

if page == "Overview":
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">PATIENT MANAGEMENT · OVERVIEW</div>
          <h1>Health Prediction System</h1>
          <p>A considered workspace for patient records and AI-assisted lab-result notes.
          Keep clinical decisions with qualified healthcare professionals.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        patients = load_patients()
        backend_available = True
    except BackendError as error:
        patients = []
        backend_available = False
        st.error(str(error))

    total = len(patients)
    ready = sum(patient.get("ai_status") == "generated" for patient in patients)
    pending = sum(patient.get("ai_status") == "pending" for patient in patients)
    failed = sum(patient.get("ai_status") == "failed" for patient in patients)
    first, second, third, fourth = st.columns(4)
    first.metric("Patient records", total, help="Records saved in the SQLite database")
    second.metric("AI remarks ready", ready)
    third.metric("Awaiting setup", pending)
    fourth.metric("Needs retry", failed)

    st.write("")
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.subheader("Workspace")
        st.markdown(
            '<p class="section-note">A quick route to the most common tasks.</p>',
            unsafe_allow_html=True,
        )
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            st.info("**Register a patient**  \nAdd contact details and laboratory measurements.")
            st.button(
                "＋  Add a patient",
                type="primary",
                width="stretch",
                on_click=navigate_to,
                args=("Add patient",),
            )
        with action_col2:
            st.info("**Review patient records**  \nSearch, inspect, edit, or remove saved records.")
            st.button(
                "View patient records",
                width="stretch",
                on_click=navigate_to,
                args=("Patient records",),
            )
    with right:
        st.subheader("Service status")
        if backend_available:
            st.success("FastAPI backend is connected")
        st.markdown(
            f"""
            <div class="disclaimer">
              AI remarks: <strong>{ready} ready · {pending} pending · {failed} failed</strong><br>
              Pending or failed analyses do not prevent patient records from being saved.
              Configure the Groq key on the backend to generate remarks.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.subheader("Recent patients")
    if not patients:
        st.info("No patient records yet. Add a patient to get started.")
    else:
        recent = sorted(patients, key=lambda item: item["id"], reverse=True)[:5]
        st.dataframe(
            [
                {
                    "ID": item["id"],
                    "Patient": item["full_name"],
                    "Date of birth": format_date(item["date_of_birth"]),
                    "Email": item["email"],
                    "AI status": status_label(item.get("ai_status", "pending")),
                }
                for item in recent
            ],
            hide_index=True,
            width="stretch",
        )

elif page == "Add patient":
    st.title("Register a patient")
    st.markdown(
        '<p class="section-note">Enter patient details and available laboratory results. '
        "Missing measurements can be left blank.</p>",
        unsafe_allow_html=True,
    )
    with st.form("create_patient_form", clear_on_submit=True):
        name_col, dob_col, email_col = st.columns(3)
        with name_col:
            full_name = st.text_input("Full name *", placeholder="e.g. Alex Morgan")
        with dob_col:
            dob = st.date_input("Date of birth *", value=date(2025, 1, 1), max_value=date.today())
        with email_col:
            email = st.text_input("Email address *", placeholder="name@example.com")
        st.markdown("#### Laboratory measurements")
        glucose_col, haemoglobin_col, cholesterol_col = st.columns(3)
        with glucose_col:
            glucose = st.number_input(
                "Glucose", min_value=0.0, max_value=800.0, value=None, step=0.1, format="%.4f",
                placeholder="Not provided",
            )
        with haemoglobin_col:
            haemoglobin = st.number_input(
                "Haemoglobin", min_value=0.0, max_value=25.0, value=None, step=0.1, format="%.4f",
                placeholder="Not provided",
            )
        with cholesterol_col:
            cholesterol = st.number_input(
                "Cholesterol", min_value=0.0, max_value=800.0, value=None, step=0.1, format="%.4f",
                placeholder="Not provided",
            )
        st.caption("No units or clinical reference ranges are assumed by this application.")
        submitted = st.form_submit_button("Save patient & generate remarks", type="primary")

    if submitted:
        if not full_name.strip() or not email.strip():
            st.error("Full name and email address are required.")
        else:
            try:
                created = api_request(
                    "POST",
                    "/api/patients",
                    json=patient_payload(
                        full_name, dob, email, glucose, haemoglobin, cholesterol
                    ),
                )
            except BackendError as error:
                st.error(str(error))
            else:
                st.success(f"Patient record #{created['id']} saved successfully.")
                if created.get("ai_status") == "generated":
                    st.markdown("#### AI-generated remarks")
                    st.text(created.get("remarks") or "")
                else:
                    st.warning(
                        "The patient record was saved, but AI remarks were not generated. "
                        f"Status: {status_label(created.get('ai_status', 'pending'))}. "
                        "Check the AI configuration or retry from Patient records."
                    )

    st.markdown(
        '<div class="disclaimer">AI-generated remarks are informational only, '
        "may be incomplete, and are not a medical diagnosis or a substitute "
        "for professional medical advice.</div>",
        unsafe_allow_html=True,
    )

elif page == "Patient records":
    st.title("Patient records")
    st.markdown(
        '<p class="section-note">Records are loaded directly from the application database.</p>',
        unsafe_allow_html=True,
    )
    toolbar_col, refresh_col = st.columns([5, 1])
    with toolbar_col:
        search = st.text_input(
            "Search patients",
            placeholder="Search by name or email",
            label_visibility="collapsed",
        ).strip().casefold()
    with refresh_col:
        if st.button("↻  Refresh", width="stretch"):
            st.rerun()

    try:
        patients = load_patients()
    except BackendError as error:
        st.error(str(error))
        patients = []

    filtered = [
        item for item in patients
        if not search
        or search in item["full_name"].casefold()
        or search in item["email"].casefold()
    ]
    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
    metrics_col1.metric("All records", len(patients))
    metrics_col2.metric("Search results", len(filtered))
    metrics_col3.metric(
        "AI remarks ready",
        sum(item.get("ai_status") == "generated" for item in patients),
    )
    if not filtered:
        st.info(
            "No matching patients. Clear your search or add a new patient."
            if patients else "No patient records yet. Use Add patient to create the first record."
        )
    else:
        table_rows = []
        for item in filtered:
            remark = item.get("remarks") or ""
            table_rows.append(
                {
                    "ID": item["id"],
                    "Full name": item["full_name"],
                    "Date of birth": format_date(item["date_of_birth"]),
                    "Email": item["email"],
                    "Glucose": item.get("glucose"),
                    "Haemoglobin": item.get("haemoglobin"),
                    "Cholesterol": item.get("cholesterol"),
                    "AI remarks": (remark[:90] + "…") if len(remark) > 90 else remark or "—",
                }
            )
        st.dataframe(table_rows, hide_index=True, width="stretch")
        st.caption("Open a record below to view complete remarks and available actions.")

        for item in filtered:
            patient_id = item["id"]
            status = item.get("ai_status", "pending")
            label = (
                f"#{patient_id}  ·  {item['full_name']}  ·  "
                f"{item['email']}  ·  {status_label(status)}"
            )
            with st.expander(label):
                details_left, details_right = st.columns(2)
                with details_left:
                    st.write(f"**Date of birth:** {format_date(item['date_of_birth'])}")
                    st.write(f"**Email:** {item['email']}")
                    st.write(f"**Created:** {format_date(item['created_at'][:10])}")
                with details_right:
                    st.write(f"**Glucose:** {item.get('glucose') if item.get('glucose') is not None else 'Not provided'}")
                    st.write(f"**Haemoglobin:** {item.get('haemoglobin') if item.get('haemoglobin') is not None else 'Not provided'}")
                    st.write(f"**Cholesterol:** {item.get('cholesterol') if item.get('cholesterol') is not None else 'Not provided'}")
                st.markdown(f'<span class="status-pill status-{status}">{status_label(status)}</span>', unsafe_allow_html=True)
                st.markdown("**AI-generated remarks**")
                if item.get("remarks"):
                    st.text(item["remarks"])
                elif status == "pending":
                    st.info("Remarks are pending. Configure Groq on the backend or retry below.")
                else:
                    st.warning("No AI remarks are available for this record yet.")

                edit_col, retry_col, delete_col = st.columns([1, 1, 1])
                with edit_col:
                    if st.button("Edit patient", key=f"edit_{patient_id}"):
                        current = st.session_state.get("edit_patient_id")
                        st.session_state["edit_patient_id"] = (
                            None if current == patient_id else patient_id
                        )
                        st.rerun()
                with retry_col:
                    if status != "generated" and st.button(
                        "Retry AI remarks", key=f"retry_{patient_id}"
                    ):
                        try:
                            api_request("POST", f"/api/patients/{patient_id}/remarks")
                        except BackendError as error:
                            st.error(str(error))
                        else:
                            flash_and_rerun("success", "AI remarks generated and saved.")
                with delete_col:
                    if st.button("Delete patient", key=f"delete_{patient_id}"):
                        st.session_state["confirm_delete_id"] = patient_id
                        st.rerun()

                if st.session_state.get("confirm_delete_id") == patient_id:
                    st.warning(f"Delete {item['full_name']}'s record? This cannot be undone.")
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button("Confirm delete", key=f"confirm_delete_{patient_id}", type="primary"):
                            try:
                                api_request("DELETE", f"/api/patients/{patient_id}")
                            except BackendError as error:
                                st.error(str(error))
                            else:
                                st.session_state["confirm_delete_id"] = None
                                st.session_state["edit_patient_id"] = None
                                flash_and_rerun("success", "Patient record deleted.")
                    with cancel_col:
                        if st.button("Cancel", key=f"cancel_delete_{patient_id}"):
                            st.session_state["confirm_delete_id"] = None
                            st.rerun()

                if st.session_state.get("edit_patient_id") == patient_id:
                    st.markdown("---")
                    st.markdown("#### Edit patient")
                    with st.form(f"edit_patient_form_{patient_id}"):
                        edit_name = st.text_input("Full name", value=item["full_name"])
                        edit_dob = st.date_input(
                            "Date of birth",
                            value=date.fromisoformat(item["date_of_birth"]),
                            max_value=date.today(),
                            key=f"edit_dob_{patient_id}",
                        )
                        edit_email = st.text_input("Email address", value=item["email"])
                        edit_glucose = st.number_input(
                            "Glucose", min_value=0.0,
                            value=float(item["glucose"]) if item["glucose"] is not None else None,
                            step=0.1, format="%.4f", key=f"edit_glucose_{patient_id}",
                        )
                        edit_haemoglobin = st.number_input(
                            "Haemoglobin", min_value=0.0,
                            value=float(item["haemoglobin"]) if item["haemoglobin"] is not None else None,
                            step=0.1, format="%.4f", key=f"edit_haemoglobin_{patient_id}",
                        )
                        edit_cholesterol = st.number_input(
                            "Cholesterol", min_value=0.0,
                            value=float(item["cholesterol"]) if item["cholesterol"] is not None else None,
                            step=0.1, format="%.4f", key=f"edit_cholesterol_{patient_id}",
                        )
                        save_edit = st.form_submit_button("Save changes", type="primary")
                    if save_edit:
                        if not edit_name.strip() or not edit_email.strip():
                            st.error("Full name and email address are required.")
                        else:
                            edit_values = {
                                "full_name": edit_name,
                                "date_of_birth": edit_dob.strftime("%d/%m/%Y"),
                                "email": edit_email,
                                "glucose": edit_glucose,
                                "haemoglobin": edit_haemoglobin,
                                "cholesterol": edit_cholesterol,
                            }
                            unchanged_values = {
                                "full_name": item["full_name"],
                                "date_of_birth": date.fromisoformat(
                                    item["date_of_birth"]
                                ).strftime("%d/%m/%Y"),
                                "email": item["email"],
                                "glucose": float(item["glucose"]) if item["glucose"] is not None else None,
                                "haemoglobin": float(item["haemoglobin"]) if item["haemoglobin"] is not None else None,
                                "cholesterol": float(item["cholesterol"]) if item["cholesterol"] is not None else None,
                            }
                            update_payload = {
                                key: value
                                for key, value in edit_values.items()
                                if value != unchanged_values[key]
                            }
                            if not update_payload:
                                st.info("No changes to save.")
                            else:
                                try:
                                    api_request(
                                        "PUT",
                                        f"/api/patients/{patient_id}",
                                        json=update_payload,
                                    )
                                except BackendError as error:
                                    st.error(str(error))
                                else:
                                    st.session_state["edit_patient_id"] = None
                                    flash_and_rerun("success", "Patient information updated.")

    st.markdown(
        '<div class="disclaimer">AI-generated remarks are informational and '
        "are not a medical diagnosis.</div>",
        unsafe_allow_html=True,
    )

else:
    st.title("Assessment data")
    st.markdown(
        '<p class="section-note">Run the exact ten supplied assessment cases through the live API. '
        "Invalid examples stay rejected; valid examples are saved in SQLite.</p>",
        unsafe_allow_html=True,
    )
    from components.assessment_data import ASSESSMENT_PATIENTS

    with st.expander("Review the assessment dataset", expanded=False):
        st.dataframe(
            [
                {
                    "Test": item["test_number"],
                    "Full name": item["full_name"],
                    "Date of birth": item["date_of_birth"],
                    "Email": item["email"],
                    "Glucose": item["glucose"],
                    "Haemoglobin": item["haemoglobin"],
                    "Cholesterol": item["cholesterol"],
                }
                for item in ASSESSMENT_PATIENTS
            ],
            hide_index=True,
            width="stretch",
        )
    st.warning(
        "Running this batch writes each valid case to your database. Duplicate patient "
        "name/email pairs are rejected, so existing patients in your database may also be rejected."
    )
    confirmed = st.checkbox("I understand valid assessment records will be added to SQLite.")
    if st.button("Run all 10 assessment cases", type="primary", disabled=not confirmed):
        results: list[dict[str, Any]] = []
        progress = st.progress(0)
        for position, case in enumerate(ASSESSMENT_PATIENTS, start=1):
            payload = patient_payload(
                case["full_name"],
                date(2000, 1, 1),
                case["email"],
                float(case["glucose"]),
                float(case["haemoglobin"]),
                float(case["cholesterol"]),
            )
            payload["date_of_birth"] = case["date_of_birth"]
            try:
                record = api_request("POST", "/api/patients", json=payload)
            except BackendError as error:
                results.append(
                    {
                        "Test": case["test_number"],
                        "Patient": case["full_name"],
                        "Result": "Rejected",
                        "Details": str(error),
                    }
                )
            else:
                results.append(
                    {
                        "Test": case["test_number"],
                        "Patient": case["full_name"],
                        "Result": "Accepted",
                        "Details": f"Saved as #{record['id']} · {status_label(record.get('ai_status', 'pending'))}",
                    }
                )
            progress.progress(position / len(ASSESSMENT_PATIENTS))
        st.session_state["assessment_results"] = results
        st.rerun()

    results = st.session_state.get("assessment_results", [])
    if results:
        st.subheader("Latest assessment run")
        accepted = sum(result["Result"] == "Accepted" for result in results)
        rejected = len(results) - accepted
        accepted_col, rejected_col = st.columns(2)
        accepted_col.metric("Accepted", accepted)
        rejected_col.metric("Rejected", rejected)
        st.dataframe(results, hide_index=True, width="stretch")
        if any(result["Test"] == 6 and result["Result"] == "Rejected" for result in results):
            st.info(
                "Test 6 matches Test 1's name and email, so duplicate prevention "
                "rejects it when Test 1 is already saved."
            )

    st.markdown(
        '<div class="disclaimer">The assessment dataset is shown here as an explicit '
        "test harness. Patient records shown in the dashboard are always loaded from SQLite. "
        "AI-generated remarks are not a medical diagnosis.</div>",
        unsafe_allow_html=True,
    )
