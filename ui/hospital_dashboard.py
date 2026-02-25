"""
CodeZero Hospital ER Dashboard — v2.0
=======================================
Tabs per patient:
  Tab 1 — This Visit    : transcript, photos, Q&A, AI assessment, red flags,
                          ETA, prep checklist
  Tab 2 — Health Record : full simulated eNabiz/NHS record via health number
                          (diagnoses, medications, vitals, labs, allergies,
                           past visits — postvisit.ai style)
  Tab 3 — Live Tracking : all en-route patients on a real-time countdown board

Fixes in this version:
  - Duplicate slider key: MD5 hash of hospital name
  - Demographics always shown (age_range / sex fallback "—")
  - Photos: stored bytes rendered with st.image
  - Occupancy: simulated in UI, no manual tab needed
  - Sort TypeError: groupby approach, no string negation
  - Auto-refresh removed (manual only)
  - UK + TR hospitals in maps_handler
  - ETA speed: 55 km/h fallback (was 30 km/h)
"""
from __future__ import annotations
import hashlib
import io
import logging
import sys
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue
from src.triage_engine import TRIAGE_EMERGENCY, TRIAGE_ROUTINE, TRIAGE_URGENT, TriageEngine
from src.health_db import get_full_record, list_demo_health_numbers, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure DB is ready
init_db()

