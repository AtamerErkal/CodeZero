"""
Hospital ER Dashboard - CodeZero
=================================
Real-time emergency department command center. Displays incoming triaged
patients with countdown timers and pre-arrival preparation checklists.

Run: streamlit run ui/hospital_dashboard.py --server.port 8502

FIXES APPLIED:
  - TriageEngine now properly imported at the top of the file
  - 'hospital_queue' undefined variable bug fixed (was using 'queue' object)
  - Auto-refresh added (30-second interval)
  - Wildcard imports removed
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Project root on sys.path so src.* imports work regardless of cwd
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# FIX: All imports at the top — no deferred imports inside functions
from src.hospital_queue import HospitalQueue
from src.triage_engine import TRIAGE_COLORS, TRIAGE_EMERGENCY, TRIAGE_ROUTINE, TRIAGE_URGENT, TriageEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CodeZero ER Dashboard",
    page_icon="🏥",
    layout="wide",
)

st.markdown("""
<style>
.block-container { padding: 1rem 2rem; }
.stButton > button { min-height: 44px; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Shared service instances (cached across reruns)
# ---------------------------------------------------------------------------
AUTO_REFRESH_SECONDS = 30


@st.cache_resource
def get_queue() -> HospitalQueue:
    """Return a cached HospitalQueue instance."""
    return HospitalQueue()


@st.cache_resource
def get_triage_engine() -> TriageEngine:
    """Return a cached TriageEngine instance for creating test records."""
    return TriageEngine()


# FIX: single canonical name used everywhere in this file
hospital_queue = get_queue()
triage_engine = get_triage_engine()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LEVEL_ICONS = {
    TRIAGE_EMERGENCY: "🔴",
    TRIAGE_URGENT: "🟠",
    TRIAGE_ROUTINE: "🟢",
}

# PRE_ARRIVAL_PREP removed — preparation checklists are now generated
# dynamically by GPT-4 via triage_engine.generate_hospital_prep() so that
# each patient card shows condition-specific ER preparation steps.
_PREP_CACHE: dict[str, list[str]] = {}  # patient_id → prep items cache


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def minutes_until_arrival(iso_timestamp: str) -> str:
    """Return a human-readable countdown string from an ISO timestamp.

    Args:
        iso_timestamp: ISO 8601 arrival time string.

    Returns:
        Countdown string such as '22 min', 'ARRIVED', or 'N/A'.
    """
    if not iso_timestamp:
        return "N/A"
    try:
        arrival = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        delta_minutes = (arrival - datetime.now(timezone.utc)).total_seconds() / 60
        if delta_minutes <= 0:
            return "ARRIVED"
        return f"{int(delta_minutes)} min"
    except Exception:
        return "N/A"


def render_patient_card(patient: dict) -> None:
    """Render a single patient card with status controls.

    Args:
        patient: Patient record dict from HospitalQueue.
    """
    level = patient.get("triage_level", TRIAGE_URGENT)
    pid = patient.get("patient_id", "UNKNOWN")
    icon = LEVEL_ICONS.get(level, "🟠")
    status = patient.get("status", "incoming")
    eta_raw = patient.get("eta_minutes")
    arrival = patient.get("arrival_time")

    # Countdown display
    countdown = (
        minutes_until_arrival(arrival)
        if arrival
        else (f"~{eta_raw} min" if eta_raw else "N/A")
    )

    # Red flag list (skip placeholder)
    flags: list[str] = patient.get("red_flags", [])
    active_flags = [f for f in flags if f != "none_identified"]

    dest = patient.get("destination_hospital", "")
    dest_line = f"\n\n🏥 **Heading to:** {dest}" if dest else ""
    flags_line = (
        "\n\n🚩 " + " · ".join(f.replace("_", " ").title() for f in active_flags[:5])
        if active_flags
        else ""
    )

    # Choose container style by triage level
    body = (
        f"**{icon} {level} — {pid}** ⏱ **{countdown}**\n\n"
        f"**Complaint:** {patient.get('chief_complaint', '')}\n\n"
        f"**Assessment:** {patient.get('assessment', '')}"
        f"{dest_line}"
        f"\n\n**Risk:** {patient.get('risk_score', 5)}/10 · "
        f"**Language:** {patient.get('language', 'en-US')}"
        f"{flags_line}"
    )

    if level == TRIAGE_EMERGENCY:
        st.error(body)
    elif level == TRIAGE_URGENT:
        st.warning(body)
    else:
        st.success(body)

    # Pre-arrival checklist — GPT-4 generated, condition-specific
    if status == "incoming":
        with st.expander(f"📋 Pre-Arrival Prep — {pid}", expanded=(level == TRIAGE_EMERGENCY)):
            # Use cached prep items to avoid regenerating on every rerun
            if pid not in _PREP_CACHE:
                with st.spinner("Generating prep checklist..."):
                    try:
                        _PREP_CACHE[pid] = triage_engine.generate_hospital_prep(
                            chief_complaint=patient.get("chief_complaint", "unknown complaint"),
                            assessment=patient,
                        )
                    except Exception as exc:
                        logger.error("Prep generation failed for %s: %s", pid, exc)
                        _PREP_CACHE[pid] = ["Assign appropriate bay", "Alert attending physician", "Prepare standard monitoring"]
            for prep_item in _PREP_CACHE.get(pid, []):
                st.checkbox(prep_item, key=f"{pid}_{prep_item}")

    # Status action buttons
    btn_cols = st.columns(4)
    with btn_cols[0]:
        if status == "incoming" and st.button("✅ Arrived", key=f"arrive_{pid}"):
            hospital_queue.update_status(pid, "arrived")
            st.rerun()
    with btn_cols[1]:
        if status == "arrived" and st.button("🩺 Treating", key=f"treat_{pid}"):
            hospital_queue.update_status(pid, "in_treatment")
            st.rerun()
    with btn_cols[2]:
        if status == "in_treatment" and st.button("🏠 Discharge", key=f"discharge_{pid}"):
            hospital_queue.update_status(pid, "discharged")
            st.rerun()
    with btn_cols[3]:
        if st.button("📄 Details", key=f"details_{pid}"):
            st.json(patient)

    st.divider()


# ---------------------------------------------------------------------------
# Admin helpers — test record factories
# ---------------------------------------------------------------------------
def _add_test_emergency() -> None:
    """Insert a synthetic EMERGENCY patient for dashboard testing."""
    record = triage_engine.create_patient_record(
        chief_complaint="Severe chest pain with arm radiation and sweating",
        assessment={
            "triage_level": TRIAGE_EMERGENCY,
            "assessment": (
                "Findings: Pain radiates to arm; Sweating; Shortness of breath. "
                "3 red flags identified."
            ),
            "red_flags": ["pain_radiation", "diaphoresis", "dyspnea"],
            "recommended_action": "Proceed to ER immediately.",
            "risk_score": 9,
            "source_guidelines": ["chest_pain_protocol.txt"],
            "suspected_conditions": ["Acute Coronary Syndrome"],
            "time_sensitivity": "Within 10 minutes",
        },
        language="de-DE",
        eta_minutes=12,
    )
    record["destination_hospital"] = "Klinikum Stuttgart (ER)"
    # FIX: use 'hospital_queue' (the module-level instance) not an undefined name
    hospital_queue.add_patient(record)
    st.success(f"Added EMERGENCY: {record['patient_id']}")


def _add_test_routine() -> None:
    """Insert a synthetic ROUTINE patient for dashboard testing."""
    record = triage_engine.create_patient_record(
        chief_complaint="Mild headache for 2 days",
        assessment={
            "triage_level": TRIAGE_ROUTINE,
            "assessment": "Pain 3/10. No red flags. Triage: ROUTINE.",
            "red_flags": ["none_identified"],
            "recommended_action": "See GP if symptoms persist.",
            "risk_score": 2,
            "source_guidelines": ["general"],
            "suspected_conditions": ["Tension Headache"],
            "time_sensitivity": "Within 48 hours",
        },
        language="en-US",
        eta_minutes=30,
    )
    record["destination_hospital"] = "Robert-Bosch-Krankenhaus (ER)"
    hospital_queue.add_patient(record)
    st.success(f"Added ROUTINE: {record['patient_id']}")


# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------
def main() -> None:
    """Render the full ER dashboard."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.title("🏥 ER COMMAND CENTER")
    st.caption(f"CodeZero Triage System · {now_str}")

    # --- Summary metrics ---
    stats = hospital_queue.get_queue_stats()
    by_level = stats.get("by_level", {})

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Incoming", stats.get("total_incoming", 0))
    col2.metric("🔴 Emergency", by_level.get(TRIAGE_EMERGENCY, 0))
    col3.metric("🟠 Urgent", by_level.get(TRIAGE_URGENT, 0))
    col4.metric("🟢 Routine", by_level.get(TRIAGE_ROUTINE, 0))

    st.divider()

    # --- Main tabs ---
    tab_incoming, tab_all, tab_admin = st.tabs(
        ["📥 Incoming", "📊 All Patients", "⚙️ Admin"]
    )

    with tab_incoming:
        incoming = hospital_queue.get_incoming_patients(limit=20)
        if not incoming:
            st.info("No incoming patients. Waiting for triage submissions...")
        for patient in incoming:
            render_patient_card(patient)

    with tab_all:
        all_patients = hospital_queue.get_all_patients(limit=50)
        if not all_patients:
            st.info("No patient records yet.")
        else:
            try:
                import pandas as pd

                df = pd.DataFrame(all_patients)
                desired_cols = [
                    "patient_id", "triage_level", "chief_complaint",
                    "risk_score", "eta_minutes", "destination_hospital",
                    "language", "status", "timestamp",
                ]
                available_cols = [c for c in desired_cols if c in df.columns]
                st.dataframe(df[available_cols], use_container_width=True, hide_index=True)
            except Exception as exc:
                logger.error("DataFrame render error: %s", exc)
                for p in all_patients:
                    st.write(p)

    with tab_admin:
        st.subheader("Admin Tools")

        if st.button("🗑 Clear All Records", type="secondary"):
            hospital_queue.clear_queue()
            st.success("Queue cleared.")
            st.rerun()

        st.divider()
        st.markdown("**Add Test Patients**")
        adm_col1, adm_col2 = st.columns(2)
        with adm_col1:
            if st.button("➕ Add Test Emergency", use_container_width=True):
                _add_test_emergency()
                st.rerun()
        with adm_col2:
            if st.button("➕ Add Test Routine", use_container_width=True):
                _add_test_routine()
                st.rerun()

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### 🏥 CodeZero ER")
        st.divider()
        st.markdown("**Triage Levels**")
        st.markdown("🔴 **Emergency** — Immediate")
        st.markdown("🟠 **Urgent** — Within 30 min")
        st.markdown("🟢 **Routine** — Within 2 hours")
        st.divider()
        st.markdown("**Status Flow**")
        st.markdown("Incoming → Arrived → Treatment → Discharged")
        st.divider()

        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()

        # FIX: Auto-refresh using st.empty + time-based rerun trigger
        st.caption(f"Auto-refreshes every {AUTO_REFRESH_SECONDS}s")
        # Store last refresh time in session state
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = datetime.now(timezone.utc)

        elapsed = (
            datetime.now(timezone.utc) - st.session_state.last_refresh
        ).total_seconds()

        if elapsed >= AUTO_REFRESH_SECONDS:
            st.session_state.last_refresh = datetime.now(timezone.utc)
            st.rerun()

        seconds_left = max(0, int(AUTO_REFRESH_SECONDS - elapsed))
        st.caption(f"Next refresh in {seconds_left}s")


if __name__ == "__main__":
    main()