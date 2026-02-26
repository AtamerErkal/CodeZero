"""
CodeZero Hospital ER Dashboard — v3.0
Real-time ER command center with:
  - Top KPI bar: Total, Emergency, Urgent, Routine, En-Route, Incoming, Treated
  - Incoming tab: rich patient cards (photo avatar, demographics, health#, AI triage, ETA)
  - Live Tracking tab: map view (simulated) + countdown board
  - Reports tab: daily / weekly / monthly charts (skeleton ready)
  - Statistics tab: operational metrics (skeleton ready)
  - Health Records tab: full postvisit.ai style lookup
  - Admin tab: test patients, clear queue
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
from src.triage_engine import TRIAGE_EMERGENCY, TRIAGE_ROUTINE, TRIAGE_URGENT, TriageEngine
from src.health_db import get_full_record, get_patient, get_age, list_demo_health_numbers, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
init_db()

st.set_page_config(page_title="CodeZero ER", page_icon="🏥", layout="wide")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', sans-serif; }
.block-container { padding: 1rem 1.8rem 2rem 1.8rem !important; }

/* KPI cards */
.kpi-box { border-radius:14px; padding:1rem 1.2rem; border:1px solid #1f2937;
           background:#111827; text-align:center; }
.kpi-label { font-size:0.65rem; color:#6b7280; text-transform:uppercase;
             letter-spacing:0.1em; margin:0 0 4px 0; }
.kpi-value { font-size:2rem; font-weight:900; color:#f9fafb; margin:0; line-height:1; }
.kpi-total { background:linear-gradient(135deg,#1e3a5f,#0f172a);
             border-color:#3b82f6; }
.kpi-total .kpi-value { color:#60a5fa; font-size:2.6rem; }

/* Triage colors */
.kpi-emg   { border-color:#ef444466; }
.kpi-urg   { border-color:#f59e0b66; }
.kpi-rtn   { border-color:#10b98166; }
.kpi-road  { border-color:#8b5cf666; }
.kpi-inc   { border-color:#06b6d466; }
.kpi-done  { border-color:#22c55e66; }

/* Patient card */
.pt-card { border-radius:14px; padding:0; margin-bottom:10px;
           border:1px solid #1f2937; overflow:hidden; }
.pt-card-e { border-left:5px solid #ef4444; background:linear-gradient(135deg,#1c0808,#0d1117); }
.pt-card-u { border-left:5px solid #f59e0b; background:linear-gradient(135deg,#1c1000,#0d1117); }
.pt-card-r { border-left:5px solid #10b981; background:linear-gradient(135deg,#001c0f,#0d1117); }

/* Avatar */
.pt-avatar { width:52px; height:52px; border-radius:10px; 
             display:flex; align-items:center; justify-content:center;
             font-size:1.6rem; flex-shrink:0; }
.av-m { background:#1e3a5f; }
.av-f { background:#4a1d5f; }

/* Badge */
.bx { display:inline-flex; align-items:center; padding:2px 8px; border-radius:20px;
      font-size:0.7rem; font-weight:600; margin:1px 2px 1px 0; white-space:nowrap; }

/* Pills */
.pill-red    { display:inline-block;background:#7f1d1d44;color:#f87171;border:1px solid #dc262644;padding:2px 8px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:1px; }
.pill-green  { display:inline-block;background:#14532d44;color:#4ade80;border:1px solid #16a34a44;padding:2px 8px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:1px; }
.pill-yellow { display:inline-block;background:#78350f44;color:#fbbf24;border:1px solid #d9770644;padding:2px 8px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:1px; }
.pill-blue   { display:inline-block;background:#1e3a5f44;color:#93c5fd;border:1px solid #3b82f644;padding:2px 8px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:1px; }
.pill-gray   { display:inline-block;background:#1f293799;color:#9ca3af;border:1px solid #37415199;padding:2px 8px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:1px; }
.pill-purple { display:inline-block;background:#4c1d9544;color:#c4b5fd;border:1px solid #7c3aed44;padding:2px 8px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:1px; }

/* Detail panel */
.dp { background:#0d1117; border:1px solid #21262d; border-radius:12px;
      padding:1.2rem 1.4rem; margin:4px 0 8px 0; }
.dp-title { font-size:0.65rem; color:#4b5563; text-transform:uppercase;
            letter-spacing:0.1em; font-weight:700; margin-bottom:0.5rem;
            padding-bottom:0.35rem; border-bottom:1px solid #1f2937; }
.dp-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:0.7rem; }
.dp-field-label { font-size:0.65rem; color:#6b7280; margin-bottom:3px; }
.dp-field-value { font-size:0.9rem; font-weight:600; color:#e5e7eb; }

/* Health record */
.hr-section { background:#0d1117; border:1px solid #21262d; border-radius:12px;
              padding:1rem 1.2rem; margin-bottom:0.8rem; }
.hr-header  { font-size:0.65rem; color:#4b5563; text-transform:uppercase;
              letter-spacing:0.1em; font-weight:700; padding-bottom:0.35rem;
              border-bottom:1px solid #1f2937; margin-bottom:0.7rem; }

/* Expander */
div[data-testid="stExpander"] { border:1px solid #1f2937 !important;
  border-radius:10px !important; background:#0d1117 !important; margin-bottom:4px; }

/* Tracking */
.track-row { background:#0f172a; border:1px solid #1f2937; border-radius:10px;
             padding:0.7rem 1rem; margin-bottom:6px; }
.track-e { border-left:4px solid #ef4444; }
.track-u { border-left:4px solid #f59e0b; }
.track-r { border-left:4px solid #10b981; }

/* Tabs */
div[data-testid="stTabs"] button { font-weight:600; font-size:0.88rem; }

/* Metrics */
div[data-testid="stMetric"] { background:#111827; border-radius:12px;
  padding:1rem 1.2rem; border:1px solid #1f2937; }
div[data-testid="stMetric"] label { color:#6b7280 !important; font-size:0.7rem !important;
  text-transform:uppercase; letter-spacing:0.08em; }
div[data-testid="stMetricValue"] { font-size:2rem !important; font-weight:800 !important;
  color:#f9fafb !important; }

/* Skeleton placeholder */
.sk-box { background:#111827; border:1px dashed #374151; border-radius:12px;
          padding:2rem; text-align:center; color:#374151; }

/* Buttons */
.stButton > button { border-radius:8px; font-weight:600; font-size:0.85rem; min-height:36px; }
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
CARD   = {TRIAGE_EMERGENCY: "pt-card-e", TRIAGE_URGENT: "pt-card-u", TRIAGE_ROUTINE: "pt-card-r"}
TRACK  = {TRIAGE_EMERGENCY: "track-e",   TRIAGE_URGENT: "track-u",   TRIAGE_ROUTINE: "track-r"}
PORDER = {TRIAGE_EMERGENCY: 0, TRIAGE_URGENT: 1, TRIAGE_ROUTINE: 2}

NAT_FLAG = {"DE": "🇩🇪", "TR": "🇹🇷", "UK": "🇬🇧"}


def _hkey(prefix: str, s: str) -> str:
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


def _eta_secs(arrival_iso, eta_raw) -> float:
    if arrival_iso:
        try:
            d = (datetime.fromisoformat(str(arrival_iso).replace("Z", "+00:00"))
                 - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, d)
        except Exception:
            pass
    return float(eta_raw or 999) * 60


# ══════════════════════════════════════════════════════════════════════════════
# KPI BAR
# ══════════════════════════════════════════════════════════════════════════════
def render_kpi_bar() -> None:
    stats  = hospital_queue.get_queue_stats()
    by_lv  = stats.get("by_level", {})
    total  = stats.get("total_incoming", 0) + stats.get("total_treated", stats.get("total_discharged", 0))
    inc    = stats.get("total_incoming", 0)
    emg    = by_lv.get(TRIAGE_EMERGENCY, 0)
    urg    = by_lv.get(TRIAGE_URGENT, 0)
    rtn    = by_lv.get(TRIAGE_ROUTINE, 0)
    # en-route = patients whose status is "incoming" with an ETA
    all_in = hospital_queue.get_incoming_patients(limit=200)
    enroute = sum(1 for p in all_in if p.get("eta_minutes") and p.get("status") == "incoming")
    treated = stats.get("total_treated", stats.get("total_discharged", 0))

    # Big total on left, rest on right
    c0, c1, c2, c3, c4, c5, c6 = st.columns([2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])
    with c0:
        st.markdown(f"""
