"""
Hospital ER Dashboard - CodeZero
Run: streamlit run ui/hospital_dashboard.py --server.port 8502
"""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue

logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="CodeZero ER Dashboard", page_icon="🏥", layout="wide")

# Minimal CSS
st.markdown("""<style>
.block-container{padding:1rem 2rem}
.stButton>button{min-height:44px;border-radius:8px}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def get_queue():
    return HospitalQueue()

queue = get_queue()

ICONS = {"EMERGENCY": "🔴", "URGENT": "🟠", "ROUTINE": "🟢"}
PREP = {
    "EMERGENCY": ["Assign resuscitation bay", "Alert attending physician",
                   "Prepare crash cart", "Pre-order STAT labs", "ECG ready"],
    "URGENT": ["Assign treatment room", "Notify triage nurse",
               "Prepare standard labs", "Queue imaging"],
    "ROUTINE": ["Assign waiting area", "Standard intake forms", "Vitals on arrival"],
}


def mins_until(iso):
    if not iso:
        return "N/A"
    try:
        arr = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = (arr - datetime.now(timezone.utc)).total_seconds() / 60
        return "ARRIVED" if diff <= 0 else "{} min".format(int(diff))
    except Exception:
        return "N/A"


def render_patient(p):
    level = p.get("triage_level", "URGENT")
    pid = p.get("patient_id", "")
    icon = ICONS.get(level, "🟠")
    eta = p.get("eta_minutes")
    arrival = p.get("arrival_time")
    ct = mins_until(arrival) if arrival else ("~{} min".format(eta) if eta else "N/A")
    dest = p.get("destination_hospital", "")
    flags = p.get("red_flags", [])
    status = p.get("status", "incoming")

    # Use native Streamlit containers
    if level == "EMERGENCY":
        container = st.error
    elif level == "URGENT":
        container = st.warning
    else:
        container = st.success

    flags_str = ""
    if flags and flags != ["none_identified"]:
        flags_str = "\n\n🚩 " + " · ".join(f.replace("_", " ").title() for f in flags[:5])

    dest_str = "\n\n🏥 **Heading to:** {}".format(dest) if dest else ""

    container(
        "**{} {} — {}** ⏱ **{}**\n\n"
        "**Complaint:** {}\n\n"
        "**Assessment:** {}{}"
        "\n\n**Risk:** {}/10 · **Language:** {}{}"
        .format(
            icon, level, pid, ct,
            p.get("chief_complaint", ""),
            p.get("assessment", ""),
            dest_str,
            p.get("risk_score", 5), p.get("language", "en-US"),
            flags_str,
        )
    )

    # Prep checklist
    preps = PREP.get(level, [])
    if preps and status == "incoming":
        with st.expander("📋 Pre-Arrival Prep — {}".format(pid)):
            for pr in preps:
                st.checkbox(pr, key="{}_{}".format(pid, pr))

    # Action buttons
    bc = st.columns(4)
    with bc[0]:
        if status == "incoming" and st.button("✅ Arrived", key="a_{}".format(pid)):
            queue.update_status(pid, "arrived")
            st.rerun()
    with bc[1]:
        if status == "arrived" and st.button("🩺 Treating", key="t_{}".format(pid)):
            queue.update_status(pid, "in_treatment")
            st.rerun()
    with bc[2]:
        if status == "in_treatment" and st.button("🏠 Discharge", key="d_{}".format(pid)):
            queue.update_status(pid, "discharged")
            st.rerun()
    with bc[3]:
        if st.button("📄 Details", key="det_{}".format(pid)):
            st.json(p)
    st.divider()


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.title("🏥 ER COMMAND CENTER")
    st.caption("CodeZero Triage System · {}".format(now))

    # Stats
    stats = queue.get_queue_stats()
    by_level = stats.get("by_level", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Incoming", stats.get("total_incoming", 0))
    c2.metric("🔴 Emergency", by_level.get("EMERGENCY", 0))
    c3.metric("🟠 Urgent", by_level.get("URGENT", 0))
    c4.metric("🟢 Routine", by_level.get("ROUTINE", 0))

    st.divider()

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📥 Incoming", "📊 All Patients", "⚙️ Admin"])

    with tab1:
        patients = queue.get_incoming_patients(limit=20)
        if not patients:
            st.info("No incoming patients. Waiting for triage submissions...")
        for p in patients:
            render_patient(p)

    with tab2:
        all_p = queue.get_all_patients(limit=50)
        if not all_p:
            st.info("No records yet.")
        else:
            try:
                import pandas as pd
                df = pd.DataFrame(all_p)
                cols = ["patient_id", "triage_level", "chief_complaint", "risk_score",
                        "eta_minutes", "destination_hospital", "language", "status", "timestamp"]
                avail = [c for c in cols if c in df.columns]
                st.dataframe(df[avail], use_container_width=True, hide_index=True)
            except Exception:
                for p in all_p:
                    st.write(p)

    with tab3:
        st.subheader("Admin Tools")
        if st.button("🗑 Clear All Records"):
            queue.clear_queue()
            st.success("Cleared.")
            st.rerun()
        st.divider()
        if st.button("➕ Add Test Emergency"):
            try:
                te = TriageEngine()
            except Exception:
                from src.triage_engine import TriageEngine
                te = TriageEngine()
            r = te.create_patient_record(
                chief_complaint="Severe chest pain with arm radiation and sweating",
                assessment=dict(
                    triage_level="EMERGENCY",
                    assessment="Findings: Pain radiates to arm; Sweating; Shortness of breath. 3 red flags.",
                    red_flags=["pain_radiation", "diaphoresis", "dyspnea"],
                    recommended_action="ER immediately",
                    risk_score=9, source_guidelines=["chest_pain_protocol.txt"],
                    suspected_conditions=["Acute Coronary Syndrome"],
                    time_sensitivity="Within 10 minutes",
                ),
                language="de-DE", eta_minutes=12,
            )
            r["destination_hospital"] = "Klinikum Stuttgart (ER)"
            hospital_queue.add_patient(r)
            st.success("Added: {}".format(r["patient_id"]))
            st.rerun()

        if st.button("➕ Add Test Routine"):
            try:
                te = TriageEngine()
            except Exception:
                from src.triage_engine import TriageEngine
                te = TriageEngine()
            r = te.create_patient_record(
                chief_complaint="Mild headache for 2 days",
                assessment=dict(
                    triage_level="ROUTINE",
                    assessment="Pain 3/10. No red flags. Triage: ROUTINE.",
                    red_flags=["none_identified"],
                    recommended_action="See GP if persists",
                    risk_score=2, source_guidelines=["general"],
                    suspected_conditions=["Tension Headache"],
                    time_sensitivity="Within 48 hours",
                ),
                language="en-US", eta_minutes=30,
            )
            r["destination_hospital"] = "Robert-Bosch-Krankenhaus (ER)"
            hospital_queue.add_patient(r)
            st.success("Added: {}".format(r["patient_id"]))
            st.rerun()

    with st.sidebar:
        st.markdown("### 🏥 CodeZero ER")
        st.divider()
        st.markdown("**Legend**")
        st.markdown("🔴 Emergency — Immediate")
        st.markdown("🟠 Urgent — 30 min")
        st.markdown("🟢 Routine — 2 hours")
        st.divider()
        st.markdown("**Flow:** Incoming → Arrived → Treatment → Discharged")
        st.divider()
        if st.button("🔄 Refresh"):
            st.rerun()


if __name__ == "__main__":
    main()