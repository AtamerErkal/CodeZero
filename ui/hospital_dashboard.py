"""
Hospital ER Dashboard — CodeZero
"""

from __future__ import annotations
import logging, sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
st.set_page_config(page_title="CodeZero ER Dashboard", page_icon="🏥", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
.main { background: #f7f8fc !important; }
header[data-testid="stHeader"] { background: #f7f8fc !important; }
section[data-testid="stSidebar"] { background: #eef0f5 !important; }
h1, h2, h3, h4 { color: #1b2559 !important; font-weight: 700 !important; }
p, li, span, div, label, td, th { color: #333 !important; }

.dash-header {
    background: linear-gradient(135deg, #1b2559 0%, #2d4a9e 100%);
    color: white; padding: 1.5rem 2rem; border-radius: 16px; margin-bottom: 1.5rem;
}
.dash-header * { color: white !important; }
.dash-header h1 { margin: 0; font-size: 1.5rem; }
.dash-header p { margin: 0.2rem 0 0; opacity: 0.85; font-size: 0.9rem; }

.stat-card {
    background: white; border-radius: 14px; padding: 1.2rem;
    text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    border: 1px solid #e8eaf0;
}
.stat-card .num { font-size: 2.4rem; font-weight: 700; color: #1b2559 !important; }
.stat-card .lbl { font-size: 0.9rem; color: #666 !important; margin-top: 2px; }

.p-card {
    background: white; border-radius: 12px; padding: 1.2rem;
    border-left: 5px solid; margin: 0.8rem 0;
    box-shadow: 0 1px 8px rgba(0,0,0,0.04);
}
.p-card * { color: #1a1a1a !important; }
.p-emergency { border-color: #dc2626; }
.p-urgent { border-color: #ea580c; }
.p-routine { border-color: #16a34a; }

.countdown { font-size: 1.6rem; font-weight: 700; color: #2d4a9e !important; }

.flag-tag {
    display: inline-block; background: #fef2f2; color: #dc2626 !important;
    padding: 2px 10px; border-radius: 6px; font-size: 0.8rem;
    margin: 2px; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
@st.cache_resource
def get_queue():
    return HospitalQueue()

queue = get_queue()

ICONS = {"EMERGENCY": "🔴", "URGENT": "🟠", "ROUTINE": "🟢"}
CSS = {"EMERGENCY": "p-emergency", "URGENT": "p-urgent", "ROUTINE": "p-routine"}

PREP = {
    "EMERGENCY": ["Assign resuscitation bay", "Alert attending physician",
                   "Prepare crash cart", "Pre-order STAT labs", "ECG machine ready"],
    "URGENT": ["Assign treatment room", "Notify triage nurse",
               "Prepare standard labs", "Queue imaging"],
    "ROUTINE": ["Assign waiting area", "Standard intake forms", "Vitals on arrival"],
}

# ---------------------------------------------------------------------------
def mins_until(iso):
    if not iso:
        return "N/A"
    try:
        arr = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        diff = (arr - datetime.now(timezone.utc)).total_seconds() / 60
        return "ARRIVED" if diff <= 0 else f"{int(diff)} min"
    except Exception:
        return "N/A"


def render_patient(p):
    level = p.get("triage_level", "URGENT")
    pid = p.get("patient_id", "")
    css = CSS.get(level, "p-urgent")
    icon = ICONS.get(level, "🟠")
    eta = p.get("eta_minutes")
    arrival = p.get("arrival_time")
    ct = mins_until(arrival) if arrival else (f"~{eta} min" if eta else "N/A")
    dest = p.get("destination_hospital", "")
    flags = p.get("red_flags", [])
    status = p.get("status", "incoming")

    flags_html = ""
    if flags and flags != ["none_identified"]:
        flags_html = " ".join(f'<span class="flag-tag">🚩 {f.replace("_"," ")}</span>' for f in flags[:5])

    dest_html = f"<br><strong>🏥 Heading to:</strong> {dest}" if dest else ""

    st.markdown(
        f'<div class="p-card {css}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<div><strong>{icon} {level}</strong> — {pid}</div>'
        f'<div class="countdown">⏱ {ct}</div></div>'
        f'<hr style="margin:0.5rem 0;border-color:#eee">'
        f'<strong>Complaint:</strong> {p.get("chief_complaint","")}<br>'
        f'<strong>Assessment:</strong> {p.get("assessment","")}{dest_html}<br>'
        f'<strong>Risk:</strong> {p.get("risk_score",5)}/10 · '
        f'<strong>Language:</strong> {p.get("language","en-US")}<br>'
        f'{flags_html}</div>',
        unsafe_allow_html=True,
    )

    preps = PREP.get(level, [])
    if preps and status == "incoming":
        with st.expander(f"📋 Prep — {pid}"):
            for pr in preps:
                st.checkbox(pr, key=f"{pid}_{pr}")

    bc = st.columns(4)
    with bc[0]:
        if status == "incoming" and st.button("✅ Arrived", key=f"a_{pid}"):
            queue.update_status(pid, "arrived"); st.rerun()
    with bc[1]:
        if status == "arrived" and st.button("🩺 Treating", key=f"t_{pid}"):
            queue.update_status(pid, "in_treatment"); st.rerun()
    with bc[2]:
        if status == "in_treatment" and st.button("🏠 Discharge", key=f"d_{pid}"):
            queue.update_status(pid, "discharged"); st.rerun()
    with bc[3]:
        if st.button("📄 Details", key=f"det_{pid}"):
            st.json(p)


# ---------------------------------------------------------------------------
def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st.markdown(
        f'<div class="dash-header"><h1>🏥 ER COMMAND CENTER</h1>'
        f'<p>CodeZero Triage System · {now}</p></div>',
        unsafe_allow_html=True,
    )

    stats = queue.get_queue_stats()
    by_level = stats.get("by_level", {})

    c1, c2, c3, c4 = st.columns(4)
    for col, num, label, clr in [
        (c1, stats.get("total_incoming", 0), "Total Incoming", "#1b2559"),
        (c2, by_level.get("EMERGENCY", 0), "🔴 Emergency", "#dc2626"),
        (c3, by_level.get("URGENT", 0), "🟠 Urgent", "#ea580c"),
        (c4, by_level.get("ROUTINE", 0), "🟢 Routine", "#16a34a"),
    ]:
        with col:
            st.markdown(
                f'<div class="stat-card"><div class="num" style="color:{clr}!important">{num}</div>'
                f'<div class="lbl">{label}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("")
    tab1, tab2, tab3 = st.tabs(["📥 Incoming", "📊 All Patients", "⚙️ Admin"])

    with tab1:
        patients = queue.get_incoming_patients(limit=20)
        if not patients:
            st.info("No incoming patients. Waiting for triage submissions…")
        else:
            for p in patients:
                render_patient(p)

    with tab2:
        all_p = queue.get_all_patients(limit=50)
        if not all_p:
            st.info("No records yet.")
        else:
            import pandas as pd
            df = pd.DataFrame(all_p)
            cols = ["patient_id", "triage_level", "chief_complaint", "risk_score",
                    "eta_minutes", "destination_hospital", "language", "status", "timestamp"]
            avail = [c for c in cols if c in df.columns]
            st.dataframe(df[avail], use_container_width=True, hide_index=True)

    with tab3:
        st.markdown("### Admin")
        if st.button("🗑 Clear All Records"):
            queue.clear_queue()
            st.success("Cleared.")
            st.rerun()
        st.markdown("---")
        if st.button("➕ Add Test Emergency"):
            from src.triage_engine import TriageEngine
            te = TriageEngine()
            r = te.create_patient_record(
                chief_complaint="Chest pain with left arm radiation and diaphoresis",
                assessment={
                    "triage_level": "EMERGENCY",
                    "assessment": "Findings: Pain radiates to arm; Sweating; Shortness of breath. 3 red flags. Triage: EMERGENCY.",
                    "red_flags": ["pain_radiation", "diaphoresis", "dyspnea"],
                    "recommended_action": "ER immediately.",
                    "risk_score": 9, "source_guidelines": ["chest_pain_protocol.txt"],
                    "suspected_conditions": ["Acute Coronary Syndrome"],
                    "time_sensitivity": "Within 10 minutes",
                },
                language="de-DE", eta_minutes=12,
            )
            r["destination_hospital"] = "Klinikum Stuttgart – Katharinenhospital (ER)"
            queue.add_patient(r)
            st.success(f"Added: {r['patient_id']}")
            st.rerun()

        if st.button("➕ Add Test Routine"):
            from src.triage_engine import TriageEngine
            te = TriageEngine()
            r = te.create_patient_record(
                chief_complaint="Mild headache for 2 days",
                assessment={
                    "triage_level": "ROUTINE",
                    "assessment": "Findings: Pain severity 3/10; No chronic conditions. 0 red flags. Triage: ROUTINE.",
                    "red_flags": ["none_identified"],
                    "recommended_action": "Self-care. See GP if persists.",
                    "risk_score": 2, "source_guidelines": ["general"],
                    "suspected_conditions": ["Tension Headache"],
                    "time_sensitivity": "Within 48 hours",
                },
                language="en-US", eta_minutes=30,
            )
            r["destination_hospital"] = "Robert-Bosch-Krankenhaus (ER)"
            queue.add_patient(r)
            st.success(f"Added: {r['patient_id']}")
            st.rerun()

    with st.sidebar:
        st.markdown("### 🏥 CodeZero ER")
        st.markdown("---")
        st.markdown("**Legend**")
        st.markdown("🔴 Emergency — Immediate")
        st.markdown("🟠 Urgent — 30 min")
        st.markdown("🟢 Routine — 2 hours")
        st.markdown("---")
        st.markdown("**Flow:** Incoming → Arrived → Treatment → Discharged")
        st.markdown("---")
        if st.button("🔄 Refresh"):
            st.rerun()


if __name__ == "__main__":
    main()