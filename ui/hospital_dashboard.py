"""
Hospital ER Dashboard — CodeZero
=================================
Professional emergency department command center.

Features:
  - Real-time patient queue with EMERGENCY / URGENT / ROUTINE priority lanes
  - Patient demographics (age, sex) displayed on each card
  - Photo indicator when patient submitted a wound photo
  - GPT-4 generated pre-arrival prep checklist per patient
  - Hospital occupancy control (Low / Medium / High / Full) per hospital
  - Occupancy affects patient routing score in maps_handler
  - Traffic-aware ETA via Azure Maps
  - Auto-refresh every 30 seconds

Run: streamlit run ui/hospital_dashboard.py --server.port 8502
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
from src.maps_handler import GERMANY_HOSPITALS, set_hospital_occupancy, get_hospital_occupancy, _OCCUPANCY_LABELS
from src.triage_engine import TRIAGE_COLORS, TRIAGE_EMERGENCY, TRIAGE_ROUTINE, TRIAGE_URGENT, TriageEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config — wide layout, dark professional theme via CSS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CodeZero ER Dashboard",
    page_icon="🏥",
    layout="wide",
)

st.markdown("""
<style>
/* ── Global ── */
.block-container { padding: 1rem 2rem 2rem 2rem; }
body { font-size: 0.95rem; }

/* ── Metric cards ── */
div[data-testid="stMetric"] {
    background: #1e293b;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    border-left: 4px solid #334155;
}
div[data-testid="stMetric"] label { color: #94a3b8 !important; font-size: 0.8rem !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 1.8rem !important; font-weight: 800 !important; color: #f1f5f9 !important;
}

/* ── Buttons ── */
.stButton > button { min-height: 40px; border-radius: 8px; font-weight: 600; }

