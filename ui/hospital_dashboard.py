"""
Hospital ER Dashboard — CodeZero
Fixes:
  1. Duplicate key  → hashlib MD5 per hospital name (never truncates)
  2. Demographics   → age_range / sex always shown on card + detail panel
  3. Photo          → photo badge on card + detail block inside expander
  4. Sort TypeError → no string negation, groupby approach
  5. Modern design  → postvisit.ai inspired expandable detail panel
  6. Auto-refresh   → removed (manual only)
"""
from __future__ import annotations
import hashlib, logging, sys
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue
from src.maps_handler import GERMANY_HOSPITALS, set_hospital_occupancy, get_hospital_occupancy
from src.triage_engine import TRIAGE_EMERGENCY, TRIAGE_ROUTINE, TRIAGE_URGENT, TriageEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="CodeZero ER", page_icon="🏥", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { font-family: 'Inter', sans-serif; }
.block-container { padding: 1.2rem 2.2rem 2rem 2.2rem !important; }

div[data-testid="stMetric"] {
  background: #111827; border-radius: 12px;
  padding: 1rem 1.2rem; border: 1px solid #1f2937;
}
div[data-testid="stMetric"] label {
  color: #6b7280 !important; font-size: 0.7rem !important;
  text-transform: uppercase; letter-spacing: 0.08em;
}
div[data-testid="stMetricValue"] {
  font-size: 2rem !important; font-weight: 800 !important; color: #f9fafb !important;
}
div[data-testid="stTabs"] button { font-weight: 600; font-size: 0.9rem; }
.stButton > button { border-radius: 8px; font-weight: 600; font-size: 0.85rem; min-height: 36px; }