<div class="kpi-box kpi-total">
  <div class="kpi-label">Total Applications Today</div>
  <div class="kpi-value">{total}</div>
</div>""", unsafe_allow_html=True)
    for col, cls, label, val in [
        (c1, "kpi-emg",  "🔴 Emergencies",  emg),
        (c2, "kpi-urg",  "🟠 Urgents",       urg),
        (c3, "kpi-rtn",  "🟢 Routines",      rtn),
        (c4, "kpi-road", "🚗 En-Route",      enroute),
        (c5, "kpi-inc",  "📥 Incoming",      inc),
        (c6, "kpi-done", "✅ Treated",        treated),
    ]:
        with col:
            st.markdown(f"""
<div class="kpi-box {cls}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{val}</div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH RECORD PANEL
# ══════════════════════════════════════════════════════════════════════════════
def render_health_record_panel(health_number: str) -> None:
    if not health_number:
        st.info("No health number provided for this patient.")
        return
    record = get_full_record(health_number.strip())
    if not record:
        st.warning(f"No record found for: **{health_number}**")
        st.caption("Available: " + ", ".join(list_demo_health_numbers()[:6]))
        return

    p      = record["patient"]
    diags  = record["diagnoses"]
    meds   = record["medications"]
    labs   = record["lab_results"]
    vitals = record["vitals"]
    visits = record["visits"]
    allgs  = record["allergies"]
    dob    = p.get("date_of_birth", "")
    age    = get_age(dob)
    nat    = p.get("nationality", "")
    flag   = NAT_FLAG.get(nat, "🌍")

    # Banner
    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);border:1px solid #334155;
     border-radius:14px;padding:1.2rem 1.4rem;margin-bottom:0.8rem;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
    <div>
      <p style="font-size:1.3rem;font-weight:800;color:#f9fafb;margin:0;">
        {flag} {p.get("first_name","")} {p.get("last_name","")}
      </p>
      <p style="color:#64748b;font-size:0.85rem;margin:0.2rem 0 0;">
        Health ID: <span style="color:#60a5fa;font-weight:600;">{health_number}</span>
      </p>
    </div>
    <div style="text-align:right;">
      <span class="pill-blue">🩸 {p.get("blood_type","?")}</span>
      <span class="pill-gray">{p.get("sex","")}</span>
      <span class="pill-gray">{age} yrs</span>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:0.6rem;margin-top:0.8rem;">
    <div><span style="color:#475569;font-size:0.68rem;">DATE OF BIRTH</span><br><span style="color:#e2e8f0;font-size:0.88rem;">{dob}</span></div>
    <div><span style="color:#475569;font-size:0.68rem;">NATIONALITY</span><br><span style="color:#e2e8f0;font-size:0.88rem;">{nat}</span></div>
    <div><span style="color:#475569;font-size:0.68rem;">INSURANCE / NHS</span><br><span style="color:#e2e8f0;font-size:0.88rem;">{p.get("insurance_id","—")}</span></div>
    <div><span style="color:#475569;font-size:0.68rem;">GP / FAMILY DOCTOR</span><br><span style="color:#e2e8f0;font-size:0.88rem;">{p.get("gp_name","—")}</span></div>
    <div><span style="color:#475569;font-size:0.68rem;">PHONE</span><br><span style="color:#e2e8f0;font-size:0.88rem;">{p.get("phone","—")}</span></div>
    <div><span style="color:#475569;font-size:0.68rem;">EMERGENCY CONTACT</span><br><span style="color:#e2e8f0;font-size:0.88rem;">{p.get("emergency_name","—")} · {p.get("emergency_phone","")}</span></div>
  </div>
  {f'<p style="margin:0.6rem 0 0;color:#94a3b8;font-size:0.85rem;font-style:italic;">📝 {p.get("notes","")}</p>' if p.get("notes") else ""}
</div>""", unsafe_allow_html=True)

    # Allergies
    if allgs:
        badges = "".join(
            f'<span class="pill-red" title="{a["reaction"]} — {a["severity"]}">⚠️ {a["allergen"]}</span>'
            for a in allgs)
        st.markdown(f'<div class="hr-section"><div class="hr-header">🚨 Allergies & Alerts</div>{badges}</div>', unsafe_allow_html=True)

    # Vitals
    if vitals:
        v = vitals[0]
        bp_sys   = v.get("bp_systolic") or 0
        bp_clr   = "#ef4444" if bp_sys >= 140 else "#4ade80" if bp_sys < 130 else "#fbbf24"
        spo2_clr = "#ef4444" if (v.get("spo2") or 99) < 95 else "#4ade80"
        bmi_clr  = "#f87171" if (v.get("bmi") or 0) >= 30 else "#4ade80" if (v.get("bmi") or 0) >= 18.5 else "#fbbf24"
        st.markdown(f"""
<div class="hr-section">
  <div class="hr-header">❤️ Latest Vitals — {v.get("recorded_at","")[:10]}</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:0.6rem;">
    <div style="background:#111827;border-radius:10px;padding:0.65rem;text-align:center;">
      <div style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;margin-bottom:3px;">BP</div>
      <div style="font-size:1.25rem;font-weight:800;color:{bp_clr};">{v.get("bp_systolic","?")}/{v.get("bp_diastolic","?")}</div>
      <div style="font-size:0.65rem;color:#4b5563;">mmHg</div></div>
    <div style="background:#111827;border-radius:10px;padding:0.65rem;text-align:center;">
      <div style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;margin-bottom:3px;">Heart Rate</div>
      <div style="font-size:1.25rem;font-weight:800;color:#f9fafb;">{v.get("heart_rate","?")} bpm</div>
      <div style="font-size:0.65rem;color:#4b5563;">beats/min</div></div>
    <div style="background:#111827;border-radius:10px;padding:0.65rem;text-align:center;">
      <div style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;margin-bottom:3px;">SpO₂</div>
      <div style="font-size:1.25rem;font-weight:800;color:{spo2_clr};">{v.get("spo2","?")}%</div>
      <div style="font-size:0.65rem;color:#4b5563;">oxygen sat</div></div>
    <div style="background:#111827;border-radius:10px;padding:0.65rem;text-align:center;">
      <div style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;margin-bottom:3px;">BMI</div>
      <div style="font-size:1.25rem;font-weight:800;color:{bmi_clr};">{v.get("bmi","?")}</div>
      <div style="font-size:0.65rem;color:#4b5563;">{v.get("weight_kg","?")}kg · {v.get("height_cm","?")}cm</div></div>
    <div style="background:#111827;border-radius:10px;padding:0.65rem;text-align:center;">
      <div style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;margin-bottom:3px;">Glucose</div>
      <div style="font-size:1.25rem;font-weight:800;color:#f9fafb;">{v.get("glucose","?")} mmol/L</div>
      <div style="font-size:0.65rem;color:#4b5563;">blood sugar</div></div>
    <div style="background:#111827;border-radius:10px;padding:0.65rem;text-align:center;">
      <div style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;margin-bottom:3px;">Temp</div>
      <div style="font-size:1.25rem;font-weight:800;color:#f9fafb;">{v.get("temperature","?")}°C</div>
      <div style="font-size:0.65rem;color:#4b5563;">body temp</div></div>
  </div>