st.set_page_config(page_title="CodeZero ER", page_icon="🏥", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', sans-serif; }
.block-container { padding: 1.2rem 2.2rem 2rem 2.2rem !important; }

/* Metrics */
div[data-testid="stMetric"] { background:#111827;border-radius:12px;padding:1rem 1.2rem;border:1px solid #1f2937; }
div[data-testid="stMetric"] label { color:#6b7280 !important;font-size:0.7rem !important;text-transform:uppercase;letter-spacing:0.08em; }
div[data-testid="stMetricValue"] { font-size:2rem !important;font-weight:800 !important;color:#f9fafb !important; }

/* Tabs */
div[data-testid="stTabs"] button { font-weight:600;font-size:0.9rem; }

/* Buttons */
.stButton > button { border-radius:8px;font-weight:600;font-size:0.85rem;min-height:36px; }

/* Patient card */
.cz-card { border-radius:14px;padding:1rem 1.2rem;margin-bottom:6px;border:1px solid #1f2937; }
.cz-e { border-left:4px solid #ef4444;background:linear-gradient(135deg,#1c0a0a,#111827); }
.cz-u { border-left:4px solid #f59e0b;background:linear-gradient(135deg,#1c1000,#111827); }
.cz-r { border-left:4px solid #10b981;background:linear-gradient(135deg,#001c0f,#111827); }

/* Badge */
.bx { display:inline-flex;align-items:center;padding:3px 9px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:2px 3px 2px 0;white-space:nowrap; }

/* Detail panel */
.dp { background:#0d1117;border:1px solid #21262d;border-radius:12px;padding:1.2rem 1.4rem;margin:4px 0 8px 0; }
.dp-section { margin-bottom:1rem; }
.dp-section:last-child { margin-bottom:0; }
.dp-title { font-size:0.68rem;color:#4b5563;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;margin-bottom:0.5rem;padding-bottom:0.4rem;border-bottom:1px solid #1f2937; }
.dp-grid { display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.8rem; }
.dp-field-label { font-size:0.68rem;color:#6b7280;margin-bottom:3px; }
.dp-field-value { font-size:0.9rem;font-weight:600;color:#e5e7eb; }

/* Expander */
div[data-testid="stExpander"] { border:1px solid #1f2937 !important;border-radius:10px !important;background:#0d1117 !important;margin-bottom:4px; }

/* Health record sections */
.hr-section { background:#0d1117;border:1px solid #21262d;border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.8rem; }
.hr-header  { font-size:0.68rem;color:#4b5563;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;padding-bottom:0.4rem;border-bottom:1px solid #1f2937;margin-bottom:0.8rem; }

/* Tracking board */
.track-card { border-radius:12px;padding:0.8rem 1rem;margin-bottom:6px;border:1px solid #1f2937;background:#0f172a; }
.track-e { border-left:4px solid #ef4444; }
.track-u { border-left:4px solid #f59e0b; }
.track-r { border-left:4px solid #10b981; }

/* Pill tags */
.pill-green  { display:inline-block;background:#14532d44;color:#4ade80;border:1px solid #16a34a44;padding:2px 9px;border-radius:20px;font-size:0.75rem;font-weight:600;margin:1px; }
.pill-red    { display:inline-block;background:#7f1d1d44;color:#f87171;border:1px solid #dc262644;padding:2px 9px;border-radius:20px;font-size:0.75rem;font-weight:600;margin:1px; }
.pill-yellow { display:inline-block;background:#78350f44;color:#fbbf24;border:1px solid #d9770644;padding:2px 9px;border-radius:20px;font-size:0.75rem;font-weight:600;margin:1px; }
.pill-blue   { display:inline-block;background:#1e3a5f44;color:#93c5fd;border:1px solid #3b82f644;padding:2px 9px;border-radius:20px;font-size:0.75rem;font-weight:600;margin:1px; }
.pill-gray   { display:inline-block;background:#1f293799;color:#9ca3af;border:1px solid #37415199;padding:2px 9px;border-radius:20px;font-size:0.75rem;font-weight:600;margin:1px; }
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

ICONS  = {TRIAGE_EMERGENCY:"🔴", TRIAGE_URGENT:"🟠", TRIAGE_ROUTINE:"🟢"}
COLORS = {TRIAGE_EMERGENCY:"#ef4444", TRIAGE_URGENT:"#f59e0b", TRIAGE_ROUTINE:"#10b981"}
CARD   = {TRIAGE_EMERGENCY:"cz-e",   TRIAGE_URGENT:"cz-u",    TRIAGE_ROUTINE:"cz-r"}
TRACK  = {TRIAGE_EMERGENCY:"track-e",TRIAGE_URGENT:"track-u", TRIAGE_ROUTINE:"track-r"}
PORDER = {TRIAGE_EMERGENCY:0, TRIAGE_URGENT:1, TRIAGE_ROUTINE:2}


def _hkey(prefix: str, s: str) -> str:
    return f"{prefix}_{hashlib.md5(s.encode()).hexdigest()[:10]}"


def _eta_str(arrival_iso, eta_raw) -> str:
    if arrival_iso:
        try:
            d = (datetime.fromisoformat(str(arrival_iso).replace("Z","+00:00"))
                 - datetime.now(timezone.utc)).total_seconds() / 60
            return "ARRIVED" if d <= 0 else f"{int(d)} min"
        except Exception:
            pass
    return f"~{eta_raw} min" if eta_raw else "N/A"


def _eta_seconds(arrival_iso, eta_raw) -> float:
    """Returns remaining seconds — used for live tracking sort."""
    if arrival_iso:
        try:
            d = (datetime.fromisoformat(str(arrival_iso).replace("Z","+00:00"))
                 - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, d)
        except Exception:
            pass
    return float(eta_raw or 999) * 60


# ── Health Record Panel (Tab 2 / inline) ─────────────────────────────────────
def render_health_record_panel(health_number: str) -> None:
    """Render full health record in a postvisit.ai inspired layout."""
    if not health_number:
        st.info("No health number provided for this patient.")
        return

    record = get_full_record(health_number.strip())
    if not record:
        st.warning(f"No health record found for: **{health_number}**")
        st.caption(f"Available demo numbers: {', '.join(list_demo_health_numbers())}")
        return

    p      = record["patient"]
    diags  = record["diagnoses"]
    meds   = record["medications"]
    labs   = record["lab_results"]
    vitals = record["vitals"]
    visits = record["visits"]
    allgs  = record["allergies"]

    # ── Patient profile banner ─────────────────────────────────────────────
    dob = p.get("date_of_birth","")
    try:
        age = (datetime.now().year - int(dob[:4]))
    except Exception:
        age = "?"

    st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);border:1px solid #334155;
     border-radius:14px;padding:1.2rem 1.4rem;margin-bottom:0.8rem;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
    <div>
      <p style="font-size:1.3rem;font-weight:800;color:#f9fafb;margin:0;">
        {p.get('first_name','')} {p.get('last_name','')}
      </p>
      <p style="color:#64748b;font-size:0.85rem;margin:0.2rem 0 0 0;">
        Health ID: <span style="color:#60a5fa;font-weight:600;">{health_number}</span>
      </p>
    </div>
    <div style="text-align:right;">
      <span class="pill-blue">🩸 {p.get('blood_type','?')}</span>
      <span class="pill-gray">{p.get('sex','')}</span>
      <span class="pill-gray">{age} yrs</span>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:0.6rem;margin-top:0.8rem;">
    <div><span style="color:#475569;font-size:0.7rem;">DATE OF BIRTH</span><br><span style="color:#e2e8f0;font-size:0.9rem;">{dob}</span></div>
    <div><span style="color:#475569;font-size:0.7rem;">NATIONALITY</span><br><span style="color:#e2e8f0;font-size:0.9rem;">{p.get('nationality','')}</span></div>
    <div><span style="color:#475569;font-size:0.7rem;">INSURANCE</span><br><span style="color:#e2e8f0;font-size:0.9rem;">{p.get('insurance_id','—')}</span></div>
    <div><span style="color:#475569;font-size:0.7rem;">GP / FAMILY DOCTOR</span><br><span style="color:#e2e8f0;font-size:0.9rem;">{p.get('gp_name','—')}</span></div>
    <div><span style="color:#475569;font-size:0.7rem;">PHONE</span><br><span style="color:#e2e8f0;font-size:0.9rem;">{p.get('phone','—')}</span></div>
    <div><span style="color:#475569;font-size:0.7rem;">EMERGENCY CONTACT</span><br><span style="color:#e2e8f0;font-size:0.9rem;">{p.get('emergency_name','—')} {p.get('emergency_phone','')}</span></div>
  </div>
  {"<p style='margin:0.6rem 0 0;color:#94a3b8;font-size:0.85rem;font-style:italic;'>📝 " + p.get('notes','') + "</p>" if p.get('notes') else ""}
</div>
""", unsafe_allow_html=True)

    # ── Allergies ──────────────────────────────────────────────────────────
    if allgs:
        allg_html = "".join(
            f'<span class="pill-red" title="{a["reaction"]} — {a["severity"]}">⚠️ {a["allergen"]}</span>'
            for a in allgs
        )
        st.markdown(f'<div class="hr-section"><div class="hr-header">🚨 Allergies</div>{allg_html}</div>', unsafe_allow_html=True)

    # ── Current vitals ─────────────────────────────────────────────────────
    if vitals:
        v = vitals[0]
        bmi_color = "#f87171" if (v.get("bmi") or 0) >= 30 else "#4ade80" if (v.get("bmi") or 0) >= 18.5 else "#fbbf24"
        spo2_color = "#f87171" if (v.get("spo2") or 99) < 95 else "#4ade80"
        bp_sys = v.get("bp_systolic") or 0
        bp_color = "#f87171" if bp_sys >= 140 else "#4ade80" if bp_sys < 130 else "#fbbf24"

        st.markdown(f"""
<div class="hr-section">
  <div class="hr-header">❤️ Latest Vitals — {(v.get('recorded_at','')[:10])}</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:0.7rem;">
    <div style="background:#111827;border-radius:10px;padding:0.7rem;text-align:center;">
      <div style="font-size:0.65rem;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">BP</div>
      <div style="font-size:1.3rem;font-weight:800;color:{bp_color};">{v.get('bp_systolic','?')}/{v.get('bp_diastolic','?')}</div>
      <div style="font-size:0.7rem;color:#4b5563;">mmHg</div>
    </div>
    <div style="background:#111827;border-radius:10px;padding:0.7rem;text-align:center;">
      <div style="font-size:0.65rem;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">Heart Rate</div>
      <div style="font-size:1.3rem;font-weight:800;color:#f9fafb;">{v.get('heart_rate','?')}</div>
      <div style="font-size:0.7rem;color:#4b5563;">bpm</div>
    </div>
    <div style="background:#111827;border-radius:10px;padding:0.7rem;text-align:center;">
      <div style="font-size:0.65rem;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">SpO₂</div>
      <div style="font-size:1.3rem;font-weight:800;color:{spo2_color};">{v.get('spo2','?')}%</div>
      <div style="font-size:0.7rem;color:#4b5563;">oxygen</div>
    </div>
    <div style="background:#111827;border-radius:10px;padding:0.7rem;text-align:center;">
      <div style="font-size:0.65rem;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">BMI</div>
      <div style="font-size:1.3rem;font-weight:800;color:{bmi_color};">{v.get('bmi','?')}</div>
      <div style="font-size:0.7rem;color:#4b5563;">{v.get('weight_kg','?')}kg · {v.get('height_cm','?')}cm</div>
    </div>
    <div style="background:#111827;border-radius:10px;padding:0.7rem;text-align:center;">
      <div style="font-size:0.65rem;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">Glucose</div>
      <div style="font-size:1.3rem;font-weight:800;color:#f9fafb;">{v.get('glucose','?')}</div>
      <div style="font-size:0.7rem;color:#4b5563;">mmol/L</div>
    </div>
    <div style="background:#111827;border-radius:10px;padding:0.7rem;text-align:center;">
      <div style="font-size:0.65rem;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">Temp</div>
      <div style="font-size:1.3rem;font-weight:800;color:#f9fafb;">{v.get('temperature','?')}°C</div>
      <div style="font-size:0.7rem;color:#4b5563;">body temp</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Diagnoses ──────────────────────────────────────────────────────────
    if diags:
        st.markdown('<div class="hr-section"><div class="hr-header">🩺 Active Diagnoses</div>', unsafe_allow_html=True)
        for d in diags:
            pill_cls = "pill-red" if d.get("status") == "active" else "pill-gray"
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;padding:0.5rem 0;border-bottom:1px solid #1f2937;">
  <div>
    <span style="color:#e5e7eb;font-size:0.92rem;font-weight:600;">{d['description']}</span>
    <span class="pill-gray" style="margin-left:6px;font-size:0.68rem;">{d.get('icd_code','')}</span>
    <p style="color:#4b5563;font-size:0.8rem;margin:2px 0 0 0;">Diagnosed {d.get('diagnosed_date','')} · {d.get('diagnosing_doctor','')}</p>
    {"<p style='color:#6b7280;font-size:0.78rem;margin:1px 0 0 0;'>" + d.get('notes','') + "</p>" if d.get('notes') else ""}
  </div>
  <span class="{pill_cls}">{d.get('status','').upper()}</span>
</div>
""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Medications ────────────────────────────────────────────────────────
    active_meds = [m for m in meds if m.get("status") == "active"]
    if active_meds:
        st.markdown('<div class="hr-section"><div class="hr-header">💊 Current Medications</div>', unsafe_allow_html=True)
        for m in active_meds:
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;padding:0.45rem 0;border-bottom:1px solid #1f2937;">
  <div>
    <span style="color:#93c5fd;font-size:0.92rem;font-weight:600;">{m['name']}</span>
    <span class="pill-gray">{m.get('dosage','')}</span>
    <p style="color:#6b7280;font-size:0.8rem;margin:2px 0 0 0;">{m.get('frequency','')} · {m.get('prescribing_doctor','')}</p>
  </div>
  <span class="pill-green">ACTIVE</span>
</div>
""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Lab results ────────────────────────────────────────────────────────
    if labs:
        st.markdown('<div class="hr-section"><div class="hr-header">🧪 Lab Results</div>', unsafe_allow_html=True)
        recent_labs = labs[:8]
        for lab in recent_labs:
            stat = lab.get("status","normal")
            pill = "pill-red" if stat == "high" else "pill-green" if stat == "normal" else "pill-yellow"
            st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;padding:0.4rem 0;border-bottom:1px solid #1f2937;">
  <div>
    <span style="color:#e5e7eb;font-size:0.9rem;font-weight:600;">{lab['test_name']}</span>
    <span style="color:#6b7280;font-size:0.8rem;margin-left:8px;">{lab.get('test_date','')[:10]}</span>
    <p style="color:#4b5563;font-size:0.75rem;margin:1px 0 0 0;">Ref: {lab.get('reference_range','')}</p>
  </div>
  <div style="text-align:right;">
    <span style="color:#f9fafb;font-size:0.95rem;font-weight:700;">{lab.get('value','')}</span>
    <br><span class="{pill}">{stat.upper()}</span>
  </div>
</div>
""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Past visits ────────────────────────────────────────────────────────
    if visits:
        st.markdown('<div class="hr-section"><div class="hr-header">🏥 Previous Hospital Visits</div>', unsafe_allow_html=True)
        for v in visits[:5]:
            type_pill = "pill-red" if v.get("visit_type") == "Emergency" else "pill-blue"
            st.markdown(f"""
<div style="padding:0.5rem 0;border-bottom:1px solid #1f2937;">
  <div style="display:flex;justify-content:space-between;">
    <span style="color:#e2e8f0;font-size:0.9rem;font-weight:600;">{v.get('hospital','')}</span>
    <span style="color:#64748b;font-size:0.8rem;">{v.get('visit_date','')[:10]}</span>
  </div>
  <div style="margin:2px 0;">
    <span class="{type_pill}">{v.get('visit_type','')}</span>
    <span class="pill-gray">{v.get('department','')}</span>
  </div>
  <p style="color:#94a3b8;font-size:0.83rem;margin:2px 0 0 0;"><strong>Complaint:</strong> {v.get('chief_complaint','')}</p>
  <p style="color:#64748b;font-size:0.8rem;margin:1px 0 0 0;"><strong>Diagnosis:</strong> {v.get('diagnosis','')}</p>
</div>
""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── Visit detail (Tab 1) ──────────────────────────────────────────────────────
def _build_visit_detail_html(p: dict) -> str:
    lvl        = p.get("triage_level", TRIAGE_URGENT)
    pid        = p.get("patient_id", "UNKNOWN")
    age        = p.get("age_range") or "—"
    sex        = p.get("sex") or "—"
    lang       = (p.get("language") or "en")[:5].upper()
    risk       = p.get("risk_score", 5)
    comp_orig  = p.get("complaint_text", p.get("chief_complaint",""))  # original language
    comp_eng   = p.get("chief_complaint","")
    asmt       = p.get("assessment","")
    flags      = [f.replace("_"," ").title() for f in p.get("red_flags",[]) if f != "none_identified"]
    conds      = p.get("suspected_conditions",[])
    dest       = p.get("destination_hospital","")
    reg        = p.get("reg_number","")
    rec_action = p.get("recommended_action","")
    time_sens  = p.get("time_sensitivity","")
    src_gl     = ", ".join(p.get("source_guidelines",[]))
    ts         = (p.get("timestamp","")[:16] or "").replace("T"," ")
    eta        = _eta_str(p.get("arrival_time"), p.get("eta_minutes"))
    clr        = COLORS.get(lvl,"#f59e0b")
    risk_clr   = "#ef4444" if risk>=8 else "#f59e0b" if risk>=5 else "#10b981"
    icon       = ICONS.get(lvl,"🟠")

    # Q&A transcript
    qa = p.get("qa_transcript",[])
    qa_html = ""
    if qa:
        rows = "".join(
            f'<div style="padding:0.4rem 0;border-bottom:1px solid #1f2937;"><span style="color:#6b7280;font-size:0.78rem;text-transform:uppercase;">Q:</span> <span style="color:#cbd5e1;font-size:0.88rem;">{q.get("question","")}</span><br><span style="color:#6b7280;font-size:0.78rem;text-transform:uppercase;">A:</span> <span style="color:#86efac;font-size:0.9rem;font-weight:600;">{q.get("answer","")}</span></div>'
            for q in qa
        )
        qa_html = '<div class="dp-section"><div class="dp-title">💬 Q&A Transcript</div>' + rows + '</div>'

    # Flags
    flags_html = ""
    if flags:
        badges = "".join(f'<span class="bx" style="background:#ef444422;color:#fca5a5;border:1px solid #ef444455;">{f}</span>' for f in flags)
        flags_html = '<div class="dp-section"><div class="dp-title">🚩 Red Flags</div><div style="display:flex;flex-wrap:wrap;gap:5px;">' + badges + '</div></div>'

    conds_html = ""
    if conds:
        conds_html = '<div class="dp-grid"><div><div class="dp-field-label">Suspected Conditions</div><div class="dp-field-value" style="color:#93c5fd;">' + " · ".join(conds) + '</div></div></div>'

    actions_html = ""
    if rec_action:
        actions_html = (
            '<div class="dp-section"><div class="dp-title">📋 Actions</div>'
            '<div class="dp-grid">'
            '<div><div class="dp-field-label">Recommended Action</div><div class="dp-field-value">' + rec_action + '</div></div>'
            '<div><div class="dp-field-label">Time Sensitivity</div><div class="dp-field-value" style="color:' + clr + ';">' + time_sens + '</div></div>'
            '</div></div>'
        )

    dest_html = ""
    if dest:
        dest_html = '<div class="dp-section"><div class="dp-title">🏥 Destination Hospital</div><p style="color:#e5e7eb;font-size:0.9rem;font-weight:600;margin:0;">' + dest + '</p></div>'

    src_html = ""
    if src_gl:
        src_html = '<div class="dp-section"><div class="dp-title">📚 Source Guidelines</div><p style="color:#6b7280;font-size:0.82rem;margin:0;">' + src_gl + '</p></div>'

    transcript_html = ""
    if comp_orig and comp_orig != comp_eng:
        transcript_html = (
            '<div class="dp-section"><div class="dp-title">🗣️ Patient\'s Own Words</div>'
            '<p style="color:#fde68a;font-size:0.92rem;margin:0;font-style:italic;">"' + comp_orig + '"</p>'
            '<p style="color:#94a3b8;font-size:0.82rem;margin:0.3rem 0 0 0;">English: ' + comp_eng + '</p>'
            '</div>'
        )
    else:
        transcript_html = (
            '<div class="dp-section"><div class="dp-title">🗣️ Chief Complaint</div>'
            '<p style="color:#e5e7eb;font-size:0.92rem;margin:0;font-weight:500;">' + comp_eng + '</p>'
            '</div>'
        )

    return (
        '<div class="dp">'
        # Header
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;padding-bottom:0.8rem;border-bottom:1px solid #21262d;flex-wrap:wrap;gap:6px;">'
        '<div>'
        '<span style="font-size:1.05rem;font-weight:800;color:#f9fafb;">' + icon + ' ' + lvl + '</span>'
        '<span style="color:#4b5563;font-size:0.9rem;margin-left:8px;">' + pid + '</span>'
        '</div>'
        '<div style="display:flex;gap:6px;flex-wrap:wrap;">'
        '<span class="bx" style="background:' + risk_clr + '22;color:' + risk_clr + ';border:1px solid ' + risk_clr + '55;">Risk ' + str(risk) + '/10</span>'
        '<span class="bx" style="background:#1f2937;color:#9ca3af;border:1px solid #374151;">Submitted ' + ts + '</span>'
        '</div></div>'
        # Demographics
        '<div class="dp-section"><div class="dp-title">👤 Demographics</div>'
        '<div class="dp-grid">'
        '<div><div class="dp-field-label">Age Range</div><div class="dp-field-value">' + age + '</div></div>'
        '<div><div class="dp-field-label">Sex</div><div class="dp-field-value">' + sex + '</div></div>'
        '<div><div class="dp-field-label">Language</div><div class="dp-field-value">' + lang + '</div></div>'
        '<div><div class="dp-field-label">ETA</div><div class="dp-field-value" style="color:' + clr + ';">' + eta + '</div></div>'
        '</div></div>'
        + transcript_html
        # Assessment
        + '<div class="dp-section"><div class="dp-title">🩺 AI Clinical Assessment</div>'
        '<p style="color:#d1d5db;font-size:0.87rem;margin:0 0 0.7rem;line-height:1.6;">' + asmt + '</p>'
        + conds_html
        + '</div>'
        + flags_html
        + actions_html
        + qa_html
        + dest_html
        + src_html
        + '</div>'
    )


# ── Patient card (compact + expandable) ──────────────────────────────────────
def render_patient_card(p: dict, show_tracking: bool = False) -> None:
    lvl       = p.get("triage_level", TRIAGE_URGENT)
    pid       = p.get("patient_id","UNKNOWN")
    stat      = p.get("status","incoming")
    eta       = _eta_str(p.get("arrival_time"), p.get("eta_minutes"))
    age       = p.get("age_range") or "—"
    sex       = p.get("sex") or "—"
    lang      = (p.get("language") or "en")[:5].upper()
    risk      = p.get("risk_score",5)
    comp      = p.get("chief_complaint","")
    asmt      = p.get("assessment","")
    flags     = [f.replace("_"," ").title() for f in p.get("red_flags",[]) if f != "none_identified"]
    dest      = p.get("destination_hospital","")
    has_photo = bool(p.get("has_photo"))
    ph_count  = p.get("photo_count",0)

    clr       = COLORS.get(lvl,"#f59e0b")
    risk_clr  = "#ef4444" if risk>=8 else "#f59e0b" if risk>=5 else "#10b981"
    stat_bg   = {"incoming":"#92400e","arrived":"#1e3a5f","in_treatment":"#4c1d95","discharged":"#14532d"}.get(stat,"#374151")
    photo_bx  = f'<span class="bx" style="background:#5b21b644;color:#a78bfa;border:1px solid #7c3aed;">📷 {ph_count} photo{"s" if ph_count!=1 else ""}</span>' if has_photo else ""
    flags_row = ""
    if flags:
        flags_row = "<p style='margin:0.15rem 0 0;font-size:0.79rem;'><span style='color:#ef4444;'>🚩</span> <span style='color:#fca5a5;'>" + " · ".join(flags[:4]) + "</span></p>"
    dest_row  = "<p style='margin:0.12rem 0 0;font-size:0.79rem;color:#4b5563;'>🏥 " + dest + "</p>" if dest else ""

    st.markdown(
        '<div class="cz-card ' + CARD.get(lvl,"cz-u") + '">'
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px;">'
        '<span style="font-size:0.98rem;font-weight:800;color:#f9fafb;">' + ICONS.get(lvl,"🟠") + ' ' + lvl + '</span>'
        '<span style="color:#4b5563;font-size:0.87rem;">— ' + pid + '</span>'
        '<span class="bx" style="background:' + stat_bg + '44;color:#e5e7eb;border:1px solid ' + stat_bg + ';">' + stat.replace("_"," ").upper() + '</span>'
        + photo_bx +
        '</div>'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:4px;">'
        '<span class="bx" style="background:#1f293799;color:#9ca3af;border:1px solid #374151;">🧑 ' + age + '</span>'
        '<span class="bx" style="background:#1f293799;color:#9ca3af;border:1px solid #374151;">⚧ ' + sex + '</span>'
        '<span class="bx" style="background:#1f293799;color:#9ca3af;border:1px solid #374151;">🌐 ' + lang + '</span>'
        '<span class="bx" style="background:' + risk_clr + '22;color:' + risk_clr + ';border:1px solid ' + risk_clr + '55;">⚡ ' + str(risk) + '/10</span>'
        '<span style="color:#6b7280;font-size:0.8rem;">⏱ ' + eta + '</span>'
        '</div></div>'
        "<p style='margin:0.45rem 0 0.12rem;color:#6b7280;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.06em;'>Complaint</p>"
        "<p style='margin:0 0 0.2rem;color:#f3f4f6;font-size:0.92rem;font-weight:600;'>" + comp + "</p>"
        "<p style='margin:0;color:#6b7280;font-size:0.82rem;line-height:1.45;'>" + asmt[:160] + ("…" if len(asmt)>160 else "") + "</p>"
        + flags_row + dest_row +
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Expandable patient detail (two tabs: visit + health record) ────────
    with st.expander("📋 This Visit — " + pid):
        # Tab 1: visit details
        t1, t2 = st.tabs(["🩺 This Visit", "🗂 Health Record"])

        with t1:
            st.markdown(_build_visit_detail_html(p), unsafe_allow_html=True)

            # Photos — render actual images if available
            if has_photo:
                st.markdown('<div class="dp-section"><div class="dp-title" style="padding:0.3rem 0;">📷 Patient Photos</div>', unsafe_allow_html=True)
                photo_bytes_list = p.get("photos_bytes", [])
                if photo_bytes_list:
                    cols = st.columns(min(len(photo_bytes_list), 3))
                    for i, pb in enumerate(photo_bytes_list):
                        with cols[i % 3]:
                            try:
                                st.image(pb, use_container_width=True, caption=f"Photo {i+1}")
                            except Exception:
                                st.markdown(f'<p style="color:#a78bfa;">📷 Photo {i+1} (preview unavailable)</p>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<p style="color:#a78bfa;font-size:0.87rem;">Patient attached {ph_count} photo(s). Photos visible in patient app.</p>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

        with t2:
            hn = p.get("health_number","")
            if hn:
                render_health_record_panel(hn)
            else:
                st.info("No health number provided by this patient.")
                # Cannot nest expanders — use text_input directly
                hn_input = st.text_input(
                    "🔍 Look up by health number",
                    key=_hkey("hn_lookup", pid),
                    placeholder="e.g. DE-1985-447291 · UK-1990-334872 · TR-1972-881043",
                )
                if hn_input and len(hn_input) > 5:
                    render_health_record_panel(hn_input)

    # ── Pre-arrival prep ────────────────────────────────────────────────────
    if stat == "incoming":
        with st.expander("🏥 Pre-Arrival Prep — " + pid, expanded=(lvl == TRIAGE_EMERGENCY)):
            if pid not in _PREP_CACHE:
                with st.spinner("Generating checklist..."):
                    try:
                        _PREP_CACHE[pid] = triage_engine.generate_hospital_prep(
                            chief_complaint=p.get("chief_complaint","unknown"),
                            assessment=p,
                        )
                    except Exception as exc:
                        logger.error("Prep failed %s: %s", pid, exc)
                        _PREP_CACHE[pid] = ["Assign appropriate bay","Alert attending physician","Prepare standard monitoring"]
            for item in _PREP_CACHE.get(pid,[]):
                st.checkbox(item, key=_hkey("prep_" + pid, item))

    # ── Action buttons ────────────────────────────────────────────────────
    c1, c2, c3, _ = st.columns([2,2,2,3])
    with c1:
        if stat=="incoming" and st.button("✅ Arrived", key="arr_"+pid, use_container_width=True):
            hospital_queue.update_status(pid,"arrived"); st.rerun()
    with c2:
        if stat=="arrived" and st.button("🩺 Treating", key="trt_"+pid, use_container_width=True):
            hospital_queue.update_status(pid,"in_treatment"); st.rerun()
    with c3:
        if stat=="in_treatment" and st.button("🏠 Discharge", key="dis_"+pid, use_container_width=True):
            hospital_queue.update_status(pid,"discharged"); st.rerun()

    st.markdown("<div style='margin-bottom:0.4rem'></div>", unsafe_allow_html=True)


# ── Live tracking board ────────────────────────────────────────────────────────
def render_tracking_board() -> None:
    """Real-time countdown board for all en-route patients."""
    st.subheader("📡 Live Patient Tracking")
    st.caption("All incoming patients sorted by time to arrival — auto-refresh manually with the sidebar button")

    incoming = hospital_queue.get_incoming_patients(limit=50)

    if not incoming:
        st.markdown("""
<div style="text-align:center;padding:3rem;color:#4b5563;">
  <div style="font-size:3rem;">📡</div>
  <p>No patients en route — waiting for triage submissions</p>
</div>""", unsafe_allow_html=True)
        return

    # Sort by seconds remaining (soonest first)
    sorted_patients = sorted(
        incoming,
        key=lambda p: _eta_seconds(p.get("arrival_time"), p.get("eta_minutes"))
    )

    now = datetime.now(timezone.utc)
    for p in sorted_patients:
        lvl       = p.get("triage_level", TRIAGE_URGENT)
        pid       = p.get("patient_id","?")
        eta_str   = _eta_str(p.get("arrival_time"), p.get("eta_minutes"))
        secs_left = _eta_seconds(p.get("arrival_time"), p.get("eta_minutes"))
        is_arrived = secs_left <= 0
        comp      = p.get("chief_complaint","")
        dest      = p.get("destination_hospital","")
        age       = p.get("age_range") or "—"
        sex       = p.get("sex") or "—"
        risk      = p.get("risk_score",5)
        risk_clr  = "#ef4444" if risk>=8 else "#f59e0b" if risk>=5 else "#10b981"
        clr       = COLORS.get(lvl,"#f59e0b")

        if is_arrived:
            eta_display = '<span style="color:#22c55e;font-size:1.3rem;font-weight:800;">ARRIVED</span>'
        else:
            mins = int(secs_left // 60)
            secs_rem = int(secs_left % 60)
            eta_display = f'<span style="color:{clr};font-size:1.3rem;font-weight:800;">{mins}:{secs_rem:02d}</span><span style="color:#64748b;font-size:0.85rem;"> remaining</span>'

        st.markdown(f"""
<div class="track-card {TRACK.get(lvl,'track-u')}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">
    <div>
      <span style="font-size:0.92rem;font-weight:700;color:#f9fafb;">{ICONS.get(lvl,'🟠')} {pid}</span>
      <span class="bx" style="background:#1f293799;color:#9ca3af;border:1px solid #374151;margin-left:6px;">🧑 {age}</span>
      <span class="bx" style="background:#1f293799;color:#9ca3af;border:1px solid #374151;">⚧ {sex}</span>
      <span class="bx" style="background:{risk_clr}22;color:{risk_clr};border:1px solid {risk_clr}55;">Risk {risk}/10</span>
    </div>
    <div style="text-align:right;">
      {eta_display}
    </div>
  </div>
  <p style="color:#94a3b8;font-size:0.85rem;margin:0.3rem 0 0.1rem 0;">{comp[:80]}{"…" if len(comp)>80 else ""}</p>
  {"<p style='color:#4b5563;font-size:0.8rem;margin:0;'>🏥 " + dest + "</p>" if dest else ""}
</div>
""", unsafe_allow_html=True)

        if is_arrived:
            if st.button("✅ Mark Arrived", key="track_arr_"+pid, use_container_width=False):
                hospital_queue.update_status(pid,"arrived"); st.rerun()


# ── All records table ─────────────────────────────────────────────────────────
def render_all_table(patients: list[dict]) -> None:
    if not patients:
        st.info("No records yet."); return
    try:
        import pandas as pd
        df   = pd.DataFrame(patients)
        cols = ["patient_id","triage_level","chief_complaint","age_range","sex",
                "risk_score","eta_minutes","destination_hospital","language","status","timestamp"]
        st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)
    except Exception as e:
        logger.error(e)
        for p in patients: st.write(p)


# ── Health Record lookup page ──────────────────────────────────────────────────
def render_health_lookup_page() -> None:
    st.subheader("🗂 Health Record Lookup")
    st.caption("Enter a patient's national health / insurance number to access their full medical history")

    col1, col2 = st.columns([3,1])
    with col1:
        hn = st.text_input(
            "Health Number",
            placeholder="e.g. DE-1985-447291 · UK-1990-334872 · TR-1972-881043",
            label_visibility="collapsed",
            key="health_lookup_input",
        )
    with col2:
        search = st.button("Look up →", type="primary", use_container_width=True, key="health_lookup_btn")

    # Demo shortcuts
    demo_nums = list_demo_health_numbers()
    st.caption("Demo records: " + "   ".join([f"`{n}`" for n in demo_nums]))

    if search and hn:
        render_health_record_panel(hn.strip())
    elif not search and not hn:
        st.markdown("""
<div style="background:#0d1117;border:1px solid #21262d;border-radius:12px;padding:2rem;text-align:center;margin-top:1rem;">
  <div style="font-size:2.5rem;">🗂</div>
  <p style="color:#4b5563;margin:0.5rem 0 0 0;">Enter a health number above to view the full patient record</p>
</div>
""", unsafe_allow_html=True)


# ── Test helpers ──────────────────────────────────────────────────────────────
def _mk(complaint, asmt_dict, lang, eta, demographics, dest, health_number=""):
    r = triage_engine.create_patient_record(
        chief_complaint=complaint, assessment=asmt_dict,
        language=lang, eta_minutes=eta, demographics=demographics,
    )
    r["destination_hospital"] = dest
    r["health_number"]  = health_number
    r["complaint_text"] = complaint
    r["qa_transcript"]  = [
        {"question":"How long have you had this symptom?","answer":"Just started, about 15 minutes ago"},
        {"question":"Rate your pain 1-10","answer":"8"},
        {"question":"Does the pain radiate?","answer":"Yes, to my left arm and jaw"},
    ]
    hospital_queue.add_patient(r)
    return r["patient_id"]

def _add_emergency():
    pid = _mk("Severe chest pain with arm radiation and sweating",
        {"triage_level":TRIAGE_EMERGENCY,"assessment":"3 red flags: radiation, diaphoresis, dyspnea. Possible ACS.",
         "red_flags":["pain_radiation","diaphoresis","dyspnea"],"recommended_action":"Activate cath lab immediately.",
         "risk_score":9,"source_guidelines":["chest_pain_protocol.txt"],
         "suspected_conditions":["Acute Coronary Syndrome"],"time_sensitivity":"Within 10 minutes"},
        "de-DE",12,{"age_range":"45-59","sex":"Male"},
        "Klinikum Stuttgart – Katharinenhospital", "DE-1985-447291")
    st.success("Added EMERGENCY: " + pid)

def _add_urgent():
    pid = _mk("Sudden severe headache and vomiting for 2 hours",
        {"triage_level":TRIAGE_URGENT,"assessment":"Thunderclap headache — SAH must be excluded.",
         "red_flags":["thunderclap_headache","vomiting"],"recommended_action":"CT head within 30 minutes.",
         "risk_score":7,"source_guidelines":[],"suspected_conditions":["SAH","Migraine"],
         "time_sensitivity":"Within 30 minutes"},
        "tr-TR",22,{"age_range":"30-44","sex":"Female"},
        "Robert-Bosch-Krankenhaus Stuttgart","TR-1972-881043")
    st.success("Added URGENT: " + pid)

def _add_routine():
    pid = _mk("Mild headache for 2 days, no fever",
        {"triage_level":TRIAGE_ROUTINE,"assessment":"Pain 3/10. No red flags. Tension headache.",
         "red_flags":["none_identified"],"recommended_action":"See GP if persists 48h.",
         "risk_score":2,"source_guidelines":[],"suspected_conditions":["Tension Headache"],
         "time_sensitivity":"Within 48 hours"},
        "en-US",45,{"age_range":"18-29","sex":"Female"},
        "Universitätsklinikum Tübingen","UK-1990-334872")
    st.success("Added ROUTINE: " + pid)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    now_str = datetime.now(timezone.utc).strftime("%d %b %Y  %H:%M UTC")

    h1, h2 = st.columns([6,1])
    with h1:
        st.markdown("## 🏥 CodeZero — ER Command Center")
    with h2:
        st.markdown(f'<div style="text-align:right;padding-top:0.8rem;color:#4b5563;font-size:0.8rem;">{now_str}</div>', unsafe_allow_html=True)

    stats = hospital_queue.get_queue_stats()
    by_lv = stats.get("by_level",{})
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("📥 Incoming",  stats.get("total_incoming",0))
    m2.metric("🔴 Emergency", by_lv.get(TRIAGE_EMERGENCY,0))
    m3.metric("🟠 Urgent",    by_lv.get(TRIAGE_URGENT,0))
    m4.metric("🟢 Routine",   by_lv.get(TRIAGE_ROUTINE,0))
    m5.metric("✅ Treated",   stats.get("total_treated", stats.get("total_discharged",0)))
    st.divider()

    t_in, t_track, t_all, t_rec, t_adm = st.tabs([
        "📥 Incoming",
        "📡 Live Tracking",
        "📊 All Records",
        "🗂 Health Records",
        "⚙️ Admin",
    ])

    with t_in:
        incoming = hospital_queue.get_incoming_patients(limit=40)
        if not incoming:
            st.markdown('<div style="text-align:center;padding:3rem;color:#4b5563;"><div style="font-size:3rem;">🏥</div><p>No incoming patients yet.</p></div>', unsafe_allow_html=True)
        else:
            sc, _ = st.columns([2,5])
            with sc:
                sm = st.selectbox("Sort",["newest_first","by_category","by_eta"],
                    format_func=lambda x:{"newest_first":"🕐 Newest","by_category":"🔴 Category","by_eta":"⏱ Soonest"}[x],
                    key="sort_mode",label_visibility="collapsed")
            if sm=="newest_first":
                out = list(reversed(incoming))
            elif sm=="by_category":
                srt = sorted(incoming, key=lambda p: PORDER.get(p.get("triage_level",TRIAGE_URGENT),1))
                out = []
                for _,grp in groupby(srt,key=lambda p:PORDER.get(p.get("triage_level",TRIAGE_URGENT),1)):
                    out.extend(sorted(list(grp),key=lambda p:p.get("timestamp",""),reverse=True))
            else:
                out = sorted(incoming,key=lambda p:p.get("eta_minutes",999))
            for p in out:
                render_patient_card(p)

    with t_track:
        render_tracking_board()

    with t_all:
        render_all_table(hospital_queue.get_all_patients(limit=100))

    with t_rec:
        render_health_lookup_page()

    with t_adm:
        st.subheader("⚙️ Admin")
        with st.expander("Add Test Patients",expanded=True):
            c1,c2,c3 = st.columns(3)
            with c1:
                if st.button("➕ Emergency",use_container_width=True,type="primary"): _add_emergency(); st.rerun()
            with c2:
                if st.button("➕ Urgent",use_container_width=True): _add_urgent(); st.rerun()
            with c3:
                if st.button("➕ Routine",use_container_width=True): _add_routine(); st.rerun()
        st.divider()
        if st.button("🗑 Clear All",type="secondary"):
            hospital_queue.clear_queue(); st.success("Cleared."); st.rerun()

    with st.sidebar:
        st.markdown("### 🏥 CodeZero ER")
        st.divider()
        st.markdown("**Priority**")
        st.markdown("🔴 Emergency — < 10 min")
        st.markdown("🟠 Urgent — < 30 min")
        st.markdown("🟢 Routine — < 2 hours")
        st.divider()
        st.markdown("**Health Number Formats**")
        st.markdown("`DE-YYYY-XXXXXX`")
        st.markdown("`UK-YYYY-XXXXXX`")
        st.markdown("`TR-YYYY-XXXXXX`")
        st.divider()
        if st.button("🔄 Refresh",use_container_width=True,type="primary"):
            st.rerun()


if __name__ == "__main__":
    main()