.cz-card {
  border-radius: 14px; padding: 1rem 1.2rem;
  margin-bottom: 6px; border: 1px solid #1f2937;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.cz-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
.cz-e { border-left: 4px solid #ef4444; background: linear-gradient(135deg,#1c0a0a,#111827); }
.cz-u { border-left: 4px solid #f59e0b; background: linear-gradient(135deg,#1c1000,#111827); }
.cz-r { border-left: 4px solid #10b981; background: linear-gradient(135deg,#001c0f,#111827); }

.bx {
  display:inline-flex; align-items:center; padding: 3px 9px;
  border-radius: 20px; font-size: 0.72rem; font-weight: 600;
  margin: 2px 3px 2px 0; white-space: nowrap;
}

.dp {
  background: #0d1117; border: 1px solid #21262d;
  border-radius: 12px; padding: 1.2rem 1.4rem; margin: 4px 0 8px 0;
}
.dp-section { margin-bottom: 1rem; }
.dp-section:last-child { margin-bottom: 0; }
.dp-title {
  font-size: 0.68rem; color: #4b5563; text-transform: uppercase;
  letter-spacing: 0.1em; font-weight: 700; margin-bottom: 0.5rem;
  padding-bottom: 0.4rem; border-bottom: 1px solid #1f2937;
}
.dp-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:0.8rem; }
.dp-field-label { font-size: 0.68rem; color: #6b7280; margin-bottom: 3px; }
.dp-field-value { font-size: 0.9rem; font-weight: 600; color: #e5e7eb; }

div[data-testid="stExpander"] {
  border: 1px solid #1f2937 !important; border-radius: 10px !important;
  background: #0d1117 !important; margin-bottom: 4px;
}
details > summary p { font-size: 0.88rem !important; color: #9ca3af !important; }
</style>
""", unsafe_allow_html=True)

# ── Services ──────────────────────────────────────────────────────────────────
@st.cache_resource
def _queue() -> HospitalQueue: return HospitalQueue()

@st.cache_resource
def _engine() -> TriageEngine: return TriageEngine()

hospital_queue = _queue()
triage_engine  = _engine()
_PREP_CACHE: dict[str, list[str]] = {}

ICONS  = {TRIAGE_EMERGENCY: "🔴", TRIAGE_URGENT: "🟠", TRIAGE_ROUTINE: "🟢"}
COLORS = {TRIAGE_EMERGENCY: "#ef4444", TRIAGE_URGENT: "#f59e0b", TRIAGE_ROUTINE: "#10b981"}
CARD   = {TRIAGE_EMERGENCY: "cz-e", TRIAGE_URGENT: "cz-u", TRIAGE_ROUTINE: "cz-r"}
PORDER = {TRIAGE_EMERGENCY: 0, TRIAGE_URGENT: 1, TRIAGE_ROUTINE: 2}


def _hkey(prefix: str, s: str) -> str:
    """Unique Streamlit key via MD5 — safe for any unicode hospital name."""
    return f"{prefix}_{hashlib.md5(s.encode()).hexdigest()[:10]}"


def _eta_str(arrival_iso, eta_raw) -> str:
    if arrival_iso:
        try:
            d = (datetime.fromisoformat(str(arrival_iso).replace("Z", "+00:00"))
                 - datetime.now(timezone.utc)).total_seconds() / 60
            return "ARRIVED" if d <= 0 else f"{int(d)} min"
        except Exception:
            pass
    return f"~{eta_raw} min" if eta_raw else "N/A"


# ── Detail panel HTML builder (no nested f-strings) ───────────────────────────
def _build_detail_html(p: dict) -> str:
    lvl        = p.get("triage_level", TRIAGE_URGENT)
    pid        = p.get("patient_id", "UNKNOWN")
    age        = p.get("age_range") or "—"
    sex        = p.get("sex") or "—"
    lang       = (p.get("language") or "en")[:5].upper()
    risk       = p.get("risk_score", 5)
    comp       = p.get("chief_complaint", "")
    asmt       = p.get("assessment", "")
    flags      = [f.replace("_", " ").title() for f in p.get("red_flags", []) if f != "none_identified"]
    conds      = p.get("suspected_conditions", [])
    dest       = p.get("destination_hospital", "")
    has_photo  = bool(p.get("has_photo"))
    photo_note = p.get("photo_note", "Patient submitted a wound/symptom photo")
    rec_action = p.get("recommended_action", "")
    time_sens  = p.get("time_sensitivity", "")
    src_gl     = ", ".join(p.get("source_guidelines", []))
    ts         = (p.get("timestamp", "")[:16] or "").replace("T", " ")
    eta        = _eta_str(p.get("arrival_time"), p.get("eta_minutes"))
    clr        = COLORS.get(lvl, "#f59e0b")
    risk_clr   = "#ef4444" if risk >= 8 else "#f59e0b" if risk >= 5 else "#10b981"
    icon       = ICONS.get(lvl, "🟠")

    # Build optional sections as strings
    flags_html = ""
    if flags:
        badges = "".join(
            '<span class="bx" style="background:#ef444422;color:#fca5a5;border:1px solid #ef444455;">'
            + f + "</span>"
            for f in flags
        )
        flags_html = (
            '<div class="dp-section">'
            '<div class="dp-title">🚩 Red Flags</div>'
            '<div style="display:flex;flex-wrap:wrap;gap:5px;">' + badges + "</div>"
            "</div>"
        )

    conds_html = ""
    if conds:
        conds_html = (
            '<div class="dp-grid"><div>'
            '<div class="dp-field-label">Suspected Conditions</div>'
            '<div class="dp-field-value" style="color:#93c5fd;">' + " · ".join(conds) + "</div>"
            "</div></div>"
        )

    actions_html = ""
    if rec_action:
        actions_html = (
            '<div class="dp-section">'
            '<div class="dp-title">📋 Actions</div>'
            '<div class="dp-grid">'
            '<div><div class="dp-field-label">Recommended Action</div>'
            '<div class="dp-field-value">' + rec_action + "</div></div>"
            '<div><div class="dp-field-label">Time Sensitivity</div>'
            '<div class="dp-field-value" style="color:' + clr + ';">' + time_sens + "</div></div>"
            "</div></div>"
        )

    photo_html = ""
    if has_photo:
        photo_html = (
            '<div class="dp-section">'
            '<div class="dp-title">📷 Photo Attachment</div>'
            '<p style="color:#a78bfa;font-size:0.87rem;margin:0;">' + photo_note + "</p>"
            "</div>"
        )

    dest_html = ""
    if dest:
        dest_html = (
            '<div class="dp-section">'
            '<div class="dp-title">🏥 Destination Hospital</div>'
            '<p style="color:#e5e7eb;font-size:0.9rem;font-weight:600;margin:0;">' + dest + "</p>"
            "</div>"
        )

    src_html = ""
    if src_gl:
        src_html = (
            '<div class="dp-section">'
            '<div class="dp-title">📚 Source Guidelines</div>'
            '<p style="color:#6b7280;font-size:0.82rem;margin:0;">' + src_gl + "</p>"
            "</div>"
        )

    return (
        '<div class="dp">'

        # Header
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'margin-bottom:1rem;padding-bottom:0.8rem;border-bottom:1px solid #21262d;flex-wrap:wrap;gap:6px;">'
        '<div>'
        '<span style="font-size:1.05rem;font-weight:800;color:#f9fafb;">' + icon + " " + lvl + "</span>"
        '<span style="color:#4b5563;font-size:0.9rem;margin-left:8px;">' + pid + "</span>"
        "</div>"
        '<div style="display:flex;gap:6px;flex-wrap:wrap;">'
        '<span class="bx" style="background:' + risk_clr + '22;color:' + risk_clr + ';border:1px solid ' + risk_clr + '55;">Risk ' + str(risk) + "/10</span>"
        '<span class="bx" style="background:#1f2937;color:#9ca3af;border:1px solid #374151;">Submitted ' + ts + "</span>"
        "</div></div>"

        # Demographics
        '<div class="dp-section">'
        '<div class="dp-title">👤 Patient Demographics</div>'
        '<div class="dp-grid">'
        '<div><div class="dp-field-label">Age Range</div><div class="dp-field-value">' + age + "</div></div>"
        '<div><div class="dp-field-label">Biological Sex</div><div class="dp-field-value">' + sex + "</div></div>"
        '<div><div class="dp-field-label">Language</div><div class="dp-field-value">' + lang + "</div></div>"
        '<div><div class="dp-field-label">ETA</div><div class="dp-field-value" style="color:' + clr + ';">' + eta + "</div></div>"
        "</div></div>"

        # Complaint
        '<div class="dp-section">'
        '<div class="dp-title">🗣️ Chief Complaint</div>'
        '<p style="color:#e5e7eb;font-size:0.92rem;margin:0;font-weight:500;">' + comp + "</p>"
        "</div>"

        # Assessment
        '<div class="dp-section">'
        '<div class="dp-title">🩺 Clinical Assessment</div>'
        '<p style="color:#d1d5db;font-size:0.87rem;margin:0 0 0.7rem;line-height:1.6;">' + asmt + "</p>"
        + conds_html +
        "</div>"

        + flags_html
        + actions_html
        + photo_html
        + dest_html
        + src_html
        + "</div>"
    )


# ── Patient card ──────────────────────────────────────────────────────────────
def render_patient_card(p: dict) -> None:
    lvl       = p.get("triage_level", TRIAGE_URGENT)
    pid       = p.get("patient_id", "UNKNOWN")
    stat      = p.get("status", "incoming")
    eta       = _eta_str(p.get("arrival_time"), p.get("eta_minutes"))
    age       = p.get("age_range") or "—"
    sex       = p.get("sex") or "—"
    lang      = (p.get("language") or "en")[:5].upper()
    risk      = p.get("risk_score", 5)
    comp      = p.get("chief_complaint", "")
    asmt      = p.get("assessment", "")
    flags     = [f.replace("_", " ").title() for f in p.get("red_flags", []) if f != "none_identified"]
    dest      = p.get("destination_hospital", "")
    has_photo = bool(p.get("has_photo"))

    clr      = COLORS.get(lvl, "#f59e0b")
    risk_clr = "#ef4444" if risk >= 8 else "#f59e0b" if risk >= 5 else "#10b981"
    stat_bg  = {"incoming": "#92400e", "arrived": "#1e3a5f", "in_treatment": "#4c1d95", "discharged": "#14532d"}.get(stat, "#374151")

    photo_bx  = '<span class="bx" style="background:#5b21b644;color:#a78bfa;border:1px solid #7c3aed;">📷 PHOTO</span>' if has_photo else ""
    flags_row = ""
    if flags:
        flags_row = "<p style='margin:0.2rem 0 0;font-size:0.79rem;'><span style='color:#ef4444;'>🚩</span> <span style='color:#fca5a5;'>" + " · ".join(flags[:4]) + "</span></p>"
    dest_row = "<p style='margin:0.15rem 0 0;font-size:0.79rem;color:#4b5563;'>🏥 " + dest + "</p>" if dest else ""

    st.markdown(
        '<div class="cz-card ' + CARD.get(lvl, "cz-u") + '">'
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;">'
        '<span style="font-size:1rem;font-weight:800;color:#f9fafb;">' + ICONS.get(lvl, "🟠") + " " + lvl + "</span>"
        '<span style="color:#4b5563;font-size:0.88rem;font-weight:500;">— ' + pid + "</span>"
        '<span class="bx" style="background:' + stat_bg + '44;color:#e5e7eb;border:1px solid ' + stat_bg + ';">' + stat.replace("_", " ").upper() + "</span>"
        + photo_bx +
        "</div>"
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:5px;">'
        '<span class="bx" style="background:#1f293799;color:#9ca3af;border:1px solid #374151;">🧑 ' + age + "</span>"
        '<span class="bx" style="background:#1f293799;color:#9ca3af;border:1px solid #374151;">⚧ ' + sex + "</span>"
        '<span class="bx" style="background:#1f293799;color:#9ca3af;border:1px solid #374151;">🌐 ' + lang + "</span>"
        '<span class="bx" style="background:' + risk_clr + '22;color:' + risk_clr + ';border:1px solid ' + risk_clr + '55;">⚡ ' + str(risk) + "/10</span>"
        '<span style="color:#6b7280;font-size:0.8rem;">⏱ ' + eta + "</span>"
        "</div></div>"
        "<p style='margin:0.5rem 0 0.15rem;color:#6b7280;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;'>Complaint</p>"
        "<p style='margin:0 0 0.25rem;color:#f3f4f6;font-size:0.93rem;font-weight:600;'>" + comp + "</p>"
        "<p style='margin:0 0 0.2rem;color:#6b7280;font-size:0.83rem;line-height:1.45;'>" + asmt[:180] + ("…" if len(asmt) > 180 else "") + "</p>"
        + flags_row + dest_row +
        "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("🔍 Full Record — " + pid):
        st.markdown(_build_detail_html(p), unsafe_allow_html=True)

    if stat == "incoming":
        with st.expander("🏥 Pre-Arrival Prep — " + pid, expanded=(lvl == TRIAGE_EMERGENCY)):
            if pid not in _PREP_CACHE:
                with st.spinner("Generating checklist..."):
                    try:
                        _PREP_CACHE[pid] = triage_engine.generate_hospital_prep(
                            chief_complaint=p.get("chief_complaint", "unknown"),
                            assessment=p,
                        )
                    except Exception as exc:
                        logger.error("Prep failed %s: %s", pid, exc)
                        _PREP_CACHE[pid] = ["Assign appropriate bay", "Alert attending physician", "Prepare standard monitoring"]
            for item in _PREP_CACHE.get(pid, []):
                st.checkbox(item, key=_hkey("prep_" + pid, item))

    c1, c2, c3, _ = st.columns([2, 2, 2, 3])
    with c1:
        if stat == "incoming" and st.button("✅ Arrived", key="arr_" + pid, use_container_width=True):
            hospital_queue.update_status(pid, "arrived"); st.rerun()
    with c2:
        if stat == "arrived" and st.button("🩺 Treating", key="trt_" + pid, use_container_width=True):
            hospital_queue.update_status(pid, "in_treatment"); st.rerun()
    with c3:
        if stat == "in_treatment" and st.button("🏠 Discharge", key="dis_" + pid, use_container_width=True):
            hospital_queue.update_status(pid, "discharged"); st.rerun()

    st.markdown("<div style='margin-bottom:0.4rem'></div>", unsafe_allow_html=True)


# ── All records ───────────────────────────────────────────────────────────────
def render_all_table(patients: list[dict]) -> None:
    if not patients:
        st.info("No records yet."); return
    try:
        import pandas as pd
        df   = pd.DataFrame(patients)
        cols = ["patient_id", "triage_level", "chief_complaint", "age_range", "sex",
                "risk_score", "eta_minutes", "destination_hospital", "language", "status", "timestamp"]
        st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)
    except Exception as e:
        logger.error(e)
        for p in patients:
            st.write(p)


# ── Occupancy ─────────────────────────────────────────────────────────────────
def render_occupancy_tab() -> None:
    st.subheader("🏥 Hospital Occupancy Control")
    st.caption("Occupancy is added as routing penalty (full = +60 min).")

    bl: dict[str, list[str]] = {
        "All": [],
        "Baden-Württemberg": ["Stuttgart","Tübingen","Freiburg","Karlsruhe","Heidelberg","Mannheim","Aalen","Heilbronn","Schwenningen","Konstanz","Reutlingen","Esslingen","Ludwigsburg","Friedrichshafen","Offenburg","Pforzheim"],
        "Bayern": ["München","Augsburg","Würzburg","Erlangen","Nürnberg","Regensburg","Landshut","Rosenheim","Ingolstadt","Passau","Bayreuth","Coburg","Bamberg","Memmingen","Kaufbeuren"],
        "Berlin": ["Berlin"],
        "Brandenburg": ["Brandenburg","Potsdam","Frankfurt (Oder)"],
        "Bremen": ["Bremen"],
        "Hamburg": ["Hamburg"],
        "Hessen": ["Frankfurt","Marburg","Kassel","Wiesbaden","Darmstadt","Offenbach"],
        "Mecklenburg-Vorpommern": ["Greifswald","Rostock","Schwerin"],
        "Niedersachsen": ["Hannover","Braunschweig","Oldenburg","Osnabrück","Wolfsburg","Hildesheim","Göttingen"],
        "NRW": ["Köln","Düsseldorf","Essen","Bochum","Münster","Bonn","Dortmund","Bielefeld","Aachen","Wuppertal","Leverkusen","Duisburg","Gelsenkirchen","Gütersloh","Minden","Solingen","Krefeld","Hamm"],
        "Rheinland-Pfalz": ["Mainz","Kaiserslautern","Koblenz","Ludwigshafen","Trier"],
        "Saarland": ["Homburg","Saarbrücken"],
        "Sachsen": ["Leipzig","Dresden","Chemnitz","Zwickau","Görlitz"],
        "Sachsen-Anhalt": ["Halle","Magdeburg","Dessau"],
        "Schleswig-Holstein": ["Kiel","Lübeck","Schleswig","Rendsburg"],
        "Thüringen": ["Jena","Erfurt","Suhl","Gera"],
    }

    sel  = st.selectbox("Bundesland", list(bl.keys()), key="occ_bl")
    show = GERMANY_HOSPITALS if sel == "All" else [
        h for h in GERMANY_HOSPITALS if any(k in h["name"] or k in h["address"] for k in bl[sel])
    ]
    st.caption(str(len(show)) + " hospitals shown")

    opts  = ["low", "medium", "high", "full"]
    icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "full": "🔴"}
    pen   = {"low": "+0 min", "medium": "+10 min", "high": "+25 min", "full": "+60 min"}

    for h in show:
        name = h["name"]
        cur  = get_hospital_occupancy(name)
        key  = _hkey("occ", name)   # MD5 hash → always unique, never truncated
        c1, c2 = st.columns([4, 1])
        with c1:
            nv = st.select_slider(
                name, options=opts, value=cur, key=key,
                format_func=lambda x: icons[x] + " " + x.capitalize() + "  (" + pen[x] + ")",
                label_visibility="visible",
            )
        with c2:
            city = h["address"].split(",")[-1].strip()
            st.markdown('<div style="padding-top:1.7rem;font-size:0.75rem;color:#4b5563;">' + city + "</div>", unsafe_allow_html=True)
        if nv != cur:
            set_hospital_occupancy(name, nv)


# ── Test helpers ──────────────────────────────────────────────────────────────
def _mk(complaint, asmt_dict, lang, eta, demographics, dest):
    r = triage_engine.create_patient_record(
        chief_complaint=complaint, assessment=asmt_dict,
        language=lang, eta_minutes=eta, demographics=demographics,
    )
    r["destination_hospital"] = dest
    hospital_queue.add_patient(r)
    return r["patient_id"]

def _add_emergency():
    pid = _mk("Severe chest pain with arm radiation and sweating",
        {"triage_level": TRIAGE_EMERGENCY, "assessment": "3 red flags: radiation, diaphoresis, dyspnea. Possible ACS.",
         "red_flags": ["pain_radiation","diaphoresis","dyspnea"], "recommended_action": "Activate cath lab immediately.",
         "risk_score": 9, "source_guidelines": ["chest_pain_protocol.txt"],
         "suspected_conditions": ["Acute Coronary Syndrome"], "time_sensitivity": "Within 10 minutes"},
        "de-DE", 12, {"age_range": "45-59", "sex": "Male"}, "Klinikum Stuttgart – Katharinenhospital")
    st.success("Added EMERGENCY: " + pid)

def _add_urgent():
    pid = _mk("Sudden severe headache and vomiting for 2 hours",
        {"triage_level": TRIAGE_URGENT, "assessment": "Thunderclap headache — SAH must be excluded.",
         "red_flags": ["thunderclap_headache","vomiting"], "recommended_action": "CT head within 30 minutes.",
         "risk_score": 7, "source_guidelines": [], "suspected_conditions": ["SAH","Migraine"],
         "time_sensitivity": "Within 30 minutes"},
        "tr-TR", 22, {"age_range": "30-44", "sex": "Female"}, "Robert-Bosch-Krankenhaus Stuttgart")
    st.success("Added URGENT: " + pid)

def _add_routine():
    pid = _mk("Mild headache for 2 days, no fever",
        {"triage_level": TRIAGE_ROUTINE, "assessment": "Pain 3/10. No red flags. Tension headache.",
         "red_flags": ["none_identified"], "recommended_action": "See GP if persists 48h.",
         "risk_score": 2, "source_guidelines": [], "suspected_conditions": ["Tension Headache"],
         "time_sensitivity": "Within 48 hours"},
        "en-US", 45, {"age_range": "18-29", "sex": "Female"}, "Universitätsklinikum Tübingen")
    st.success("Added ROUTINE: " + pid)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    now_str = datetime.now(timezone.utc).strftime("%d %b %Y  %H:%M UTC")

    h1, h2 = st.columns([6, 1])
    with h1:
        st.markdown("## 🏥 CodeZero — ER Command Center")
    with h2:
        st.markdown('<div style="text-align:right;padding-top:0.8rem;color:#4b5563;font-size:0.8rem;">' + now_str + "</div>", unsafe_allow_html=True)

    stats = hospital_queue.get_queue_stats()
    by_lv = stats.get("by_level", {})
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("📥 Incoming",  stats.get("total_incoming", 0))
    m2.metric("🔴 Emergency", by_lv.get(TRIAGE_EMERGENCY, 0))
    m3.metric("🟠 Urgent",    by_lv.get(TRIAGE_URGENT, 0))
    m4.metric("🟢 Routine",   by_lv.get(TRIAGE_ROUTINE, 0))
    m5.metric("✅ Treated",   stats.get("total_treated", stats.get("total_discharged", 0)))
    st.divider()

    t_in, t_all, t_occ, t_adm = st.tabs(["📥 Incoming", "📊 All Records", "🏥 Occupancy", "⚙️ Admin"])

    with t_in:
        incoming = hospital_queue.get_incoming_patients(limit=40)
        if not incoming:
            st.markdown('<div style="text-align:center;padding:3rem;color:#4b5563;"><div style="font-size:3rem;">🏥</div><p>No incoming patients yet.</p></div>', unsafe_allow_html=True)
        else:
            sc, _ = st.columns([2, 5])
            with sc:
                sm = st.selectbox("Sort", ["newest_first","by_category","by_eta"],
                    format_func=lambda x: {"newest_first":"🕐 Newest first","by_category":"🔴 Category","by_eta":"⏱ Soonest arrival"}[x],
                    key="sort_mode", label_visibility="collapsed")

            if sm == "newest_first":
                out = list(reversed(incoming))
            elif sm == "by_category":
                srt = sorted(incoming, key=lambda p: PORDER.get(p.get("triage_level", TRIAGE_URGENT), 1))
                out = []
                for _, grp in groupby(srt, key=lambda p: PORDER.get(p.get("triage_level", TRIAGE_URGENT), 1)):
                    out.extend(sorted(list(grp), key=lambda p: p.get("timestamp", ""), reverse=True))
            else:
                out = sorted(incoming, key=lambda p: p.get("eta_minutes", 999))

            for p in out:
                render_patient_card(p)

    with t_all:
        render_all_table(hospital_queue.get_all_patients(limit=100))

    with t_occ:
        render_occupancy_tab()

    with t_adm:
        st.subheader("⚙️ Admin")
        with st.expander("Add Test Patients", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("➕ Emergency", use_container_width=True, type="primary"): _add_emergency(); st.rerun()
            with c2:
                if st.button("➕ Urgent", use_container_width=True): _add_urgent(); st.rerun()
            with c3:
                if st.button("➕ Routine", use_container_width=True): _add_routine(); st.rerun()
        st.divider()
        if st.button("🗑 Clear All", type="secondary"):
            hospital_queue.clear_queue(); st.success("Cleared."); st.rerun()

    with st.sidebar:
        st.markdown("### 🏥 CodeZero ER")
        st.divider()
        st.markdown("**Triage Levels**")
        st.markdown("🔴 Emergency — < 10 min")
        st.markdown("🟠 Urgent — < 30 min")
        st.markdown("🟢 Routine — < 2 hours")
        st.divider()
        st.markdown("**Occupancy Penalty**")
        st.markdown("🟢 Low → +0 min")
        st.markdown("🟡 Medium → +10 min")
        st.markdown("🟠 High → +25 min")
        st.markdown("🔴 Full → +60 min")
        st.divider()
        if st.button("🔄 Refresh", use_container_width=True, type="primary"):
            st.rerun()


if __name__ == "__main__":
    main()