</div>""", unsafe_allow_html=True)

    # Diagnoses
    if diags:
        st.markdown('<div class="hr-section"><div class="hr-header">🩺 Active Diagnoses</div>', unsafe_allow_html=True)
        for d in diags:
            pill = "pill-red" if d.get("status") == "active" else "pill-gray"
            st.markdown(f"""
<div style="padding:0.45rem 0;border-bottom:1px solid #1f2937;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <span style="color:#e5e7eb;font-size:0.9rem;font-weight:600;">{d["description"]}</span>
      <span class="pill-gray" style="font-size:0.65rem;margin-left:5px;">{d.get("icd_code","")}</span>
      <p style="color:#4b5563;font-size:0.78rem;margin:2px 0 0;">Diagnosed {d.get("diagnosed_date","")} · {d.get("diagnosing_doctor","")}</p>
      {f'<p style="color:#6b7280;font-size:0.76rem;margin:1px 0 0;">{d.get("notes","")}</p>' if d.get("notes") else ""}
    </div>
    <span class="{pill}">{d.get("status","").upper()}</span>
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Medications
    active_meds = [m for m in meds if m.get("status") == "active"]
    if active_meds:
        st.markdown('<div class="hr-section"><div class="hr-header">💊 Current Medications</div>', unsafe_allow_html=True)
        for m in active_meds:
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;padding:0.4rem 0;border-bottom:1px solid #1f2937;">
  <div>
    <span style="color:#93c5fd;font-size:0.9rem;font-weight:600;">{m["name"]}</span>
    <span class="pill-gray">{m.get("dosage","")}</span>
    <p style="color:#6b7280;font-size:0.78rem;margin:2px 0 0;">{m.get("frequency","")} · {m.get("prescribing_doctor","")}</p>
  </div>
  <span class="pill-green">ACTIVE</span>
