"""
Hospital ER Dashboard (Streamlit)
=================================
Real-time ER command center showing incoming triaged patients with
countdown timers, pre-arrival preparation checklists, and queue
statistics.

Run with: streamlit run ui/hospital_dashboard.py

AI-102 Concepts demonstrated:
  - Multi-service orchestration visualization
  - Real-time data pipeline consumption
  - Dashboard design for AI-powered healthcare systems
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ER Command Center",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """<style>
    .main .block-container {padding:1rem 2rem}
    .metric-card {background:#1e1e2e;color:#fff;padding:1.2rem;border-radius:10px;text-align:center;margin:.5rem 0}
    .metric-number {font-size:2.5rem;font-weight:700}
    .patient-card {border-radius:10px;padding:1.2rem;margin:.8rem 0;border-left:5px solid}
    .card-emergency {background:#fff0f0;border-color:#ff0000}
    .card-urgent {background:#fff8f0;border-color:#ff8800}
    .card-routine {background:#f0fff0;border-color:#22aa22}
    .countdown {font-size:1.8rem;font-weight:700;color:#0077ff}
    .prep-item {padding:.3rem .5rem;margin:.2rem 0;background:#f0f4ff;border-radius:4px;font-size:.9rem}
    </style>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

@st.cache_resource
def get_queue():
    return HospitalQueue()

queue = get_queue()

TRIAGE_ICONS = {"EMERGENCY": "🔴", "URGENT": "🟠", "ROUTINE": "🟢"}
TRIAGE_CSS = {"EMERGENCY": "card-emergency", "URGENT": "card-urgent", "ROUTINE": "card-routine"}

# Pre-arrival preparation suggestions per triage level
PREP_SUGGESTIONS = {
    "EMERGENCY": [
        "Assign resuscitation bay",
        "Alert attending physician",
        "Prepare crash cart",
        "Pre-order STAT labs (Troponin, CBC, BMP)",
        "Ensure ECG machine is ready",
    ],
    "URGENT": [
        "Assign treatment room",
        "Notify triage nurse",
        "Prepare standard lab panel",
        "Queue diagnostic imaging if needed",
    ],
    "ROUTINE": [
        "Assign waiting area",
        "Standard intake paperwork",
        "Vital signs on arrival",
    ],
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def render_header():
    hospital_name = "CITY GENERAL HOSPITAL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(f"# 🏥 {hospital_name} — ER COMMAND CENTER")
    st.caption(f"🕐 {now}  |  Auto-refreshes every 10 seconds")

    # AI-102: Streamlit auto-refresh via st.fragment or rerun loop
    # In production, use WebSocket or polling for real-time updates
    import time
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = True
    st.session_state.auto_refresh = st.toggle("Auto-refresh (10s)", value=st.session_state.auto_refresh)
    if st.session_state.auto_refresh:
        time.sleep(0.05)  # Small yield for UI to render
        # Use st.empty + rerun pattern for auto-refresh
        placeholder = st.empty()
        placeholder.empty()


# ---------------------------------------------------------------------------
# Statistics cards
# ---------------------------------------------------------------------------

def render_stats():
    stats = queue.get_queue_stats()
    by_level = stats.get("by_level", {})

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-number">{stats.get("total_incoming",0)}</div>'
            f"<div>Total Incoming</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card" style="border-bottom:3px solid #ff0000">'
            f'<div class="metric-number">{by_level.get("EMERGENCY",0)}</div>'
            f"<div>🔴 Emergency</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card" style="border-bottom:3px solid #ff8800">'
            f'<div class="metric-number">{by_level.get("URGENT",0)}</div>'
            f"<div>🟠 Urgent</div></div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-card" style="border-bottom:3px solid #22aa22">'
            f'<div class="metric-number">{by_level.get("ROUTINE",0)}</div>'
            f"<div>🟢 Routine</div></div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Patient cards
# ---------------------------------------------------------------------------

def _minutes_until(arrival_iso: str | None) -> str:
    """Calculate minutes remaining until arrival."""
    if not arrival_iso:
        return "N/A"
    try:
        arrival = datetime.fromisoformat(arrival_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (arrival - now).total_seconds() / 60
        if diff <= 0:
            return "ARRIVED"
        return f"{int(diff)} min"
    except Exception:
        return "N/A"


def render_patient_card(patient: dict):
    """Render a single patient card."""
    level = patient.get("triage_level", "URGENT")
    icon = TRIAGE_ICONS.get(level, "🟠")
    css = TRIAGE_CSS.get(level, "card-urgent")

    pid = patient.get("patient_id", "N/A")
    complaint = patient.get("chief_complaint", "Unknown")
    assessment = patient.get("assessment", "")
    risk = patient.get("risk_score", 5)
    lang = patient.get("language", "en-US")
    eta = patient.get("eta_minutes")
    arrival = patient.get("arrival_time")
    red_flags = patient.get("red_flags", [])
    suspected = patient.get("suspected_conditions", [])
    status = patient.get("status", "incoming")

    countdown_text = _minutes_until(arrival) if arrival else (f"~{eta} min" if eta else "N/A")

    # Card HTML
    flags_html = ""
    if red_flags and red_flags != ["none_identified"]:
        flags_html = " ".join(
            f'<span style="background:#ffdddd;padding:2px 6px;border-radius:4px;font-size:.8rem;margin:2px">'
            f"🚩 {f.replace('_',' ')}</span>"
            for f in red_flags[:5]
        )

    st.markdown(
        f'<div class="patient-card {css}">'
        f"<div style='display:flex;justify-content:space-between;align-items:center'>"
        f"<div><strong>{icon} {level}</strong> — {pid}</div>"
        f'<div class="countdown">⏱ {countdown_text}</div>'
        f"</div>"
        f"<hr style='margin:.5rem 0'>"
        f"<p><strong>Chief Complaint:</strong> {complaint}</p>"
        f"<p><strong>Assessment:</strong> {assessment}</p>"
        f"<p><strong>Risk Score:</strong> {risk}/10 &nbsp;|&nbsp; <strong>Language:</strong> {lang}</p>"
        f"<div>{flags_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Pre-arrival preparation checklist
    preps = PREP_SUGGESTIONS.get(level, [])
    if preps and status == "incoming":
        with st.expander(f"📋 Pre-Arrival Prep — {pid}"):
            for prep in preps:
                st.checkbox(prep, key=f"{pid}_{prep}")

    # Action buttons
    bcols = st.columns(4)
    with bcols[0]:
        if status == "incoming" and st.button("✅ Mark Arrived", key=f"arrive_{pid}"):
            queue.update_status(pid, "arrived")
            st.rerun()
    with bcols[1]:
        if status == "arrived" and st.button("🩺 In Treatment", key=f"treat_{pid}"):
            queue.update_status(pid, "in_treatment")
            st.rerun()
    with bcols[2]:
        if status == "in_treatment" and st.button("🏠 Discharge", key=f"discharge_{pid}"):
            queue.update_status(pid, "discharged")
            st.rerun()
    with bcols[3]:
        if st.button("📄 Full Details", key=f"details_{pid}"):
            st.json(patient)


# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------

def main():
    render_header()
    st.markdown("---")
    render_stats()
    st.markdown("---")

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📥 Incoming Patients", "📊 All Patients", "⚙️ Admin"])

    with tab1:
        st.markdown("### Incoming Patients (Real-time)")
        patients = queue.get_incoming_patients(limit=20)
        if not patients:
            st.info("No incoming patients at this time. Waiting for triage submissions...")
        else:
            for p in patients:
                render_patient_card(p)

    with tab2:
        st.markdown("### All Patient Records")
        all_patients = queue.get_all_patients(limit=50)
        if not all_patients:
            st.info("No patient records yet.")
        else:
            import pandas as pd
            df = pd.DataFrame(all_patients)
            display_cols = [
                "patient_id", "triage_level", "chief_complaint",
                "risk_score", "eta_minutes", "language", "status", "timestamp",
            ]
            available = [c for c in display_cols if c in df.columns]
            st.dataframe(df[available], use_container_width=True, hide_index=True)

    with tab3:
        st.markdown("### Admin Controls")
        st.warning("⚠️ These actions are irreversible in the current session.")
        if st.button("🗑 Clear All Patient Records", type="secondary"):
            queue.clear_queue()
            st.success("Queue cleared.")
            st.rerun()

        st.markdown("---")
        st.markdown("### Add Test Patient")
        if st.button("➕ Add Sample Emergency Patient"):
            from src.triage_engine import TriageEngine
            te = TriageEngine()
            record = te.create_patient_record(
                chief_complaint="Chest pain with left arm radiation and diaphoresis",
                assessment={
                    "triage_level": "EMERGENCY",
                    "assessment": "Suspected Acute Coronary Syndrome. Multiple cardiac red flags present.",
                    "red_flags": ["chest_pain", "arm_radiation", "diaphoresis", "dyspnea"],
                    "recommended_action": "Proceed to nearest ER immediately.",
                    "risk_score": 9,
                    "source_guidelines": ["chest_pain_protocol.txt"],
                    "suspected_conditions": ["Acute Coronary Syndrome", "STEMI"],
                    "time_sensitivity": "Seek ER within 10 minutes",
                },
                language="de-DE",
                eta_minutes=18,
                location={"lat": 48.78, "lon": 9.18},
            )
            queue.add_patient(record)
            st.success(f"Added test patient: {record['patient_id']}")
            st.rerun()

        if st.button("➕ Add Sample Routine Patient"):
            from src.triage_engine import TriageEngine
            te = TriageEngine()
            record = te.create_patient_record(
                chief_complaint="Mild headache for 2 days",
                assessment={
                    "triage_level": "ROUTINE",
                    "assessment": "Mild tension headache. No red flags identified.",
                    "red_flags": ["none_identified"],
                    "recommended_action": "Self-care with OTC pain relief. See GP if persists.",
                    "risk_score": 2,
                    "source_guidelines": ["general_assessment"],
                    "suspected_conditions": ["Tension Headache"],
                    "time_sensitivity": "Schedule appointment within 48 hours",
                },
                language="en-US",
                eta_minutes=35,
                location={"lat": 48.80, "lon": 9.20},
            )
            queue.add_patient(record)
            st.success(f"Added test patient: {record['patient_id']}")
            st.rerun()

    # Sidebar
    with st.sidebar:
        st.markdown("### 🏥 Dashboard Settings")
        st.markdown(f"**Hospital:** City General Hospital")
        st.markdown("---")
        st.markdown("### Legend")
        st.markdown("🔴 **EMERGENCY** — Immediate attention")
        st.markdown("🟠 **URGENT** — Within 30 minutes")
        st.markdown("🟢 **ROUTINE** — Within 2 hours")
        st.markdown("---")
        st.markdown("### Status Flow")
        st.markdown("📥 Incoming → ✅ Arrived → 🩺 Treatment → 🏠 Discharged")
        st.markdown("---")
        if st.button("🔄 Refresh Now"):
            st.rerun()
        st.caption("Toggle auto-refresh in the header area.")

    # Auto-refresh: rerun after 10 seconds if enabled
    if st.session_state.get("auto_refresh", False):
        import time
        time.sleep(10)
        st.rerun()


if __name__ == "__main__":
    main()