/* ── Patient card containers ── */
.patient-card {
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
    border-left: 5px solid;
}
.card-emergency { border-color: #dc2626; background: #1a0505; }
.card-urgent    { border-color: #d97706; background: #1a0f00; }
.card-routine   { border-color: #16a34a; background: #001a07; }

/* ── Tab styling ── */
div[data-testid="stTabs"] button { font-weight: 600; font-size: 0.95rem; }

/* ── Selectbox ── */
div[data-testid="stSelectbox"] { max-width: 220px; }

/* ── Expander ── */
details summary { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cached shared instances
# ---------------------------------------------------------------------------

@st.cache_resource
def get_queue() -> HospitalQueue:
    return HospitalQueue()

@st.cache_resource
def get_triage_engine() -> TriageEngine:
    return TriageEngine()

hospital_queue = get_queue()
triage_engine  = get_triage_engine()

# Per-session prep cache: patient_id → list[str]
_PREP_CACHE: dict[str, list[str]] = {}

LEVEL_ICONS = {
    TRIAGE_EMERGENCY: "🔴",
    TRIAGE_URGENT:    "🟠",
    TRIAGE_ROUTINE:   "🟢",
}

LEVEL_LABELS = {
    TRIAGE_EMERGENCY: "EMERGENCY",
    TRIAGE_URGENT:    "URGENT",
    TRIAGE_ROUTINE:   "ROUTINE",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def minutes_until_arrival(iso_timestamp: str) -> str:
    if not iso_timestamp:
        return "N/A"
    try:
        arrival = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        delta   = (arrival - datetime.now(timezone.utc)).total_seconds() / 60
        return "ARRIVED" if delta <= 0 else f"{int(delta)} min"
    except Exception:
        return "N/A"


def _badge(text: str, color: str) -> str:
    """Return an HTML inline badge."""
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:6px;font-size:0.75rem;font-weight:700;">{text}</span>'
    )


# ---------------------------------------------------------------------------
# Patient card
# ---------------------------------------------------------------------------
def render_patient_card(patient: dict) -> None:
    level    = patient.get("triage_level", TRIAGE_URGENT)
    pid      = patient.get("patient_id", "UNKNOWN")
    status   = patient.get("status", "incoming")
    arrival  = patient.get("arrival_time")
    eta_raw  = patient.get("eta_minutes")
    countdown = minutes_until_arrival(arrival) if arrival else (f"~{eta_raw} min" if eta_raw else "N/A")

    # Demographics
    age_range = patient.get("age_range", "—")
    sex       = patient.get("sex", "—")
    lang      = patient.get("language", "en")

    # Red flags
    flags = [f.replace("_", " ").title() for f in patient.get("red_flags", []) if f != "none_identified"]

    # Photo indicator
    photo_badge = ' &nbsp;<span style="background:#7c3aed;color:#fff;padding:2px 7px;border-radius:6px;font-size:0.72rem;font-weight:700;">📷 PHOTO</span>' if patient.get("has_photo") else ""

    icon        = LEVEL_ICONS.get(level, "🟠")
    card_class  = {"EMERGENCY": "card-emergency", "URGENT": "card-urgent", "ROUTINE": "card-routine"}.get(level, "card-urgent")
    risk        = patient.get("risk_score", 5)

    st.markdown(f"""
<div class="patient-card {card_class}">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.4rem;">
    <div>
      <span style="font-size:1.05rem; font-weight:800;">{icon} {level} — {pid}</span>{photo_badge}
      &nbsp;&nbsp;
      <span style="color:#94a3b8; font-size:0.85rem;">⏱ {countdown}</span>
    </div>
    <div style="display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;">
      <span style="background:#334155;color:#cbd5e1;padding:2px 8px;border-radius:6px;font-size:0.78rem;">🧑 {age_range}</span>
      <span style="background:#334155;color:#cbd5e1;padding:2px 8px;border-radius:6px;font-size:0.78rem;">⚧ {sex}</span>
      <span style="background:#334155;color:#cbd5e1;padding:2px 8px;border-radius:6px;font-size:0.78rem;">🌍 {lang[:2].upper()}</span>
      <span style="background:#1e3a5f;color:#93c5fd;padding:2px 8px;border-radius:6px;font-size:0.78rem;">Risk {risk}/10</span>
    </div>
  </div>
  <p style="margin:0.5rem 0 0.2rem 0; color:#cbd5e1; font-size:0.95rem;">
    <strong>Complaint:</strong> {patient.get("chief_complaint", "")}
  </p>
  <p style="margin:0 0 0.3rem 0; color:#94a3b8; font-size:0.88rem;">
    {patient.get("assessment", "")[:200]}{"..." if len(patient.get("assessment","")) > 200 else ""}
  </p>
  {"<p style='margin:0;font-size:0.82rem;'>🚩 <strong>Red flags:</strong> " + " · ".join(flags[:5]) + "</p>" if flags else ""}
  {"<p style='margin:0.2rem 0 0;font-size:0.82rem;color:#94a3b8;'>🏥 " + patient.get("destination_hospital","") + "</p>" if patient.get("destination_hospital") else ""}
</div>
""", unsafe_allow_html=True)

    # ── GPT-4 Pre-arrival prep (only for incoming) ──
    if status == "incoming":
        with st.expander(f"📋 Pre-Arrival Prep — {pid}", expanded=(level == TRIAGE_EMERGENCY)):
            if pid not in _PREP_CACHE:
                with st.spinner("Generating prep checklist..."):
                    try:
                        _PREP_CACHE[pid] = triage_engine.generate_hospital_prep(
                            chief_complaint=patient.get("chief_complaint", "unknown"),
                            assessment=patient,
                        )
                    except Exception as exc:
                        logger.error("Prep generation failed for %s: %s", pid, exc)
                        _PREP_CACHE[pid] = [
                            "Assign appropriate bay",
                            "Alert attending physician",
                            "Prepare standard monitoring",
                        ]
            for item in _PREP_CACHE.get(pid, []):
                st.checkbox(item, key=f"prep_{pid}_{item[:30]}")

    # ── Status action buttons ──
    cols = st.columns([2, 2, 2, 2, 1])
    with cols[0]:
        if status == "incoming" and st.button("✅ Arrived", key=f"arrive_{pid}", use_container_width=True):
            hospital_queue.update_status(pid, "arrived")
            st.rerun()
    with cols[1]:
        if status == "arrived" and st.button("🩺 Treating", key=f"treat_{pid}", use_container_width=True):
            hospital_queue.update_status(pid, "in_treatment")
            st.rerun()
    with cols[2]:
        if status == "in_treatment" and st.button("🏠 Discharge", key=f"discharge_{pid}", use_container_width=True):
            hospital_queue.update_status(pid, "discharged")
            st.rerun()
    with cols[3]:
        if st.button("📄 Full Record", key=f"details_{pid}", use_container_width=True):
            with st.expander(f"Full JSON — {pid}", expanded=True):
                st.json(patient)
    with cols[4]:
        status_colors = {"incoming": "#d97706", "arrived": "#2563eb", "in_treatment": "#7c3aed", "discharged": "#16a34a"}
        st.markdown(
            f'<div style="background:{status_colors.get(status,"#334155")};color:#fff;'
            f'padding:6px 10px;border-radius:8px;font-size:0.78rem;font-weight:700;text-align:center;">'
            f'{status.replace("_"," ").upper()}</div>',
            unsafe_allow_html=True,
        )

    st.divider()


# ---------------------------------------------------------------------------
# All patients table
# ---------------------------------------------------------------------------
def render_all_patients_table(patients: list[dict]) -> None:
    if not patients:
        st.info("No patient records yet.")
        return
    try:
        import pandas as pd
        df = pd.DataFrame(patients)
        cols = ["patient_id", "triage_level", "chief_complaint", "age_range", "sex",
                "risk_score", "eta_minutes", "destination_hospital", "language", "status", "timestamp"]
        available = [c for c in cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
    except Exception as exc:
        logger.error("DataFrame render error: %s", exc)
        for p in patients:
            st.write(p)


# ---------------------------------------------------------------------------
# Occupancy management tab
# ---------------------------------------------------------------------------
def render_occupancy_tab() -> None:
    st.subheader("🏥 Hospital Occupancy Control")
    st.caption(
        "Set current ER occupancy for each hospital. "
        "Occupancy affects patient routing — full hospitals are deprioritised."
    )

    # Filter hospitals by Bundesland for easier navigation
    bundeslaender = {
        "Baden-Württemberg": ["Stuttgart", "Tübingen", "Freiburg", "Karlsruhe", "Heidelberg", "Mannheim", "Aalen", "Heilbronn", "Schwenningen", "Konstanz", "Reutlingen", "Esslingen", "Ludwigsburg", "Friedrichshafen", "Offenburg", "Pforzheim"],
        "Bayern": ["München", "Augsburg", "Würzburg", "Erlangen", "Nürnberg", "Regensburg", "Landshut", "Rosenheim", "Ingolstadt", "Passau", "Bayreuth", "Coburg", "Bamberg", "Memmingen", "Kaufbeuren"],
        "Berlin": ["Berlin"],
        "Brandenburg": ["Brandenburg", "Potsdam", "Frankfurt (Oder)"],
        "Bremen": ["Bremen"],
        "Hamburg": ["Hamburg"],
        "Hessen": ["Frankfurt", "Marburg", "Kassel", "Wiesbaden", "Darmstadt", "Offenbach"],
        "Mecklenburg-Vorpommern": ["Greifswald", "Rostock", "Schwerin"],
        "Niedersachsen": ["Hannover", "Braunschweig", "Oldenburg", "Osnabrück", "Wolfsburg", "Hildesheim", "Göttingen"],
        "Nordrhein-Westfalen": ["Köln", "Düsseldorf", "Essen", "Bochum", "Münster", "Bonn", "Dortmund", "Bielefeld", "Aachen", "Wuppertal", "Leverkusen", "Duisburg", "Gelsenkirchen", "Gütersloh", "Minden", "Solingen", "Krefeld", "Hamm"],
        "Rheinland-Pfalz": ["Mainz", "Kaiserslautern", "Koblenz", "Ludwigshafen", "Trier"],
        "Saarland": ["Homburg", "Saarbrücken"],
        "Sachsen": ["Leipzig", "Dresden", "Chemnitz", "Zwickau", "Görlitz"],
        "Sachsen-Anhalt": ["Halle", "Magdeburg", "Dessau"],
        "Schleswig-Holstein": ["Kiel", "Lübeck", "Schleswig", "Rendsburg"],
        "Thüringen": ["Jena", "Erfurt", "Suhl", "Gera"],
    }

    selected_land = st.selectbox("Filter by Bundesland", ["All"] + list(bundeslaender.keys()))

    # Filter hospital list
    if selected_land == "All":
        hospitals_to_show = GERMANY_HOSPITALS
    else:
        keywords = bundeslaender.get(selected_land, [])
        hospitals_to_show = [
            h for h in GERMANY_HOSPITALS
            if any(kw in h["name"] or kw in h["address"] for kw in keywords)
        ]

    st.markdown(f"**{len(hospitals_to_show)} hospitals** — select occupancy level:")
    st.markdown("")

    occupancy_options = ["low", "medium", "high", "full"]
    icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "full": "🔴"}
    penalty_labels = {"low": "+0 min", "medium": "+10 min", "high": "+25 min", "full": "+60 min"}

    for h in hospitals_to_show:
        name    = h["name"]
        current = get_hospital_occupancy(name)
        c1, c2  = st.columns([3, 1])
        with c1:
            new_level = st.select_slider(
                f"{name}",
                options=occupancy_options,
                value=current,
                key=f"occ_{name[:40]}",
                format_func=lambda x: f"{icons[x]} {x.capitalize()} ({penalty_labels[x]})",
            )
        with c2:
            st.markdown(
                f'<div style="margin-top:1.8rem;font-size:0.8rem;color:#94a3b8;">'
                f'{h["address"].split(",")[-1].strip()}</div>',
                unsafe_allow_html=True,
            )
        if new_level != current:
            set_hospital_occupancy(name, new_level)


# ---------------------------------------------------------------------------
# Admin / test tools
# ---------------------------------------------------------------------------
def _add_test_emergency() -> None:
    record = triage_engine.create_patient_record(
        chief_complaint="Severe chest pain with arm radiation and sweating",
        assessment={
            "triage_level": TRIAGE_EMERGENCY,
            "assessment": "3 red flags: pain radiation, diaphoresis, dyspnea. Possible ACS.",
            "red_flags": ["pain_radiation", "diaphoresis", "dyspnea"],
            "recommended_action": "Proceed to ER immediately — activate cath lab.",
            "risk_score": 9,
            "source_guidelines": ["chest_pain_protocol.txt"],
            "suspected_conditions": ["Acute Coronary Syndrome"],
            "time_sensitivity": "Within 10 minutes",
        },
        language="de-DE",
        eta_minutes=12,
        demographics={"age_range": "45-59", "sex": "Male"},
    )
    record["destination_hospital"] = "Klinikum Stuttgart – Katharinenhospital"
    hospital_queue.add_patient(record)
    st.success(f"Added EMERGENCY: {record['patient_id']}")


def _add_test_urgent() -> None:
    record = triage_engine.create_patient_record(
        chief_complaint="Sudden severe headache and vomiting for 2 hours",
        assessment={
            "triage_level": TRIAGE_URGENT,
            "assessment": "Thunderclap headache — subarachnoid haemorrhage must be excluded.",
            "red_flags": ["thunderclap_headache", "vomiting"],
            "recommended_action": "Urgent CT head within 30 minutes.",
            "risk_score": 7,
            "source_guidelines": [],
            "suspected_conditions": ["Subarachnoid Haemorrhage", "Migraine"],
            "time_sensitivity": "Within 30 minutes",
        },
        language="tr-TR",
        eta_minutes=22,
        demographics={"age_range": "30-44", "sex": "Female"},
    )
    record["destination_hospital"] = "Robert-Bosch-Krankenhaus Stuttgart"
    hospital_queue.add_patient(record)
    st.success(f"Added URGENT: {record['patient_id']}")


def _add_test_routine() -> None:
    record = triage_engine.create_patient_record(
        chief_complaint="Mild headache for 2 days, no fever",
        assessment={
            "triage_level": TRIAGE_ROUTINE,
            "assessment": "Pain 3/10. No red flags. Tension headache likely.",
            "red_flags": ["none_identified"],
            "recommended_action": "See GP if symptoms persist beyond 48 hours.",
            "risk_score": 2,
            "source_guidelines": [],
            "suspected_conditions": ["Tension Headache"],
            "time_sensitivity": "Within 48 hours",
        },
        language="en-US",
        eta_minutes=45,
        demographics={"age_range": "18-29", "sex": "Female"},
    )
    record["destination_hospital"] = "Universitätsklinikum Tübingen"
    hospital_queue.add_patient(record)
    st.success(f"Added ROUTINE: {record['patient_id']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    now_str = datetime.now(timezone.utc).strftime("%d %b %Y — %H:%M UTC")

    # ── Header ──
    col_title, col_time = st.columns([4, 1])
    with col_title:
        st.markdown("## 🏥 CodeZero — ER Command Center")
    with col_time:
        st.markdown(
            f'<div style="text-align:right;padding-top:0.6rem;color:#64748b;font-size:0.85rem;">{now_str}</div>',
            unsafe_allow_html=True,
        )

    # ── Summary metrics ──
    stats    = hospital_queue.get_queue_stats()
    by_level = stats.get("by_level", {})

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📥 Total Incoming",  stats.get("total_incoming", 0))
    m2.metric("🔴 Emergency",       by_level.get(TRIAGE_EMERGENCY, 0))
    m3.metric("🟠 Urgent",          by_level.get(TRIAGE_URGENT, 0))
    m4.metric("🟢 Routine",         by_level.get(TRIAGE_ROUTINE, 0))
    m5.metric("✅ Treated Today",   stats.get("total_treated", stats.get("total_discharged", 0)))

    st.divider()

    # ── Tabs ──
    tab_incoming, tab_all, tab_occupancy, tab_admin = st.tabs([
        "📥 Incoming Patients",
        "📊 All Records",
        "🏥 Occupancy Control",
        "⚙️ Admin",
    ])

    with tab_incoming:
        incoming = hospital_queue.get_incoming_patients(limit=20)
        if not incoming:
            st.markdown("""
<div style="text-align:center;padding:3rem;color:#475569;">
  <div style="font-size:3rem;">🏥</div>
  <p style="font-size:1.1rem;">No incoming patients.<br>Waiting for triage submissions...</p>
</div>""", unsafe_allow_html=True)
        else:
            # ── Sort controls ──────────────────────────────────────────────
            sort_col, _ = st.columns([2, 3])
            with sort_col:
                sort_mode = st.selectbox(
                    "Sort by",
                    options=["newest_first", "by_category", "by_eta"],
                    format_func=lambda x: {
                        "newest_first": "🕐 Newest first",
                        "by_category":  "🔴 Category (Emergency → Routine)",
                        "by_eta":       "⏱ Arrival time (soonest first)",
                    }[x],
                    key="sort_mode",
                    label_visibility="collapsed",
                )

            priority_order = {TRIAGE_EMERGENCY: 0, TRIAGE_URGENT: 1, TRIAGE_ROUTINE: 2}

            if sort_mode == "newest_first":
                # Most recently submitted first (reverse insertion order)
                sorted_patients = list(reversed(incoming))
            elif sort_mode == "by_category":
                # EMERGENCY → URGENT → ROUTINE, then newest within each group
                sorted_patients = sorted(
                    incoming,
                    key=lambda p: (
                        priority_order.get(p.get("triage_level", TRIAGE_URGENT), 1),
                        # within same category: newest first (reverse timestamp)
                        -(p.get("timestamp", "") or ""),
                    ),
                )
            else:  # by_eta
                sorted_patients = sorted(
                    incoming,
                    key=lambda p: p.get("eta_minutes", 999),
                )

            for patient in sorted_patients:
                render_patient_card(patient)

    with tab_all:
        all_patients = hospital_queue.get_all_patients(limit=100)
        render_all_patients_table(all_patients)

    with tab_occupancy:
        render_occupancy_tab()

    with tab_admin:
        st.subheader("⚙️ Admin Tools")

        with st.expander("Add Test Patients", expanded=True):
            a1, a2, a3 = st.columns(3)
            with a1:
                if st.button("➕ Add Emergency", use_container_width=True, type="primary"):
                    _add_test_emergency(); st.rerun()
            with a2:
                if st.button("➕ Add Urgent", use_container_width=True):
                    _add_test_urgent(); st.rerun()
            with a3:
                if st.button("➕ Add Routine", use_container_width=True):
                    _add_test_routine(); st.rerun()

        st.divider()
        if st.button("🗑 Clear All Records", type="secondary"):
            hospital_queue.clear_queue()
            st.success("Queue cleared.")
            st.rerun()

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("### 🏥 CodeZero ER")
        st.divider()
        st.markdown("**Priority Levels**")
        st.markdown("🔴 **Emergency** — Immediate (< 10 min)")
        st.markdown("🟠 **Urgent** — Within 30 min")
        st.markdown("🟢 **Routine** — Within 2 hours")
        st.divider()
        st.markdown("**Status Workflow**")
        st.markdown("📥 Incoming → ✅ Arrived → 🩺 Treating → 🏠 Discharged")
        st.divider()
        st.markdown("**Occupancy Penalties**")
        st.markdown("🟢 Low — +0 min to ETA score")
        st.markdown("🟡 Medium — +10 min")
        st.markdown("🟠 High — +25 min")
        st.markdown("🔴 Full — +60 min (last resort)")
        st.divider()

        if st.button("🔄 Refresh", use_container_width=True, type="primary"):
            st.rerun()


if __name__ == "__main__":
    main()