</div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Lab Results
    if labs:
        st.markdown('<div class="hr-section"><div class="hr-header">🧪 Lab Results</div>', unsafe_allow_html=True)
        for lab in labs[:8]:
            stat = lab.get("status", "normal")
            pill = "pill-red" if stat == "high" else ("pill-green" if stat == "normal" else "pill-yellow")
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;padding:0.38rem 0;border-bottom:1px solid #1f2937;">
  <div>
    <span style="color:#e5e7eb;font-size:0.88rem;font-weight:600;">{lab["test_name"]}</span>
    <span style="color:#6b7280;font-size:0.78rem;margin-left:8px;">{lab.get("test_date","")[:10]}</span>
    <p style="color:#4b5563;font-size:0.72rem;margin:1px 0 0;">Ref: {lab.get("reference_range","")}</p>
  </div>
  <div style="text-align:right;">
    <span style="color:#f9fafb;font-size:0.92rem;font-weight:700;">{lab.get("value","")}</span>
    <br><span class="{pill}">{stat.upper()}</span>
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Past Visits
    if visits:
        st.markdown('<div class="hr-section"><div class="hr-header">🏥 Previous Hospital Visits</div>', unsafe_allow_html=True)
        for v in visits[:5]:
            tpill = "pill-red" if v.get("visit_type") == "Emergency" else "pill-blue"
            st.markdown(f"""
<div style="padding:0.45rem 0;border-bottom:1px solid #1f2937;">
  <div style="display:flex;justify-content:space-between;">
    <span style="color:#e2e8f0;font-size:0.88rem;font-weight:600;">{v.get("hospital","")}</span>
    <span style="color:#64748b;font-size:0.78rem;">{v.get("visit_date","")[:10]}</span>
  </div>
  <div style="margin:2px 0;">
    <span class="{tpill}">{v.get("visit_type","")}</span>
    <span class="pill-gray">{v.get("department","")}</span>
  </div>
  <p style="color:#94a3b8;font-size:0.82rem;margin:2px 0 0;"><b>Complaint:</b> {v.get("chief_complaint","")}</p>
  <p style="color:#64748b;font-size:0.78rem;margin:1px 0 0;"><b>Diagnosis:</b> {v.get("diagnosis","")}</p>
</div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PATIENT CARD
# ══════════════════════════════════════════════════════════════════════════════

def _h(*parts: str) -> str:
    """Concatenate HTML parts — avoids nested f-string issues."""
    return "".join(parts)


def render_patient_card(p: dict) -> None:
    lvl       = p.get("triage_level", TRIAGE_URGENT)
    pid       = p.get("patient_id", "UNKNOWN")
    hn        = p.get("health_number", "")
    stat      = p.get("status", "incoming")
    eta       = _eta_str(p.get("arrival_time"), p.get("eta_minutes"))
    risk      = p.get("risk_score", 5)
    comp      = p.get("chief_complaint", "") or ""
    comp_orig = p.get("complaint_text", comp) or ""
    asmt      = p.get("assessment", "") or ""
    flags     = [f.replace("_", " ").title() for f in p.get("red_flags", []) if f != "none_identified"]
    dest      = p.get("destination_hospital", "") or ""
    has_photo = bool(p.get("has_photo"))
    ph_count  = p.get("photo_count", 0)
    qa        = p.get("qa_transcript", [])
    ts        = (p.get("timestamp", "")[:16] or "").replace("T", " ")
    conds     = p.get("suspected_conditions", [])
    rec_act   = p.get("recommended_action", "") or ""
    time_sens = p.get("time_sensitivity", "") or ""

    db_patient = get_patient(hn) if hn else None
    if db_patient:
        first_name = db_patient.get("first_name", "")
        last_name  = db_patient.get("last_name", "")
        sex        = db_patient.get("sex", p.get("sex", "—")) or "—"
        blood_type = db_patient.get("blood_type", "?") or "?"
        dob        = db_patient.get("date_of_birth", "")
        age        = str(get_age(dob))
        nat        = db_patient.get("nationality", "") or ""
        flag       = NAT_FLAG.get(nat, "&#127758;")
        height     = str(db_patient.get("height_cm", "?") or "?")
        weight     = str(db_patient.get("weight_kg", "?") or "?")
    else:
        first_name = last_name = ""
        sex        = p.get("sex", "—") or "—"
        blood_type = "?"
        age        = str(p.get("age_range", "—") or "—")
        nat        = ""
        flag       = "&#127758;"
        height     = weight = "?"

    full_name  = (first_name + " " + last_name).strip() or pid
    avatar_cls = "av-m" if sex == "Male" else "av-f"
    avatar_ico = "&#128104;" if sex == "Male" else "&#128105;"
    clr        = COLORS.get(lvl, "#f59e0b")
    risk_clr   = "#ef4444" if risk >= 8 else "#f59e0b" if risk >= 5 else "#10b981"
    stat_clr   = {"incoming":"#92400e","arrived":"#1e3a5f","in_treatment":"#4c1d95","discharged":"#14532d"}.get(stat,"#374151")
    lvl_icon   = ICONS.get(lvl, "&#128992;")
    stat_upper = stat.replace("_"," ").upper()
    hn_display = hn if hn else "&#8212;"

    # Pre-build optional badges/lines
    photo_b  = ('<span class="bx" style="background:#4c1d9544;color:#c4b5fd;border:1px solid #7c3aed44;">'
                '&#128247; ' + str(ph_count) + ' photo' + ('s' if ph_count != 1 else '') + '</span>') if has_photo else ""
    weight_b = ('<span class="bx" style="background:#1f293799;color:#94a3b8;border:1px solid #374151;">'
                '&#9878; ' + weight + 'kg &middot; ' + height + 'cm</span>') if weight != "?" else ""
    dest_b   = ('<span style="color:#6b7280;font-size:0.75rem;margin-left:8px;">&#127973; ' + dest + '</span>') if dest else ""
    orig_l   = ('<p style="margin:0;color:#fde68a;font-size:0.82rem;font-style:italic;">&ldquo;'
                + comp_orig + '&rdquo;</p>') if comp_orig and comp_orig != comp else ""
    asmt_p   = ('<p style="margin:0.2rem 0 0;color:#6b7280;font-size:0.8rem;line-height:1.45;">'
                + asmt[:180] + ("&hellip;" if len(asmt) > 180 else "") + "</p>") if asmt else ""
    flags_l  = ('<p style="margin:0.2rem 0 0;font-size:0.78rem;">'
                '<span style="color:#ef4444;">&#128681;</span> '
                '<span style="color:#fca5a5;">' + " &middot; ".join(flags[:4]) + '</span></p>') if flags else ""

    # Build card using string concatenation — no nested f-strings
    card = (
        '<div class="pt-card ' + CARD.get(lvl,"pt-card-u") + '" style="padding:0.9rem 1rem 0.6rem 1rem;">'
        '<div style="display:flex;gap:0.8rem;align-items:flex-start;">'
          '<div class="pt-avatar ' + avatar_cls + '">' + avatar_ico + '</div>'
          '<div style="flex:1;min-width:0;">'
            # Row 1: name + ETA
            '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:4px;">'
              '<div>'
                '<span style="font-size:1.05rem;font-weight:800;color:#f9fafb;">' + full_name + '</span>'
                '<span style="color:#4b5563;font-size:0.82rem;margin-left:6px;">&#8212; ' + pid + '</span>'
              '</div>'
              '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">'
                '<span style="background:#1e293b;border:1px solid ' + clr + ';color:' + clr + ';'
                      'padding:3px 10px;border-radius:20px;font-size:0.75rem;font-weight:700;">'
                      '&#9201; ' + eta + '</span>'
                '<span class="bx" style="background:' + stat_clr + '44;color:#e5e7eb;border:1px solid ' + stat_clr + ';">'
                  + stat_upper + '</span>'
              '</div>'
            '</div>'
            # Row 2: demographic badges
            '<div style="margin:0.35rem 0 0.2rem;display:flex;flex-wrap:wrap;gap:3px;">'
              '<span class="bx" style="background:#1f293799;color:#94a3b8;border:1px solid #374151;">' + flag + ' ' + nat + '</span>'
              '<span class="bx" style="background:#1f293799;color:#94a3b8;border:1px solid #374151;">&#127874; ' + age + 'y</span>'
              '<span class="bx" style="background:#1f293799;color:#94a3b8;border:1px solid #374151;">&#9895; ' + sex + '</span>'
              '<span class="bx" style="background:#1e3a5f44;color:#93c5fd;border:1px solid #3b82f644;">&#129656; ' + blood_type + '</span>'
              '<span class="bx" style="background:#1f293799;color:#94a3b8;border:1px solid #374151;">&#128282; ' + hn_display + '</span>'
              '<span class="bx" style="background:' + risk_clr + '22;color:' + risk_clr + ';border:1px solid ' + risk_clr + '55;">'
                '&#9889; Risk ' + str(risk) + '/10</span>'
              + photo_b + weight_b +
            '</div>'
            # Row 3: triage level + dest + time
            '<div style="margin:0.2rem 0;">'
              '<span style="font-size:0.78rem;font-weight:700;color:' + clr + ';">' + lvl_icon + ' ' + lvl + '</span>'
              + dest_b +
              '<span style="color:#4b5563;font-size:0.72rem;margin-left:8px;">&#128336; ' + ts + '</span>'
            '</div>'
            # Chief complaint
            '<p style="margin:0.3rem 0 0.15rem;color:#64748b;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.06em;">Chief Complaint</p>'
            '<p style="margin:0 0 0.1rem;color:#f3f4f6;font-size:0.9rem;font-weight:600;">' + comp + '</p>'
            + orig_l + asmt_p + flags_l +
          '</div>'
        '</div>'
        '</div>'
    )
    st.markdown(card, unsafe_allow_html=True)

    # ── Expandable detail ─────────────────────────────────────────────────────
    with st.expander("&#128203; Full Detail &#8212; " + full_name + " (" + pid + ")"):
        tab1, tab2, tab3 = st.tabs(["&#129514; This Visit", "&#128202; Health Record", "&#127973; Pre-Arrival Prep"])

        with tab1:
            # AI Assessment
            if asmt:
                conds_h  = ('<div class="dp-grid"><div><div class="dp-field-label">Suspected Conditions</div>'
                            '<div class="dp-field-value" style="color:#93c5fd;">' + " &middot; ".join(conds) + '</div></div></div>') if conds else ""
                recact_h = ('<div style="margin-top:0.5rem;"><div class="dp-field-label">Recommended Action</div>'
                            '<div class="dp-field-value">' + rec_act + '</div></div>') if rec_act else ""
                timens_h = ('<div style="margin-top:0.4rem;"><div class="dp-field-label">Time Sensitivity</div>'
                            '<div class="dp-field-value" style="color:' + clr + ';">' + time_sens + '</div></div>') if time_sens else ""
                st.markdown(
                    '<div class="dp">'
                    '<div class="dp-title">&#129302; AI Clinical Assessment &amp; Diagnosis</div>'
                    '<p style="color:#d1d5db;font-size:0.88rem;line-height:1.65;margin:0 0 0.7rem;">' + asmt + '</p>'
                    + conds_h + recact_h + timens_h +
                    '</div>',
                    unsafe_allow_html=True,
                )

            # Red flags
            if flags:
                badges = "".join(
                    '<span class="bx" style="background:#ef444422;color:#fca5a5;border:1px solid #ef444455;">' + fl + '</span>'
                    for fl in flags
                )
                st.markdown(
                    '<div class="dp"><div class="dp-title">&#128681; Red Flags</div>'
                    '<div style="display:flex;flex-wrap:wrap;gap:4px;">' + badges + '</div></div>',
                    unsafe_allow_html=True,
                )

            # Voice transcript
            if comp_orig and comp_orig != comp:
                tr_inner = ('<p style="color:#fde68a;font-size:0.9rem;font-style:italic;margin:0 0 0.4rem;">'
                            '&ldquo;' + comp_orig + '&rdquo;</p>'
                            '<p style="color:#6b7280;font-size:0.8rem;margin:0;">English: ' + comp + '</p>')
            else:
                tr_inner = '<p style="color:#e5e7eb;font-size:0.9rem;font-weight:500;margin:0;">' + comp + '</p>'
            st.markdown(
                '<div class="dp"><div class="dp-title">&#128483; Patient Voice Transcript / Chief Complaint</div>'
                + tr_inner + '</div>',
                unsafe_allow_html=True,
            )

            # Q&A
            if qa:
                rows = "".join(
                    '<div style="padding:0.38rem 0;border-bottom:1px solid #1f2937;">'
                    '<span style="color:#6b7280;font-size:0.72rem;text-transform:uppercase;">Q:</span> '
                    '<span style="color:#cbd5e1;font-size:0.86rem;">' + (q.get("question","")) + '</span><br>'
                    '<span style="color:#6b7280;font-size:0.72rem;text-transform:uppercase;">A:</span> '
                    '<span style="color:#86efac;font-size:0.88rem;font-weight:600;">' + (q.get("original_answer") or q.get("answer","")) + '</span>'
                    '</div>'
                    for q in qa
                )
                st.markdown(
                    '<div class="dp"><div class="dp-title">&#128172; Follow-Up Q&amp;A Answers</div>'
                    + rows + '</div>',
                    unsafe_allow_html=True,
                )

            # Photos
            if has_photo:
                st.markdown('<div class="dp"><div class="dp-title">&#128247; Patient-Submitted Photos</div>', unsafe_allow_html=True)
                photo_bytes_list = p.get("photos_bytes", [])
                if photo_bytes_list:
                    cols = st.columns(min(len(photo_bytes_list), 3))
                    for i, pb in enumerate(photo_bytes_list):
                        with cols[i % 3]:
                            try:
                                st.image(pb, use_container_width=True, caption="Photo " + str(i+1))
                            except Exception:
                                st.markdown('<p style="color:#a78bfa;font-size:0.85rem;">&#128247; Photo ' + str(i+1) + ' (preview unavailable)</p>', unsafe_allow_html=True)
                else:
                    st.markdown('<p style="color:#a78bfa;font-size:0.85rem;">Patient attached ' + str(ph_count) + ' photo(s). Photos stored in patient session.</p>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            # ETA / Location
            loc       = p.get("location") or {}
            coords_h  = ('<div><div class="dp-field-label">Current Coordinates</div>'
                         '<div class="dp-field-value">' + str(round(loc.get("lat",0),4)) + ', ' + str(round(loc.get("lon",0),4)) + '</div></div>') if loc.get("lat") else ""
            dest_h    = ('<div><div class="dp-field-label">Destination</div>'
                         '<div class="dp-field-value">' + dest + '</div></div>') if dest else ""
            consent_v = "&#9989; Given" if p.get("data_consent") else "&#10060; Not given"
            st.markdown(
                '<div class="dp"><div class="dp-title">&#128205; Location &amp; ETA</div>'
                '<div class="dp-grid">'
                '<div><div class="dp-field-label">ETA to Hospital</div>'
                '<div class="dp-field-value" style="color:' + clr + ';font-size:1.2rem;">' + eta + '</div></div>'
                + coords_h + dest_h +
                '<div><div class="dp-field-label">Data Consent</div>'
                '<div class="dp-field-value">' + consent_v + '</div></div>'
                '</div></div>',
                unsafe_allow_html=True,
            )

        with tab2:
            if hn:
                render_health_record_panel(hn)
            else:
                st.info("No health number provided by this patient.")
                hn_input = st.text_input(
                    "&#128269; Look up by health number",
                    key=_hkey("hn_lookup", pid),
                    placeholder="e.g. DEMO-DE-001 · DEMO-TR-001 · DEMO-UK-001",
                )
                if hn_input and len(hn_input) > 5:
                    render_health_record_panel(hn_input)

        with tab3:
            if pid not in _PREP_CACHE:
                with st.spinner("Generating checklist..."):
                    try:
                        _PREP_CACHE[pid] = triage_engine.generate_hospital_prep(
                            chief_complaint=p.get("chief_complaint", "unknown"),
                            assessment=p,
                        )
                    except Exception as exc:
                        logger.error("Prep failed %s: %s", pid, exc)
                        _PREP_CACHE[pid] = [
                            "Assign appropriate bay",
                            "Alert attending physician",
                            "Prepare standard monitoring",
                        ]
            items = _PREP_CACHE.get(pid, [])
            if items:
                for item in items:
                    key = _hkey("prep", pid + item)
                    done = st.session_state.get(key, False)
                    st.checkbox(item, value=done, key=key)


# ══════════════════════════════════════════════════════════════════════════════
# LIVE TRACKING TAB  — real OpenStreetMap via Leaflet.js (browser-side CDN)
# ══════════════════════════════════════════════════════════════════════════════
def _build_leaflet_html(patients: list[dict],
                        hosp_lat: float = 48.7758,
                        hosp_lon: float = 9.1829) -> str:
    """Return a standalone HTML page with a dark Leaflet/CARTO map.
    Patient markers are colour-coded by triage level and show popup details.
    No server-side map library needed — Leaflet is loaded from CDN in the browser."""
    import json

    markers: list[dict] = []
    for p in patients:
        loc = p.get("location") or {}
        lat = loc.get("lat")
        lon = loc.get("lon")
        if not (lat and lon):
            continue
        lvl   = p.get("triage_level", TRIAGE_URGENT)
        color = {TRIAGE_EMERGENCY: "#ef4444",
                 TRIAGE_URGENT:    "#f59e0b",
                 TRIAGE_ROUTINE:   "#10b981"}.get(lvl, "#f59e0b")
        hn    = p.get("health_number", p.get("patient_id", ""))
        comp  = (p.get("chief_complaint", "") or "")[:60]
        eta   = p.get("eta_minutes", "?")
        markers.append({"lat": lat, "lon": lon, "color": color,
                        "label": hn, "eta": eta, "comp": comp, "lvl": lvl})

    markers_js   = json.dumps(markers)
    hospital_js  = json.dumps({"lat": hosp_lat, "lon": hosp_lon})

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    crossorigin=""/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    crossorigin=""></script>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    html,body{{height:100%;background:#0d1117;overflow:hidden}}
    #map{{height:100vh;width:100%}}
    .leaflet-popup-content-wrapper{{
      background:#1e293b;border:1px solid #334155;
      border-radius:10px;box-shadow:0 4px 20px #00000088;
    }}
    .leaflet-popup-content{{color:#f1f5f9;font-size:12px;
      font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;
      line-height:1.5;min-width:140px}}
    .leaflet-popup-tip{{background:#1e293b}}
    .leaflet-popup-close-button{{color:#64748b!important}}
    .pm{{display:flex;align-items:center;justify-content:center;
      border-radius:50%;border:2px solid #ffffff66;
      font-size:10px;font-weight:800;color:white;
      box-shadow:0 0 12px var(--c),0 0 4px #00000088;
      background:var(--c)}}
    @keyframes pulse{{
      0%,100%{{transform:scale(1);opacity:1}}
      50%{{transform:scale(1.35);opacity:.7}}
    }}
  </style>
</head>
<body>
<div id="map"></div>
<script>
(function(){{
  var markers   = {markers_js};
  var hospital  = {hospital_js};

  var map = L.map("map",{{
    center:[hospital.lat, hospital.lon],
    zoom:12,
    zoomControl:true,
    attributionControl:true,
    preferCanvas:true
  }});

  // Dark CARTO tiles — free, no API key
  L.tileLayer(
    "https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png",
    {{
      attribution:"&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> &copy; <a href='https://carto.com/'>CARTO</a>",
      subdomains:"abcd",
      maxZoom:19
    }}
  ).addTo(map);

  // Hospital pin
  var hospIcon = L.divIcon({{
    html:'<div style="background:#3b82f6;color:#fff;padding:5px 10px;'
        +'border-radius:8px;font-size:12px;font-weight:700;'
        +'white-space:nowrap;box-shadow:0 0 14px #3b82f688;'
        +'border:1px solid #60a5fa;">🏥 Hospital</div>',
    className:"",
    iconAnchor:[44,16]
  }});
  L.marker([hospital.lat,hospital.lon],{{icon:hospIcon}}).addTo(map);

  // Patient markers
  var bounds = [[hospital.lat,hospital.lon]];
  markers.forEach(function(m){{
    var sz = m.lvl==="EMERGENCY" ? 20 : 15;
    var icon = L.divIcon({{
      html:'<div class="pm" style="--c:'+m.color+';width:'+sz+'px;height:'+sz+'px;'
          +'animation:pulse '+(m.lvl==="EMERGENCY"?"1s":"2s")+' infinite;"></div>',
      className:"",
      iconSize:[sz,sz],
      iconAnchor:[sz/2,sz/2]
    }});
    var popup = "<b>"+m.label+"</b>"
      +(m.eta!=="?" ? "<br>&#x23F1; ETA: "+m.eta+" min" : "")
      +(m.comp      ? "<br>"+m.comp : "");
    L.marker([m.lat,m.lon],{{icon:icon}}).addTo(map).bindPopup(popup);
    bounds.push([m.lat,m.lon]);
  }});

  // Fit all markers in view
  if(bounds.length>1){{
    map.fitBounds(bounds,{{padding:[40,40],maxZoom:14}});
  }}
}})();
</script>
</body>
</html>"""


def render_tracking_tab() -> None:
    incoming = hospital_queue.get_incoming_patients(limit=100)
    en_route = [p for p in incoming if p.get("eta_minutes") or p.get("arrival_time")]
    en_route.sort(key=lambda p: _eta_secs(p.get("arrival_time"), p.get("eta_minutes")))

    with_gps = [p for p in en_route if (p.get("location") or {}).get("lat")]
    no_gps   = [p for p in en_route if not (p.get("location") or {}).get("lat")]

    # Header row
    hc1, hc2 = st.columns([5, 1])
    with hc1:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:0.5rem;">'
            f'<span style="background:#10b98122;color:#4ade80;border:1px solid #10b98144;'
            f'padding:3px 12px;border-radius:20px;font-size:0.75rem;font-weight:700;">&#9679; LIVE</span>'
            f'<span style="color:#4b5563;font-size:0.8rem;">'
            f'{len(en_route)} patients en-route &nbsp;·&nbsp; {len(with_gps)} with GPS</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with hc2:
        if st.button("🔄 Refresh", use_container_width=True, key="tracking_refresh"):
            st.rerun()

    if not en_route:
        st.markdown(
            '<div style="text-align:center;padding:3rem;color:#374151;">'
            '<div style="font-size:2.5rem;">📡</div>'
            '<p>No patients currently en-route.</p></div>',
            unsafe_allow_html=True,
        )
        return

    # Real Leaflet/OpenStreetMap map
    st.components.v1.html(_build_leaflet_html(en_route), height=430, scrolling=False)

    if no_gps:
        st.caption(
            f"ℹ️ {len(no_gps)} patient(s) without GPS coordinates — "
            "shown in list only (location not yet shared by patient)"
        )

    st.markdown(
        f'<p style="color:#64748b;font-size:0.78rem;margin:0.6rem 0 0.4rem;">'
        f'{len(en_route)} patient(s) · sorted by arrival time</p>',
        unsafe_allow_html=True,
    )
    for p in en_route:
        lvl      = p.get("triage_level", TRIAGE_URGENT)
        pid      = p.get("patient_id", "")
        hn       = p.get("health_number", "")
        eta      = _eta_str(p.get("arrival_time"), p.get("eta_minutes"))
        eta_secs = _eta_secs(p.get("arrival_time"), p.get("eta_minutes"))
        clr      = COLORS.get(lvl, "#f59e0b")
        db_p     = get_patient(hn) if hn else None
        name     = f"{db_p['first_name']} {db_p['last_name']}" if db_p else pid
        flag     = NAT_FLAG.get(db_p.get("nationality", ""), "") if db_p else ""
        age      = get_age(db_p["date_of_birth"]) if db_p else p.get("age_range", "—")
        sex      = db_p.get("sex", "") if db_p else p.get("sex", "—")
        blood    = db_p.get("blood_type", "?") if db_p else "?"
        loc      = p.get("location") or {}
        lat_str  = f"{loc.get('lat', 0):.4f}" if loc.get("lat") else "N/A"
        lon_str  = f"{loc.get('lon', 0):.4f}" if loc.get("lon") else "N/A"
        bar_pct  = max(5, min(100, int(100 - (eta_secs / 3600) * 100))) if eta_secs < 3600 else 5
        urgent   = eta_secs < 600
        eta_clr  = "#ef4444" if urgent else clr
        urgent_pfx = "🚨 " if urgent else ""
        anim_bar = "animation:pulse 1s infinite;" if urgent else ""

        st.markdown(
            f'<div class="track-row {TRACK.get(lvl, "track-u")}">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">'
            f'<div>'
            f'<span style="font-size:0.95rem;font-weight:800;color:#f9fafb;">{ICONS.get(lvl,"")} {flag} {name}</span>'
            f'<span style="color:#4b5563;font-size:0.8rem;margin-left:6px;">{hn}</span>'
            f'<div style="margin-top:0.25rem;display:flex;gap:4px;flex-wrap:wrap;">'
            f'<span class="bx" style="background:#1f2937;color:#9ca3af;border:1px solid #374151;">{age}y · {sex}</span>'
            f'<span class="bx" style="background:#1e3a5f44;color:#93c5fd;border:1px solid #3b82f644;">&#x1FA78; {blood}</span>'
            f'<span class="bx" style="background:#1f2937;color:#9ca3af;border:1px solid #374151;">&#x1F4CD; {lat_str}, {lon_str}</span>'
            f'</div>'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<div style="font-size:1.4rem;font-weight:900;color:{eta_clr};">{urgent_pfx}{eta}</div>'
            f'<div style="font-size:0.72rem;color:#4b5563;">to arrival</div>'
            f'</div>'
            f'</div>'
            f'<div style="background:#1f2937;border-radius:4px;height:4px;margin-top:0.6rem;overflow:hidden;">'
            f'<div style="background:{clr};width:{bar_pct}%;height:100%;border-radius:4px;'
            f'transition:width 1s ease;{anim_bar}"></div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# REPORTS TAB (skeleton)
# ══════════════════════════════════════════════════════════════════════════════
def render_reports_tab() -> None:
    st.markdown("### 📊 Reports")
    rt1, rt2, rt3 = st.tabs(["📅 Daily", "📆 Weekly", "🗓 Monthly"])

    skeleton = """
<div class="sk-box">
  <div style="font-size:2rem;margin-bottom:0.5rem;">{icon}</div>
  <p style="font-size:0.9rem;color:#4b5563;margin:0;">{label}</p>
  <p style="font-size:0.75rem;color:#1f2937;margin:0.3rem 0 0;">Coming soon — data will populate automatically</p>
</div>"""

    with rt1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(skeleton.format(icon="📈", label="Daily Patient Volume"), unsafe_allow_html=True)
        with c2:
            st.markdown(skeleton.format(icon="⏱", label="Average Wait Times by Triage Level"), unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        with c3:
            st.markdown(skeleton.format(icon="🩺", label="Diagnosis Distribution"), unsafe_allow_html=True)
        with c4:
            st.markdown(skeleton.format(icon="🌍", label="Patient Nationality Breakdown"), unsafe_allow_html=True)

    with rt2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(skeleton.format(icon="📊", label="Weekly Trend — Emergency vs Urgent vs Routine"), unsafe_allow_html=True)
        with c2:
            st.markdown(skeleton.format(icon="🏥", label="Bed Occupancy Rate"), unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        with c3:
            st.markdown(skeleton.format(icon="💊", label="Most Common Medications on Admission"), unsafe_allow_html=True)
        with c4:
            st.markdown(skeleton.format(icon="🔴", label="Weekly Red Flag Frequency"), unsafe_allow_html=True)

    with rt3:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(skeleton.format(icon="📉", label="Monthly Patient Volume Trend"), unsafe_allow_html=True)
        with c2:
            st.markdown(skeleton.format(icon="⭐", label="Patient Satisfaction Score"), unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        with c3:
            st.markdown(skeleton.format(icon="🚑", label="ETA Accuracy Analysis"), unsafe_allow_html=True)
        with c4:
            st.markdown(skeleton.format(icon="💰", label="Resource Utilisation"), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# STATISTICS TAB (skeleton)
# ══════════════════════════════════════════════════════════════════════════════
def render_statistics_tab() -> None:
    st.markdown("### 📈 Statistics")

    # Live mini-metrics from queue
    stats  = hospital_queue.get_queue_stats()
    by_lv  = stats.get("by_level", {})
    all_in = hospital_queue.get_incoming_patients(limit=200)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg. Risk Score",
              f"{sum(p.get('risk_score',5) for p in all_in)/max(len(all_in),1):.1f}/10" if all_in else "—")
    c2.metric("Patients with Photos",
              f"{sum(1 for p in all_in if p.get('has_photo'))} / {len(all_in)}")
    c3.metric("Avg. ETA",
              f"{sum(p.get('eta_minutes',0) for p in all_in if p.get('eta_minutes'))/max(sum(1 for p in all_in if p.get('eta_minutes')),1):.0f} min" if all_in else "—")
    c4.metric("Data Consent Rate",
              f"{100*sum(1 for p in all_in if p.get('data_consent'))/max(len(all_in),1):.0f}%" if all_in else "—")

    st.divider()
    skeleton = """
<div class="sk-box">
  <div style="font-size:2rem;margin-bottom:0.5rem;">{icon}</div>
  <p style="font-size:0.9rem;color:#4b5563;margin:0;">{label}</p>
  <p style="font-size:0.75rem;color:#1f2937;margin:0.3rem 0 0;">Coming soon</p>
</div>"""
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(skeleton.format(icon="🔄", label="Triage Accuracy Rate"), unsafe_allow_html=True)
    with c2:
        st.markdown(skeleton.format(icon="⚡", label="AI vs Doctor Diagnosis Match"), unsafe_allow_html=True)
    with c3:
        st.markdown(skeleton.format(icon="🌡", label="Peak Hours Heatmap"), unsafe_allow_html=True)
    c4, c5, c6 = st.columns(3)
    with c4:
        st.markdown(skeleton.format(icon="🏃", label="Door-to-Doctor Time"), unsafe_allow_html=True)
    with c5:
        st.markdown(skeleton.format(icon="🔁", label="Re-admission Rate"), unsafe_allow_html=True)
    with c6:
        st.markdown(skeleton.format(icon="📱", label="App Adoption by Nationality"), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ALL RECORDS TABLE
# ══════════════════════════════════════════════════════════════════════════════
def render_all_table(patients: list[dict]) -> None:
    if not patients:
        st.info("No patient records yet.")
        return
    rows = []
    for p in patients:
        hn  = p.get("health_number","")
        db  = get_patient(hn) if hn else None
        rows.append({
            "ID":         p.get("patient_id",""),
            "Name":       f"{db['first_name']} {db['last_name']}" if db else "—",
            "Health #":   hn or "—",
            "Triage":     p.get("triage_level",""),
            "Risk":       p.get("risk_score",""),
            "ETA":        _eta_str(p.get("arrival_time"), p.get("eta_minutes")),
            "Complaint":  (p.get("chief_complaint",""))[:60],
            "Status":     p.get("status",""),
            "Submitted":  (p.get("timestamp","")[:16] or "").replace("T"," "),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH LOOKUP PAGE
# ══════════════════════════════════════════════════════════════════════════════
def render_health_lookup_page() -> None:
    st.markdown("### 🗂 Patient Health Record Lookup")
    c1, c2 = st.columns([3, 1])
    with c1:
        hn = st.text_input("Health Number", placeholder="e.g. DEMO-DE-001  ·  DEMO-TR-004  ·  DEMO-UK-007",
                           label_visibility="collapsed", key="hr_lookup_input")
    with c2:
        search = st.button("Search →", type="primary", use_container_width=True, key="hr_lookup_btn")

    # Quick-select chips
    st.caption("Quick select: " + "  ".join(f"`{n}`" for n in list_demo_health_numbers()))

    if search and hn:
        render_health_record_panel(hn.strip())
    elif not hn:
        st.markdown("""
<div style="background:#0d1117;border:1px dashed #374151;border-radius:12px;
     padding:2.5rem;text-align:center;margin-top:1rem;">
  <div style="font-size:2.5rem;margin-bottom:0.5rem;">🗂</div>
  <p style="color:#4b5563;margin:0;">Enter a health number above to view the full patient record</p>
  <p style="color:#1f2937;font-size:0.8rem;margin:0.3rem 0 0;">Supports all 30 demo patients (DE · TR · UK)</p>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TEST HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _mk(complaint, asmt_dict, lang, eta, demographics, dest, health_number="", photos_bytes=None):
    r = triage_engine.create_patient_record(
        chief_complaint=complaint, assessment=asmt_dict,
        language=lang, eta_minutes=eta, demographics=demographics,
    )
    r["destination_hospital"] = dest
    r["health_number"]        = health_number
    r["complaint_text"]       = complaint
    r["photos_bytes"]         = photos_bytes or []
    r["has_photo"]            = bool(photos_bytes)
    r["photo_count"]          = len(photos_bytes) if photos_bytes else 0
    r["data_consent"]         = True
    r["qa_transcript"] = [
        {"question": "How long have you had this symptom?",  "answer": "Just started, about 15 minutes ago", "original_answer": "Gerade erst, etwa 15 Minuten"},
        {"question": "Rate your pain 1-10",                  "answer": "8",                                  "original_answer": "8"},
        {"question": "Does the pain radiate?",               "answer": "Yes, to my left arm and jaw",        "original_answer": "Ja, in den linken Arm"},
    ]
    hospital_queue.add_patient(r)
    return r["patient_id"]

def _add_emergency():
    pid = _mk("Severe chest pain with arm radiation and sweating",
        {"triage_level":TRIAGE_EMERGENCY,"assessment":"3 red flags: radiation to left arm, diaphoresis, dyspnea. Probable ACS — activate cath lab immediately.",
         "red_flags":["pain_radiation","diaphoresis","dyspnea"],"recommended_action":"Activate cath lab immediately. 12-lead ECG. IV access × 2.",
         "risk_score":9,"source_guidelines":["chest_pain_protocol.txt"],
         "suspected_conditions":["Acute Coronary Syndrome","STEMI"],"time_sensitivity":"Within 10 minutes"},
        "de-DE", 12, {"age_range":"45-59","sex":"Male"},
        "Klinikum Stuttgart – Katharinenhospital", "DEMO-DE-001")
    st.success("Added EMERGENCY: " + pid)

def _add_urgent():
    pid = _mk("Sudden severe headache — worst of my life — and vomiting for 2 hours",
        {"triage_level":TRIAGE_URGENT,"assessment":"Thunderclap headache with vomiting. SAH must be excluded urgently. CT head within 30 minutes.",
         "red_flags":["thunderclap_headache","vomiting","worst_headache_ever"],"recommended_action":"CT head within 30 min. LP if CT negative.",
         "risk_score":7,"source_guidelines":[],"suspected_conditions":["Subarachnoid Haemorrhage","Migraine"],
         "time_sensitivity":"Within 30 minutes"},
        "tr-TR", 22, {"age_range":"30-44","sex":"Female"},
        "Robert-Bosch-Krankenhaus Stuttgart", "DEMO-TR-004")
    st.success("Added URGENT: " + pid)

def _add_routine():
    pid = _mk("Mild headache for 2 days, no fever, no vomiting",
        {"triage_level":TRIAGE_ROUTINE,"assessment":"Tension-type headache. Pain 3/10. No red flags. No neurological deficit.",
         "red_flags":["none_identified"],"recommended_action":"Analgesia, rest. See GP if persists 48h.",
         "risk_score":2,"source_guidelines":[],"suspected_conditions":["Tension Headache"],
         "time_sensitivity":"Within 48 hours"},
        "en-GB", 45, {"age_range":"18-29","sex":"Female"},
        "Universitätsklinikum Tübingen", "DEMO-UK-002")
    st.success("Added ROUTINE: " + pid)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    now_str = datetime.now(timezone.utc).strftime("%d %b %Y  %H:%M UTC")

    # ── Page header ───────────────────────────────────────────────────────────
    hc1, hc2 = st.columns([5, 1])
    with hc1:
        st.markdown("## 🏥 CodeZero — ER Command Center")
    with hc2:
        st.markdown(f'<div style="text-align:right;padding-top:0.9rem;color:#4b5563;font-size:0.78rem;">{now_str}</div>', unsafe_allow_html=True)

    # ── KPI bar ───────────────────────────────────────────────────────────────
    render_kpi_bar()
    st.markdown("<div style='margin:0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Main tabs ─────────────────────────────────────────────────────────────
    t_in, t_track, t_rep, t_stat, t_rec, t_adm = st.tabs([
        "📥 Incoming",
        "📡 Live Tracking",
        "📊 Reports",
        "📈 Statistics",
        "🗂 Health Records",
        "⚙️ Admin",
    ])

    # ── Incoming tab ──────────────────────────────────────────────────────────
    with t_in:
        incoming = hospital_queue.get_incoming_patients(limit=40)
        if not incoming:
            st.markdown('<div style="text-align:center;padding:4rem;color:#374151;"><div style="font-size:3rem;">🏥</div><p>No incoming patients yet. Add test patients from the Admin tab.</p></div>', unsafe_allow_html=True)
        else:
            sc1, sc2 = st.columns([2, 5])
            with sc1:
                sm = st.selectbox(
                    "Sort by", ["by_category", "newest_first", "by_eta"],
                    format_func=lambda x: {"newest_first":"🕐 Newest first","by_category":"🔴 Triage level","by_eta":"⏱ Soonest arrival"}[x],
                    key="sort_mode", label_visibility="collapsed",
                )
            if sm == "newest_first":
                out = list(reversed(incoming))
            elif sm == "by_category":
                srt = sorted(incoming, key=lambda p: PORDER.get(p.get("triage_level", TRIAGE_URGENT), 1))
                out = []
                for _, grp in groupby(srt, key=lambda p: PORDER.get(p.get("triage_level", TRIAGE_URGENT), 1)):
                    out.extend(sorted(list(grp), key=lambda p: p.get("timestamp", ""), reverse=True))
            else:
                out = sorted(incoming, key=lambda p: p.get("eta_minutes") or 999)

            st.markdown(f'<p style="color:#4b5563;font-size:0.78rem;margin:0 0 0.5rem;">{len(out)} patient(s)</p>', unsafe_allow_html=True)
            for p in out:
                render_patient_card(p)

    # ── Live Tracking tab ─────────────────────────────────────────────────────
    with t_track:
        render_tracking_tab()

    # ── Reports tab ───────────────────────────────────────────────────────────
    with t_rep:
        render_reports_tab()

    # ── Statistics tab ────────────────────────────────────────────────────────
    with t_stat:
        render_statistics_tab()

    # ── Health Records tab ────────────────────────────────────────────────────
    with t_rec:
        render_health_lookup_page()

    # ── Admin tab ─────────────────────────────────────────────────────────────
    with t_adm:
        st.subheader("⚙️ Admin")
        with st.expander("➕ Add Test Patients", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("➕ Add Emergency", use_container_width=True, type="primary"):
                    _add_emergency(); st.rerun()
            with c2:
                if st.button("➕ Add Urgent", use_container_width=True):
                    _add_urgent(); st.rerun()
            with c3:
                if st.button("➕ Add Routine", use_container_width=True):
                    _add_routine(); st.rerun()
        st.divider()
        if st.button("🗑 Clear All Patients", type="secondary"):
            hospital_queue.clear_queue(); st.success("Queue cleared."); st.rerun()
        st.divider()
        st.subheader("📋 All Records")
        render_all_table(hospital_queue.get_all_patients(limit=100))

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🏥 CodeZero ER")
        st.caption("Real-time Emergency Dashboard · v3.0")
        st.divider()
        st.markdown("**Triage Priority**")
        st.markdown("🔴 **Emergency** — within 10 min")
        st.markdown("🟠 **Urgent** — within 30 min")
        st.markdown("🟢 **Routine** — within 2 hours")
        st.divider()
        st.markdown("**Health Number Formats**")
        st.markdown("`DEMO-DE-001` → `DEMO-DE-010`")
        st.markdown("`DEMO-TR-001` → `DEMO-TR-010`")
        st.markdown("`DEMO-UK-001` → `DEMO-UK-010`")
        st.divider()
        if st.button("🔄 Refresh Dashboard", use_container_width=True, type="primary"):
            st.rerun()
        st.divider()
        st.caption("⚠️ Demo only. Not for clinical use.")


if __name__ == "__main__":
    main()