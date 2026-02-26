"""
CodeZero Patient App — v2.0
============================
Scenario flow:
  1. INPUT        — Voice (mic) or text. Minimal UI. GPS auto-detected.
  2. PHOTOS       — Optional 1–3 photos (add / delete / re-add)
  3. DEMOGRAPHICS — Age range + sex (2 quick questions)
  4. QUESTIONS    — AI follow-up questions + health number + data sharing consent
  5. TRIAGE       — Emergency call button (112/999/112) OR nearest 3 hospitals
                    with distance, ETA, occupancy
  6. RESULT       — DO / DON'T list, registration number, location tracking note

Hospital dashboard receives:
  - Transcript, photos flag, Q&A, AI assessment, demographics, health record link
"""
from __future__ import annotations
import hashlib
import logging
import os
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue
from src.knowledge_indexer import KnowledgeIndexer
from src.maps_handler import MapsHandler
from src.triage_engine import (
    DEMOGRAPHIC_QUESTIONS,
    TRIAGE_COLORS,
    TRIAGE_EMERGENCY,
    TRIAGE_ROUTINE,
    TRIAGE_URGENT,
    TriageEngine,
)
from src.translator import Translator
from src.health_db import get_patient, get_full_record, get_age, list_demo_health_numbers

try:
    from src.speech_handler import SpeechHandler
    _HAS_SPEECH = True
except Exception:
    _HAS_SPEECH = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RTL_LOCALES = {"ar-SA", "ar-EG", "ar-AE", "he-IL", "fa-IR", "ur-PK"}

# Emergency numbers by detected country (from phone locale / GPS)
EMERGENCY_NUMBERS: dict[str, dict] = {
    "de": {"number": "112", "label": "Notruf"},
    "en-GB": {"number": "999", "label": "Emergency"},
    "tr": {"number": "112", "label": "Acil"},
    "en": {"number": "112", "label": "Emergency"},
    "fr": {"number": "15", "label": "SAMU"},
    "nl": {"number": "112", "label": "Spoed"},
    "default": {"number": "112", "label": "Emergency"},
}

# Simulated ER occupancy (in production: real-time hospital API)
_SIMULATED_OCCUPANCY = ["🟢 Low", "🟡 Moderate", "🟠 High", "🔴 Full"]

def _sim_occupancy(hospital_name: str) -> str:
    # Deterministic but varied per hospital name
    h = int(hashlib.md5(hospital_name.encode()).hexdigest()[:4], 16) % 4
    return _SIMULATED_OCCUPANCY[h]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="CodeZero", page_icon="🚑", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', sans-serif; }

.block-container { max-width: 500px; padding: 1rem 1rem 4rem 1rem !important; }

/* Big tap-friendly buttons */
.stButton > button {
    min-height: 60px !important; font-size: 1.15rem !important;
    font-weight: 700 !important; border-radius: 14px !important;
    letter-spacing: 0.01em; transition: transform 0.1s;
}
.stButton > button:active { transform: scale(0.97); }

/* Radio — pill style */
div[data-testid="stRadio"] > div { gap: 8px !important; flex-direction: column !important; }
div[data-testid="stRadio"] > div > label {
    font-size: 1.15rem !important; padding: 16px 20px !important;
    border: 2px solid #334155 !important; border-radius: 12px !important;
    min-height: 56px !important; cursor: pointer !important;
    width: 100% !important; display: flex !important; align-items: center !important;
    color: #f1f5f9 !important;
}
div[data-testid="stRadio"] > div > label:hover { border-color: #3b82f6 !important; background: rgba(59,130,246,0.1) !important; }
div[data-testid="stRadio"] > div > label:has(input:checked) { border-color: #3b82f6 !important; background: rgba(59,130,246,0.15) !important; }

/* Text area */
textarea { font-size: 1.1rem !important; border-radius: 12px !important; }

/* Progress bar */
div[data-testid="stProgress"] > div > div { background: #3b82f6 !important; }

/* Audio input */
div[data-testid="stAudioInput"] { margin: 0.5rem 0; }

/* Input fields */
input[type="text"], input[type="number"] { font-size: 1rem !important; }

/* Hospital card */
.hosp-card {
    border: 2px solid #1e293b; border-radius: 14px;
    padding: 1rem 1.1rem; margin-bottom: 0.6rem;
    background: #0f172a; transition: border-color 0.15s;
}
.hosp-card.fastest { border-color: #22c55e; background: #052e16; }
.hosp-card.second  { border-color: #1e293b; }

/* DO/DON'T list */
.do-item   { color: #4ade80; font-size: 1rem; padding: 4px 0; }
.dont-item { color: #f87171; font-size: 1rem; padding: 4px 0; }

/* Registration number box */
.reg-box {
    background: #0f172a; border: 2px solid #3b82f6;
    border-radius: 12px; padding: 0.8rem 1rem; text-align: center;
    font-size: 1.8rem; font-weight: 800; letter-spacing: 0.15em; color: #60a5fa;
    margin: 0.8rem 0;
}

/* Photo grid */
.photo-row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)


# ── Services ──────────────────────────────────────────────────────────────────
@st.cache_resource
def load_services():
    status = {}
    ki = te = tr = mh = hq = sh = None
    try:
        ki = KnowledgeIndexer(); status["AI Search"] = ki._initialized
    except Exception: status["AI Search"] = False
    try:
        tr = Translator(); status["Translator"] = tr._initialized
    except Exception: status["Translator"] = False
    try:
        te = TriageEngine(knowledge_indexer=ki, translator=tr)
        status["GPT-4"] = te._initialized
    except Exception: status["GPT-4"] = False
    try:
        mh = MapsHandler(); status["Azure Maps"] = mh._initialized
    except Exception: status["Azure Maps"] = False
    try:
        hq = HospitalQueue(); status["Queue"] = True
    except Exception: status["Queue"] = False
    try:
        sh = SpeechHandler() if _HAS_SPEECH else None
        status["Speech"] = bool(sh and sh._initialized)
    except Exception: status["Speech"] = False
    return te, tr, mh, hq, sh, status

triage_engine, translator, maps_handler, hospital_queue, speech_handler, _svc_status = load_services()

# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS: dict = dict(
    step="input",
    complaint_text="",
    complaint_english="",
    detected_language="en-US",
    photos=[],              # list of bytes — max 3
    questions=[],
    answers=[],
    q_idx=0,
    demographics={},
    demo_idx=0,
    health_number="",       # health number from activation
    patient_profile=None,   # full patient record from health_db
    data_consent=False,     # consent to share with hospital
    assessment=None,
    patient_record=None,
    eta_info=None,
    nearby_hospitals=[],
    selected_hospital=None,
    patient_lat=None,
    patient_lon=None,
    gps_fetched=False,
    pre_arrival_advice=None,
    reg_number=None,        # registration number shown on arrival
    country="DE",           # detected from GPS or language
)
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

_TC = "_tcache"
if _TC not in st.session_state:
    st.session_state[_TC] = {}

# ── Offline UI strings (no API required) ─────────────────────────────────────
# Format: _UI["key"]["lang_code"] where lang_code = de|tr|fr|ar|en
_UI: dict[str, dict[str, str]] = {
    "Medical emergency assistant":     {"de":"Medizinischer Notfallassistent","tr":"Tıbbi acil asistan","fr":"Assistant médical d'urgence","ar":"مساعد الطوارئ الطبية","en":"Medical emergency assistant"},
    "Location detected":               {"de":"Standort erkannt","tr":"Konum algılandı","fr":"Localisation détectée","ar":"تم اكتشاف الموقع","en":"Location detected"},
    "Allow location access when prompted":{"de":"Standortzugriff erlauben","tr":"İstendiğinde konum erişimine izin verin","fr":"Autorisez l'accès à la localisation","ar":"السماح بالوصول إلى الموقع","en":"Allow location access when prompted"},
    "Record your symptoms":            {"de":"Symptome aufnehmen","tr":"Semptomlarınızı kaydedin","fr":"Enregistrez vos symptômes","ar":"سجّل أعراضك","en":"Record your symptoms"},
    "Speak in your language — tap the microphone":{"de":"In Ihrer Sprache sprechen — Mikrofon tippen","tr":"Kendi dilinizde konuşun — mikrofona dokunun","fr":"Parlez dans votre langue — touchez le micro","ar":"تحدث بلغتك — اضغط على الميكروفون","en":"Speak in your language — tap the microphone"},
    "Understood":                      {"de":"Verstanden","tr":"Anlaşıldı","fr":"Compris","ar":"مفهوم","en":"Understood"},
    "Could not process audio — please type below":{"de":"Audio konnte nicht verarbeitet werden — bitte unten eingeben","tr":"Ses işlenemedi — lütfen aşağıya yazın","fr":"Impossible de traiter l'audio — tapez ci-dessous","ar":"تعذّر معالجة الصوت — اكتب أدناه","en":"Could not process audio — please type below"},
    "Type instead":                    {"de":"Stattdessen tippen","tr":"Bunun yerine yazın","fr":"Taper à la place","ar":"اكتب بدلاً من ذلك","en":"Type instead"},
    "Describe your symptoms":          {"de":"Beschreiben Sie Ihre Symptome","tr":"Semptomlarınızı tanımlayın","fr":"Décrivez vos symptômes","ar":"صف أعراضك","en":"Describe your symptoms"},
    "e.g. Sudden chest pain, difficulty breathing...":{"de":"z.B. Plötzliche Brustschmerzen, Atembeschwerden...","tr":"Örn. Ani göğüs ağrısı, nefes darlığı...","fr":"Ex. Douleur thoracique soudaine, difficulté à respirer...","ar":"مثل: ألم مفاجئ في الصدر، صعوبة في التنفس...","en":"e.g. Sudden chest pain, difficulty breathing..."},
    "Continue →":                      {"de":"Weiter →","tr":"Devam →","fr":"Continuer →","ar":"متابعة →","en":"Continue →"},
    "🔄 Processing...":                {"de":"🔄 Verarbeitung...","tr":"🔄 İşleniyor...","fr":"🔄 Traitement...","ar":"🔄 جارٍ المعالجة...","en":"🔄 Processing..."},
    "Add photos (optional)":           {"de":"Fotos hinzufügen (optional)","tr":"Fotoğraf ekle (isteğe bağlı)","fr":"Ajouter des photos (facultatif)","ar":"إضافة صور (اختياري)","en":"Add photos (optional)"},
    "Take or upload a photo":          {"de":"Foto aufnehmen oder hochladen","tr":"Fotoğraf çekin veya yükleyin","fr":"Prendre ou télécharger une photo","ar":"التقط صورة أو حمّلها","en":"Take or upload a photo"},
    "Skip →":                          {"de":"Überspringen →","tr":"Atla →","fr":"Passer →","ar":"تخطي →","en":"Skip →"},
    "Preparing your assessment...":    {"de":"Bewertung wird vorbereitet...","tr":"Değerlendirmeniz hazırlanıyor...","fr":"Préparation de votre évaluation...","ar":"جارٍ تحضير تقييمك...","en":"Preparing your assessment..."},
    "Almost done":                     {"de":"Fast fertig","tr":"Neredeyse bitti","fr":"Presque terminé","ar":"على وشك الانتهاء","en":"Almost done"},
    "Please review what will be shared with the hospital":{"de":"Bitte überprüfen, was mit dem Krankenhaus geteilt wird","tr":"Hastaneyle paylaşılacakları inceleyin","fr":"Vérifiez ce qui sera partagé avec l'hôpital","ar":"راجع ما سيتم مشاركته مع المستشفى","en":"Please review what will be shared with the hospital"},
    "Data sharing consent":            {"de":"Einwilligung zur Datenweitergabe","tr":"Veri paylaşım onayı","fr":"Consentement au partage de données","ar":"الموافقة على مشاركة البيانات","en":"Data sharing consent"},
    "Do you consent to sharing the following information with the hospital you are directed to?":{"de":"Stimmen Sie zu, die folgenden Informationen mit dem Krankenhaus zu teilen?","tr":"Yönlendirileceğiniz hastaneyle aşağıdaki bilgileri paylaşmayı kabul ediyor musunuz?","fr":"Consentez-vous à partager ces informations avec l'hôpital?","ar":"هل توافق على مشاركة هذه المعلومات مع المستشفى؟","en":"Do you consent to sharing the following information with the hospital you are directed to?"},
    "Health / insurance number":       {"de":"Gesundheits-/Versicherungsnummer","tr":"Sağlık/sigorta numarası","fr":"Numéro de santé/assurance","ar":"رقم الصحة/التأمين","en":"Health / insurance number"},
    "Photos you attached":             {"de":"Beigefügte Fotos","tr":"Eklediğiniz fotoğraflar","fr":"Photos jointes","ar":"الصور المرفقة","en":"Photos you attached"},
    "photo(s)":                        {"de":"Foto(s)","tr":"fotoğraf","fr":"photo(s)","ar":"صورة","en":"photo(s)"},
    "Your symptom description and answers to questions":{"de":"Ihre Symptombeschreibung und Antworten","tr":"Semptom açıklamanız ve sorulara yanıtlarınız","fr":"Description des symptômes et réponses","ar":"وصف أعراضك وإجاباتك","en":"Your symptom description and answers to questions"},
    "Your real-time location (for live tracking)":{"de":"Ihr Echtzeit-Standort (für Live-Tracking)","tr":"Gerçek zamanlı konumunuz (canlı takip için)","fr":"Votre position en temps réel (suivi en direct)","ar":"موقعك الفعلي (للتتبع المباشر)","en":"Your real-time location (for live tracking)"},
    "Yes — share my information with the hospital":{"de":"Ja — meine Daten mit dem Krankenhaus teilen","tr":"Evet — bilgilerimi hastaneyle paylaş","fr":"Oui — partager mes informations","ar":"نعم — مشاركة معلوماتي مع المستشفى","en":"Yes — share my information with the hospital"},
    "No — do not share my data":       {"de":"Nein — meine Daten nicht teilen","tr":"Hayır — verilerimi paylaşma","fr":"Non — ne pas partager mes données","ar":"لا — لا تشارك بياناتي","en":"No — do not share my data"},
    "Consent":                         {"de":"Einwilligung","tr":"Onay","fr":"Consentement","ar":"الموافقة","en":"Consent"},
    "Get my assessment →":             {"de":"Bewertung erhalten →","tr":"Değerlendirmemi al →","fr":"Obtenir mon évaluation →","ar":"احصل على تقييمي →","en":"Get my assessment →"},
    "You must consent to data sharing to proceed.":{"de":"Sie müssen der Datenweitergabe zustimmen.","tr":"Devam etmek için veri paylaşımını onaylamanız gerekir.","fr":"Vous devez consentir au partage de données.","ar":"يجب الموافقة على مشاركة البيانات للمتابعة.","en":"You must consent to data sharing to proceed."},
    "🔍 Analysing your answers...":    {"de":"🔍 Antworten werden analysiert...","tr":"🔍 Yanıtlarınız analiz ediliyor...","fr":"🔍 Analyse de vos réponses...","ar":"🔍 جارٍ تحليل إجاباتك...","en":"🔍 Analysing your answers..."},
    "Go to emergency immediately":     {"de":"Sofort in die Notaufnahme","tr":"Hemen acile gidin","fr":"Allez aux urgences immédiatement","ar":"اذهب إلى الطوارئ فوراً","en":"Go to emergency immediately"},
    "Your symptoms require urgent care — do not wait":{"de":"Ihre Symptome erfordern dringende Behandlung","tr":"Semptomlarınız acil bakım gerektiriyor","fr":"Vos symptômes nécessitent des soins urgents","ar":"أعراضك تستدعي رعاية عاجلة","en":"Your symptoms require urgent care — do not wait"},
    "You need to go to hospital soon": {"de":"Sie müssen bald ins Krankenhaus","tr":"Yakında hastaneye gitmeniz gerekiyor","fr":"Vous devez aller à l'hôpital rapidement","ar":"يجب عليك الذهاب إلى المستشفى قريباً","en":"You need to go to hospital soon"},
    "Please find a hospital within the next 30 minutes":{"de":"Bitte innerhalb von 30 Minuten ein Krankenhaus aufsuchen","tr":"Lütfen 30 dakika içinde bir hastane bulun","fr":"Veuillez trouver un hôpital dans les 30 minutes","ar":"يرجى الذهاب إلى مستشفى خلال 30 دقيقة","en":"Please find a hospital within the next 30 minutes"},
    "You should see a doctor today":   {"de":"Sie sollten heute einen Arzt aufsuchen","tr":"Bugün bir doktora görünmelisiniz","fr":"Vous devriez voir un médecin aujourd'hui","ar":"يجب عليك رؤية طبيب اليوم","en":"You should see a doctor today"},
    "Your symptoms are not immediately life-threatening":{"de":"Ihre Symptome sind nicht unmittelbar lebensbedrohlich","tr":"Semptomlarınız hemen hayatı tehdit etmiyor","fr":"Vos symptômes ne sont pas immédiatement dangereux","ar":"أعراضك ليست مهددة للحياة فوراً","en":"Your symptoms are not immediately life-threatening"},
    "Nearest Emergency Hospitals":     {"de":"Nächste Notaufnahmen","tr":"En yakın acil hastaneler","fr":"Hôpitaux d'urgence les plus proches","ar":"أقرب مستشفيات الطوارئ","en":"Nearest Emergency Hospitals"},
    "Finding nearest hospitals...":    {"de":"Nächste Krankenhäuser werden gesucht...","tr":"En yakın hastaneler aranıyor...","fr":"Recherche des hôpitaux les plus proches...","ar":"جارٍ البحث عن أقرب المستشفيات...","en":"Finding nearest hospitals..."},
    "📍 GPS not available — enter approximate location":{"de":"📍 GPS nicht verfügbar — ungefähren Standort eingeben","tr":"📍 GPS yok — yaklaşık konumu girin","fr":"📍 GPS non disponible — entrez votre emplacement approximatif","ar":"📍 GPS غير متاح — أدخل موقعاً تقريبياً","en":"📍 GPS not available — enter approximate location"},
    "Find Hospitals":                  {"de":"Krankenhäuser finden","tr":"Hastane bul","fr":"Trouver des hôpitaux","ar":"البحث عن مستشفيات","en":"Find Hospitals"},
    "Searching for hospitals...":      {"de":"Krankenhäuser werden gesucht...","tr":"Hastaneler aranıyor...","fr":"Recherche des hôpitaux...","ar":"جارٍ البحث عن المستشفيات...","en":"Searching for hospitals..."},
    "Hospital notified — head there now!":{"de":"Krankenhaus benachrichtigt — sofort dorthin fahren!","tr":"Hastane bildirildi — hemen oraya gidin!","fr":"Hôpital averti — rendez-vous y immédiatement!","ar":"تم إخطار المستشفى — توجه إليه الآن!","en":"Hospital notified — head there now!"},
    "They are preparing for your arrival":{"de":"Sie bereiten sich auf Ihre Ankunft vor","tr":"Gelişinize hazırlanıyorlar","fr":"Ils se préparent à votre arrivée","ar":"إنهم يستعدون لاستقبالك","en":"They are preparing for your arrival"},
    "Hospital notified":               {"de":"Krankenhaus benachrichtigt","tr":"Hastane bildirildi","fr":"Hôpital averti","ar":"تم إخطار المستشفى","en":"Hospital notified"},
    "Please follow the instructions below":{"de":"Bitte den untenstehenden Anweisungen folgen","tr":"Lütfen aşağıdaki talimatları takip edin","fr":"Veuillez suivre les instructions ci-dessous","ar":"يرجى اتباع التعليمات أدناه","en":"Please follow the instructions below"},
    "Your information has been sent":  {"de":"Ihre Daten wurden gesendet","tr":"Bilgileriniz gönderildi","fr":"Vos informations ont été envoyées","ar":"تم إرسال معلوماتك","en":"Your information has been sent"},
    "See instructions below before leaving":{"de":"Bitte Anweisungen lesen vor dem Verlassen","tr":"Ayrılmadan önce talimatları okuyun","fr":"Voir les instructions avant de partir","ar":"راجع التعليمات قبل المغادرة","en":"See instructions below before leaving"},
    "Your hospital registration number":{"de":"Ihre Krankenhaus-Registrierungsnummer","tr":"Hastane kayıt numaranız","fr":"Votre numéro d'enregistrement","ar":"رقم تسجيلك في المستشفى","en":"Your hospital registration number"},
    "Show this number at the hospital reception when you arrive":{"de":"Diese Nummer bei der Anmeldung vorzeigen","tr":"Varışta bu numarayı resepsiyonda gösterin","fr":"Montrez ce numéro à l'accueil à votre arrivée","ar":"أظهر هذا الرقم عند الاستقبال عند وصولك","en":"Show this number at the hospital reception when you arrive"},
    "Before you arrive":               {"de":"Vor Ihrer Ankunft","tr":"Varmadan önce","fr":"Avant votre arrivée","ar":"قبل وصولك","en":"Before you arrive"},
    "DO:":                             {"de":"TUN:","tr":"YAPILACAKLAR:","fr":"À FAIRE:","ar":"افعل:","en":"DO:"},
    "DON'T:":                          {"de":"NICHT TUN:","tr":"YAPILMAYACAKLAR:","fr":"À ÉVITER:","ar":"لا تفعل:","en":"DON'T:"},
    "⏳ Personalised advice being prepared...":{"de":"⏳ Personalisierte Ratschläge werden vorbereitet...","tr":"⏳ Kişiselleştirilmiş tavsiyeler hazırlanıyor...","fr":"⏳ Conseils personnalisés en cours...","ar":"⏳ جارٍ تحضير النصائح الشخصية...","en":"⏳ Personalised advice being prepared..."},
    "Keep your location enabled while travelling":{"de":"Standort aktiviert lassen während der Fahrt","tr":"Yolculuk sırasında konumunuzu açık tutun","fr":"Gardez la localisation activée pendant le trajet","ar":"أبقِ الموقع مفعّلاً أثناء التنقل","en":"Keep your location enabled while travelling"},
    "your care team tracks your arrival in real time":{"de":"Ihr Behandlungsteam verfolgt Ihre Ankunft in Echtzeit","tr":"Bakım ekibiniz gelişinizi gerçek zamanlı takip eder","fr":"votre équipe suit votre arrivée en temps réel","ar":"فريق رعايتك يتابع وصولك في الوقت الفعلي","en":"your care team tracks your arrival in real time"},
    "New assessment":                  {"de":"Neue Bewertung","tr":"Yeni değerlendirme","fr":"Nouvelle évaluation","ar":"تقييم جديد","en":"New assessment"},
    "Question {n} of {total}":         {"de":"Frage {n} von {total}","tr":"{n}. soru / {total}","fr":"Question {n} sur {total}","ar":"السؤال {n} من {total}","en":"Question {n} of {total}"},
    "← Back":                          {"de":"← Zurück","tr":"← Geri","fr":"← Retour","ar":"← رجوع","en":"← Back"},
    "Next →":                          {"de":"Weiter →","tr":"İleri →","fr":"Suivant →","ar":"التالي →","en":"Next →"},
    "Please select an answer.":        {"de":"Bitte eine Antwort auswählen.","tr":"Lütfen bir cevap seçin.","fr":"Veuillez sélectionner une réponse.","ar":"يرجى اختيار إجابة.","en":"Please select an answer."},
    "Just now":                        {"de":"Gerade eben","tr":"Az önce","fr":"À l'instant","ar":"الآن","en":"Just now"},
    "< 1 hour ago":                    {"de":"Vor weniger als 1 Stunde","tr":"1 saatten az önce","fr":"Il y a moins d'1 heure","ar":"منذ أقل من ساعة","en":"< 1 hour ago"},
    "1–6 hours ago":                   {"de":"Vor 1–6 Stunden","tr":"1–6 saat önce","fr":"Il y a 1 à 6 heures","ar":"منذ 1 إلى 6 ساعات","en":"1–6 hours ago"},
    "6–24 hours ago":                  {"de":"Vor 6–24 Stunden","tr":"6–24 saat önce","fr":"Il y a 6 à 24 heures","ar":"منذ 6 إلى 24 ساعة","en":"6–24 hours ago"},
    "More than 1 day":                 {"de":"Mehr als 1 Tag","tr":"1 günden fazla","fr":"Plus d'1 jour","ar":"أكثر من يوم","en":"More than 1 day"},
    "Head/neck":                       {"de":"Kopf/Hals","tr":"Baş/boyun","fr":"Tête/cou","ar":"الرأس/الرقبة","en":"Head/neck"},
    "Chest":                           {"de":"Brust","tr":"Göğüs","fr":"Poitrine","ar":"الصدر","en":"Chest"},
    "Abdomen":                         {"de":"Bauch","tr":"Karın","fr":"Abdomen","ar":"البطن","en":"Abdomen"},
    "Back":                            {"de":"Rücken","tr":"Sırt","fr":"Dos","ar":"الظهر","en":"Back"},
    "Arms":                            {"de":"Arme","tr":"Kollar","fr":"Bras","ar":"الذراعان","en":"Arms"},
    "Legs":                            {"de":"Beine","tr":"Bacaklar","fr":"Jambes","ar":"الساقان","en":"Legs"},
    "Whole body":                      {"de":"Ganzer Körper","tr":"Tüm vücut","fr":"Corps entier","ar":"الجسم كله","en":"Whole body"},
    "Yes":                             {"de":"Ja","tr":"Evet","fr":"Oui","ar":"نعم","en":"Yes"},
    "No":                              {"de":"Nein","tr":"Hayır","fr":"Non","ar":"لا","en":"No"},
    "Not sure":                        {"de":"Nicht sicher","tr":"Emin değilim","fr":"Pas sûr","ar":"غير متأكد","en":"Not sure"},
    "or select a hospital below":      {"de":"oder unten ein Krankenhaus wählen","tr":"veya aşağıdan bir hastane seçin","fr":"ou sélectionnez un hôpital ci-dessous","ar":"أو اختر مستشفى أدناه","en":"or select a hospital below"},
    "Active Patient":                  {"de":"Aktiver Patient","tr":"Aktif Hasta","fr":"Patient actif","ar":"المريض النشط","en":"Active Patient"},
    "Switch demo profile":             {"de":"Demo-Profil wechseln","tr":"Demo profili değiştir","fr":"Changer de profil démo","ar":"تغيير الملف التجريبي","en":"Switch demo profile"},
    "Load →":                          {"de":"Laden →","tr":"Yükle →","fr":"Charger →","ar":"تحميل →","en":"Load →"},
    "Symptoms":                        {"de":"Symptome","tr":"Semptomlar","fr":"Symptômes","ar":"الأعراض","en":"Symptoms"},
    "Photos":                          {"de":"Fotos","tr":"Fotoğraflar","fr":"Photos","ar":"الصور","en":"Photos"},
    "Questions":                       {"de":"Fragen","tr":"Sorular","fr":"Questions","ar":"الأسئلة","en":"Questions"},
    "Hospital":                        {"de":"Krankenhaus","tr":"Hastane","fr":"Hôpital","ar":"المستشفى","en":"Hospital"},
    "Done":                            {"de":"Fertig","tr":"Tamamlandı","fr":"Terminé","ar":"تم","en":"Done"},
    "Demo only. Call 112 for real emergencies.":{"de":"Nur Demo. Im Notfall 112 anrufen.","tr":"Yalnızca demo. Gerçek acillerde 112'yi arayın.","fr":"Démo uniquement. Appelez le 15 en urgence.","ar":"للعرض فقط. اتصل بـ 112 في حالات الطوارئ.","en":"Demo only. Call 112 for real emergencies."},
}

_LANG_CODE_MAP = {
    "de-DE":"de","de":"de",
    "tr-TR":"tr","tr":"tr",
    "fr-FR":"fr","fr":"fr",
    "ar-SA":"ar","ar-EG":"ar","ar":"ar",
    "en-US":"en","en-GB":"en","en":"en",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_hospitals(mh, lat: float, lon: float, country: str = "DE") -> list[dict]:
    """Backward-compatible wrapper — passes 'country' only if the installed
    maps_handler supports it (older installs may not have the parameter yet)."""
    import inspect
    sig = inspect.signature(mh.find_nearest_hospitals)
    if "country" in sig.parameters:
        return mh.find_nearest_hospitals(lat, lon, count=3, country=country)
    return mh.find_nearest_hospitals(lat, lon, count=3)


def _lang_code() -> str:
    """Return 2-letter language code from session detected_language."""
    full = st.session_state.get("detected_language", "en-US")
    return _LANG_CODE_MAP.get(full, _LANG_CODE_MAP.get(full[:2], "en"))


def t(text: str) -> str:
    """Translate a UI string. Uses offline _UI dict first; falls back to Azure Translator."""
    lc = _lang_code()
    if lc == "en":
        return text
    # Offline dictionary lookup
    if text in _UI and lc in _UI[text]:
        return _UI[text][lc]
    # Azure Translator fallback (only if available)
    if translator:
        lang = st.session_state.get("detected_language", "en-US")
        cache = st.session_state[_TC]
        key = f"{lang}:{text[:80]}"
        if key in cache:
            return cache[key]
        try:
            out = translator.translate_from_english(text, lang)
            cache[key] = out
            return out
        except Exception:
            pass
    return text


def reset():
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v
    st.session_state[_TC] = {}


def _inject_rtl():
    if st.session_state.detected_language in RTL_LOCALES:
        st.markdown('<style>.block-container { direction: rtl; text-align: right; }</style>', unsafe_allow_html=True)


def _emergency_number() -> dict:
    lang = st.session_state.detected_language.split("-")[0]
    ctry = st.session_state.get("country", "DE")
    if ctry == "UK":
        return {"number": "999", "label": "Emergency"}
    return EMERGENCY_NUMBERS.get(lang, EMERGENCY_NUMBERS["default"])


def _gen_reg_number() -> str:
    return "CZ-" + datetime.now(timezone.utc).strftime("%H%M") + "-" + str(random.randint(1000, 9999))


def _try_transcribe(audio) -> str | None:
    if not speech_handler or not getattr(speech_handler, "_initialized", False):
        return None
    raw = audio.getvalue()
    if not raw:
        return None
    try:
        is_wav  = raw[:4] == b"RIFF"
        is_ogg  = raw[:4] == b"OggS"
        if is_wav:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(raw); wav_path = tmp.name
        else:
            src = ".ogg" if is_ogg else ".webm"
            wav_path = speech_handler.convert_browser_audio_to_wav(raw, source_suffix=src)
            if not wav_path:
                return None
        result = speech_handler.recognize_from_audio_file(wav_path)
        try:
            os.unlink(wav_path)
        except OSError:
            pass
        if result and result.get("text"):
            st.session_state.detected_language = result.get("language", "en-US")
            return result["text"]
    except Exception as exc:
        logger.error("Transcription error: %s", exc)
    return None


def _detect_country_from_gps(lat: float, lon: float) -> str:
    """Rough country detection from lat/lon bounding boxes."""
    if 47.2 <= lat <= 55.1 and 5.9 <= lon <= 15.1:
        return "DE"
    if 49.9 <= lat <= 60.9 and -8.6 <= lon <= 1.8:
        return "UK"
    if 35.8 <= lat <= 42.1 and 26.0 <= lon <= 44.8:
        return "TR"
    return "DE"


def _do_process(text: str) -> None:
    detected_code: str | None = None
    if translator:
        try:
            detected_code = translator.detect_language(text)
        except Exception:
            pass
    locale_map = {
        "de": "de-DE", "tr": "tr-TR", "ar": "ar-SA", "fr": "fr-FR",
        "es": "es-ES", "it": "it-IT", "ru": "ru-RU", "en": "en-US",
        "nl": "nl-NL", "pl": "pl-PL",
    }
    new_lang = locale_map.get(detected_code or "en", "en-US")
    lang_changed = (new_lang != st.session_state.detected_language)
    st.session_state.detected_language = new_lang
    st.session_state[_TC] = {}

    # If language changed significantly, re-assign profile to match
    if lang_changed:
        lc = _LANG_CODE_MAP.get(new_lang, "en")
        lang_to_prefix = {"de": "DEMO-DE", "tr": "DEMO-TR", "en": "DEMO-UK", "fr": "DEMO-DE", "ar": "DEMO-DE"}
        prefix = lang_to_prefix.get(lc, "DEMO-DE")
        all_nums = list_demo_health_numbers()
        matching = [n for n in all_nums if n.startswith(prefix)]
        if matching:
            import random as _rnd
            _load_profile(_rnd.choice(matching))
            st.session_state.detected_language = new_lang  # restore after _load_profile

    english = text
    if translator:
        try:
            english = translator.translate_to_english(text, st.session_state.detected_language)
        except Exception:
            pass

    st.session_state.complaint_text    = text
    st.session_state.complaint_english = english
    st.session_state.demographics      = {}
    st.session_state.demo_idx          = 0
    st.session_state.q_idx             = 0
    st.session_state.answers           = []
    st.session_state.questions         = []
    st.session_state.step              = "photos"
    st.rerun()


def _do_notify(lat, lon, eta, hospital_name):
    location = {"lat": lat, "lon": lon} if lat and lon else None
    eta_min  = eta.get("eta_minutes") if eta else None

    # Build photos metadata list
    photos_meta = []
    for i, photo_bytes in enumerate(st.session_state.photos):
        photos_meta.append({"index": i + 1, "size_bytes": len(photo_bytes)})

    if triage_engine:
        record = triage_engine.create_patient_record(
            chief_complaint=st.session_state.complaint_english,
            assessment=st.session_state.assessment,
            language=st.session_state.detected_language,
            eta_minutes=eta_min,
            location=location,
            demographics=st.session_state.get("demographics"),
        )
    else:
        record = {
            "patient_id": "DEMO-" + str(random.randint(1000, 9999)),
            "triage_level": TRIAGE_URGENT,
            "chief_complaint": st.session_state.complaint_text,
            "language": st.session_state.detected_language,
        }

    if hospital_name:
        record["destination_hospital"] = hospital_name

    # Enrich record
    record["qa_transcript"]   = st.session_state.answers
    record["complaint_text"]  = st.session_state.complaint_text   # original language
    record["has_photo"]       = len(st.session_state.photos) > 0
    record["photo_count"]     = len(st.session_state.photos)
    record["photos_meta"]     = photos_meta
    record["photo_note"]      = f"Patient attached {len(st.session_state.photos)} photo(s)" if st.session_state.photos else ""
    record["health_number"]   = st.session_state.get("health_number", "")
    record["data_consent"]    = st.session_state.get("data_consent", False)
    record["age_range"]       = st.session_state.demographics.get("age_range", "—")
    record["sex"]             = st.session_state.demographics.get("sex", "—")

    if hospital_queue:
        hospital_queue.add_patient(record)

    reg = _gen_reg_number()
    st.session_state.patient_record = record
    st.session_state.reg_number     = reg

    # Pre-arrival advice
    if triage_engine:
        try:
            advice = triage_engine.generate_pre_arrival_advice(
                chief_complaint=st.session_state.complaint_english,
                assessment=st.session_state.assessment,
                language=st.session_state.detected_language,
            )
            st.session_state.pre_arrival_advice = advice
        except Exception as exc:
            logger.error("Pre-arrival advice: %s", exc)
            st.session_state.pre_arrival_advice = None


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-PROFILE: random demo patient loaded on first run
# In production this is pre-configured at install time.
# In demo: switch profiles from the sidebar at any time.
# ══════════════════════════════════════════════════════════════════════════════
def _load_profile(hn: str) -> None:
    """Load a patient profile from DB and configure session state."""
    patient = get_patient(hn)
    if not patient:
        return
    age = get_age(patient["date_of_birth"])
    if age < 12:   age_range = "Under 12"
    elif age < 18: age_range = "12-17"
    elif age < 30: age_range = "18-29"
    elif age < 45: age_range = "30-44"
    elif age < 60: age_range = "45-59"
    elif age < 75: age_range = "60-74"
    else:          age_range = "75+"
    st.session_state.health_number    = hn
    st.session_state.patient_profile  = patient
    st.session_state.demographics     = {"age_range": age_range, "sex": patient["sex"]}
    st.session_state.detected_language = patient.get("language", "en-US")
    st.session_state[_TC]             = {}
    nat = patient.get("nationality", "DE")
    st.session_state.country = nat if nat in ("DE", "TR", "UK") else "DE"


def _ensure_profile() -> None:
    """If no profile loaded yet, assign a random demo patient that matches detected language.
    Language is detected from the browser/system; in demo it defaults to DE profile."""
    if not st.session_state.health_number:
        all_nums = list_demo_health_numbers()
        if not all_nums:
            return
        lang = st.session_state.get("detected_language", "en-US")
        lc = _LANG_CODE_MAP.get(lang, _LANG_CODE_MAP.get(lang[:2], "en"))
        # Map language to country prefix
        lang_to_prefix = {"de": "DEMO-DE", "tr": "DEMO-TR", "en": "DEMO-UK", "fr": "DEMO-DE", "ar": "DEMO-DE"}
        prefix = lang_to_prefix.get(lc, "DEMO-DE")
        matching = [n for n in all_nums if n.startswith(prefix)]
        pool = matching if matching else all_nums
        import random as _rnd
        _load_profile(_rnd.choice(pool))


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — INPUT
# Ultra-minimal: voice first, tiny "type instead" option
# ══════════════════════════════════════════════════════════════════════════════
def page_input() -> None:
    _inject_rtl()

    # GPS detection
    if not st.session_state.gps_fetched:
        try:
            p = st.query_params
            if "cz_lat" in p and "cz_lon" in p:
                lat = float(p["cz_lat"]); lon = float(p["cz_lon"])
                st.session_state.patient_lat = lat
                st.session_state.patient_lon = lon
                st.session_state.gps_fetched = True
                st.session_state.country = _detect_country_from_gps(lat, lon)
        except Exception:
            pass

    if not st.session_state.gps_fetched:
        st.components.v1.html("""
<script>
(function(){
  if(!navigator.geolocation)return;
  navigator.geolocation.getCurrentPosition(function(p){
    try{
      var u=new URL(window.parent.location.href);
      u.searchParams.set("cz_lat",p.coords.latitude.toFixed(6));
      u.searchParams.set("cz_lon",p.coords.longitude.toFixed(6));
      window.parent.location.replace(u.toString());
    }catch(e){}
  },function(){},{timeout:8000,enableHighAccuracy:false});
})();
</script>""", height=0)

    # ── Header ──
    st.markdown(f"""
<div style="text-align:center; padding:2rem 0 1rem 0;">
  <div style="font-size:4rem; line-height:1.1;">🚑</div>
  <h1 style="font-size:2.2rem; font-weight:900; margin:0.2rem 0 0.3rem 0; color:#f8fafc;">CodeZero</h1>
  <p style="font-size:1.05rem; color:#64748b; margin:0;">{t("Medical emergency assistant")}</p>
</div>
""", unsafe_allow_html=True)

    # GPS status
    if st.session_state.patient_lat:
        st.markdown(f'<p style="text-align:center;font-size:0.88rem;color:#22c55e;margin:0 0 0.8rem 0;">📍 {t("Location detected")}</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p style="text-align:center;font-size:0.88rem;color:#475569;margin:0 0 0.8rem 0;">📍 {t("Allow location access when prompted")}</p>', unsafe_allow_html=True)

    # ── Primary: voice ──
    st.markdown(f"""
<div style="text-align:center; margin:0.5rem 0 0.2rem 0;">
  <p style="font-size:1.25rem; font-weight:700; color:#f1f5f9; margin:0 0 0.2rem 0;">🎤 {t('Record your symptoms')}</p>
  <p style="font-size:0.95rem; color:#64748b; margin:0;">{t('Speak in your language — tap the microphone')}</p>
</div>
""", unsafe_allow_html=True)

    if hasattr(st, "audio_input"):
        audio = st.audio_input(" ", label_visibility="collapsed", key="audio_main")
        if audio is not None:
            with st.spinner(t("🔄 Processing...")):
                transcribed = _try_transcribe(audio)
            if transcribed:
                st.markdown(f"""
<div style="background:#052e16; border:2px solid #22c55e; border-radius:12px; padding:1rem 1.1rem; margin:0.6rem 0;">
  <p style="color:#86efac; font-size:0.8rem; margin:0 0 0.3rem 0; text-transform:uppercase; letter-spacing:0.05em;">{t('Understood')}</p>
  <p style="color:#f0fdf4; font-size:1.05rem; margin:0; font-style:italic;">"{transcribed}"</p>
</div>
""", unsafe_allow_html=True)
                if st.button(t("Continue →"), type="primary", use_container_width=True, key="btn_voice"):
                    _do_process(transcribed)
            else:
                st.markdown(f'<p style="color:#f87171;text-align:center;font-size:0.95rem;margin:0.4rem 0;">{t("Could not process audio — please type below")}</p>', unsafe_allow_html=True)
    else:
        st.info("Upgrade Streamlit for voice input: `pip install -U streamlit`")

    # ── "Or type" — minimal, secondary ──
    with st.expander(f"✏️ {t('Type instead')}", expanded=False):
        complaint = st.text_area(
            t("Describe your symptoms"),
            placeholder=t("e.g. Sudden chest pain, difficulty breathing..."),
            height=90,
            label_visibility="collapsed",
        )
        st.caption(f"🌍 {t('Any language is understood')}")
        if st.button(t("Continue →"), type="primary", use_container_width=True, key="btn_text"):
            if complaint and complaint.strip():
                _do_process(complaint.strip())
            else:
                st.warning(t("Please describe your symptoms first."))


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — PHOTOS (optional, max 3)
# ══════════════════════════════════════════════════════════════════════════════
def page_photos() -> None:
    _inject_rtl()

    st.markdown("""
<div style="text-align:center; padding:1rem 0 0.5rem 0;">
  <p style="font-size:1.3rem; font-weight:700; color:#f1f5f9; margin:0;">📷 Add photos</p>
  <p style="font-size:0.95rem; color:#64748b; margin:0.2rem 0 0;">Wound, rash, swelling — up to 3 photos</p>
</div>
""", unsafe_allow_html=True)

    photos = st.session_state.photos
    max_photos = 3

    # Show existing photos with delete option
    if photos:
        cols = st.columns(min(len(photos), 3))
        for i, photo_bytes in enumerate(photos):
            with cols[i % 3]:
                st.image(photo_bytes, use_container_width=True, caption=f"Photo {i+1}")
                if st.button("🗑 Remove", key=f"del_photo_{i}", use_container_width=True):
                    st.session_state.photos.pop(i)
                    st.rerun()

    # Add more photos
    if len(photos) < max_photos:
        st.markdown(f'<p style="color:#64748b;font-size:0.9rem;margin:0.3rem 0;">({len(photos)}/{max_photos} photos)</p>', unsafe_allow_html=True)

        # Camera input
        try:
            if hasattr(st, "camera_input"):
                new_photo = st.camera_input("Take a photo", label_visibility="collapsed", key=f"cam_{len(photos)}")
                if new_photo is not None:
                    st.session_state.photos.append(new_photo.getvalue())
                    st.rerun()
        except Exception:
            pass

        # File upload fallback
        uploaded = st.file_uploader(
            "Or upload a photo",
            type=["jpg", "jpeg", "png", "heic"],
            label_visibility="collapsed",
            key=f"up_{len(photos)}",
        )
        if uploaded is not None:
            st.session_state.photos.append(uploaded.getvalue())
            st.rerun()

    # Navigation — skip demographics, go to AI questions
    def _go_to_questions():
        with st.spinner(t("Preparing your assessment...")):
            if triage_engine:
                st.session_state.questions = triage_engine.generate_questions(
                    st.session_state.complaint_english,
                    demographics=st.session_state.demographics,
                )
            else:
                st.session_state.questions = []
        st.session_state.q_idx = 0
        st.session_state.step = "questions"
        st.rerun()

    col_skip, col_cont = st.columns(2)
    with col_skip:
        if st.button(t("Skip →"), use_container_width=True, key="skip_photos"):
            _go_to_questions()
    with col_cont:
        label = t("Continue →") if photos else t("Skip →")
        if st.button(label, type="primary", use_container_width=True, key="cont_photos"):
            _go_to_questions()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — DEMOGRAPHICS (REMOVED — auto-filled from health record)
# Kept as redirect for backward compatibility.
# ══════════════════════════════════════════════════════════════════════════════
def page_demographics() -> None:
    """Demographics are now auto-filled from the health record.
    This function only exists as a redirect in case something routes here."""
    with st.spinner(t("Preparing your assessment...")):
        if triage_engine:
            st.session_state.questions = triage_engine.generate_questions(
                st.session_state.complaint_english,
                demographics=st.session_state.demographics,
            )
        else:
            st.session_state.questions = []
    st.session_state.q_idx = 0
    st.session_state.step = "questions"
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — QUESTIONS + health number + consent
# ══════════════════════════════════════════════════════════════════════════════
def page_questions() -> None:
    _inject_rtl()

    questions = st.session_state.questions
    idx       = st.session_state.q_idx
    lang      = st.session_state.detected_language

    # After all AI questions: health number + consent screen
    if idx >= len(questions):
        _page_consent()
        return

    total = len(questions) + 1  # +1 for consent screen
    st.progress(idx / total)
    _q_label = t("Question {n} of {total}").replace("{n}", str(idx+1)).replace("{total}", str(len(questions)))
    st.markdown(f'<p style="color:#64748b;font-size:0.8rem;text-align:right;margin:0 0 0.5rem 0;">{_q_label}</p>', unsafe_allow_html=True)

    question = questions[idx]
    q_text: str  = question.get("question", "")
    q_type: str  = question.get("type", "yes_no")
    options: list = question.get("options", [])

    # Normalise free-text / empty options
    if q_type == "free_text" or not options:
        q_lower = q_text.lower()
        if any(w in q_lower for w in ["when","how long","since","start","began","zaman","başla"]):
            q_type = "multiple_choice"
            options = ["Just now","< 1 hour ago","1–6 hours ago","6–24 hours ago","More than 1 day"]
        elif any(w in q_lower for w in ["how","rate","scale","severity","şiddet","puan","pain"]):
            q_type = "scale"
            options = [str(i) for i in range(1, 11)]
        elif any(w in q_lower for w in ["where","location","nerede","yer"]):
            q_type = "multiple_choice"
            options = ["Head/neck","Chest","Abdomen","Back","Arms","Legs","Whole body"]
        else:
            q_type = "yes_no"
            options = ["Yes","No","Not sure"]

    st.markdown(f'<p style="font-size:1.15rem;font-weight:600;color:#f1f5f9;margin:0 0 0.5rem 0;">{t(q_text)}</p>', unsafe_allow_html=True)

    answer = None
    if q_type == "scale":
        answer = st.select_slider("", options=options, key=f"q_{idx}")
    elif q_type == "multiple_choice":
        sel = st.multiselect("", [t(o) for o in options], key=f"q_{idx}", label_visibility="collapsed")
        answer = ", ".join(sel) if sel else None
    else:
        answer = st.radio("", [t(o) for o in options], key=f"q_{idx}", label_visibility="collapsed")

    c1, c2 = st.columns(2)
    with c1:
        if idx > 0 and st.button(t("← Back"), use_container_width=True, key="q_back"):
            st.session_state.q_idx -= 1
            if st.session_state.answers: st.session_state.answers.pop()
            st.rerun()
    with c2:
        if st.button(t("Next →"), type="primary", use_container_width=True, key="q_next"):
            if answer:
                eng = str(answer)
                if translator:
                    try: eng = translator.translate_to_english(str(answer), lang)
                    except Exception: pass
                st.session_state.answers.append({"question": q_text, "answer": eng, "original_answer": str(answer)})
                st.session_state.q_idx += 1
                st.rerun()
            else:
                st.warning(t("Please select an answer."))


def _page_consent() -> None:
    """Data sharing consent — lists specific items shared with hospital.
    Forces geolocation on approval."""
    _inject_rtl()

    hn = st.session_state.health_number or "—"
    photo_count = len(st.session_state.photos)

    st.markdown(f"""
<div style="text-align:center;padding:0.5rem 0 0.8rem;">
  <p style="font-size:1.2rem;font-weight:700;color:#f1f5f9;margin:0;">{t('Almost done')}</p>
  <p style="font-size:0.9rem;color:#64748b;margin:0.1rem 0;">{t('Please review what will be shared with the hospital')}</p>
</div>""", unsafe_allow_html=True)

    # Show specific consent items
    st.markdown(f'<p style="font-size:1rem;font-weight:600;color:#cbd5e1;margin:0 0 0.5rem 0;">📋 {t("Data sharing consent")}</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:0.92rem;color:#94a3b8;margin:0 0 0.8rem 0;">{t("Do you consent to sharing the following information with the hospital you are directed to?")}</p>', unsafe_allow_html=True)

    st.markdown(f"""
<div style="background:#0f172a;border:1px solid #1e293b;border-radius:14px;padding:1rem 1.2rem;margin:0 0 1rem 0;">
  <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">
    <span style="font-size:1.2rem;">🪪</span>
    <span style="color:#e2e8f0;font-size:0.95rem;">{t('Health / insurance number')}: <strong style="color:#60a5fa;">{hn}</strong></span>
  </div>
  <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">
    <span style="font-size:1.2rem;">📷</span>
    <span style="color:#e2e8f0;font-size:0.95rem;">{t('Photos you attached')}: <strong style="color:#60a5fa;">{photo_count} {t('photo(s)')}</strong></span>
  </div>
  <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">
    <span style="font-size:1.2rem;">💬</span>
    <span style="color:#e2e8f0;font-size:0.95rem;">{t('Your symptom description and answers to questions')}</span>
  </div>
  <div style="display:flex;align-items:center;gap:0.6rem;">
    <span style="font-size:1.2rem;">📍</span>
    <span style="color:#e2e8f0;font-size:0.95rem;">{t('Your real-time location (for live tracking)')}</span>
  </div>
</div>
""", unsafe_allow_html=True)

    consent = st.radio(
        t("Consent"),
        [f"✅ {t('Yes — share my information with the hospital')}", f"❌ {t('No — do not share my data')}"],
        label_visibility="collapsed",
        key="consent_radio",
    )
    st.session_state.data_consent = "Yes" in consent or "Evet" in consent or "Ja" in consent

    if st.button(t("Get my assessment →"), type="primary", use_container_width=True, key="btn_consent"):
        if not st.session_state.data_consent:
            st.warning(t("You must consent to data sharing to proceed."))
            return

        # Force geolocation via JavaScript
        if not st.session_state.gps_fetched:
            st.components.v1.html("""
<script>
(function(){
  if(!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(function(p){
    try{
      var u=new URL(window.parent.location.href);
      u.searchParams.set("cz_lat",p.coords.latitude.toFixed(6));
      u.searchParams.set("cz_lon",p.coords.longitude.toFixed(6));
      window.parent.location.replace(u.toString());
    }catch(e){}
  },function(err){
    // Retry with lower accuracy if denied
    alert("Location access is required. Please enable location and try again.");
  },{timeout:10000,enableHighAccuracy:true});
})();
</script>""", height=0)

        # Run triage assessment
        with st.spinner(t("🔍 Analysing your answers...")):
            if triage_engine:
                assessment = triage_engine.assess_triage(
                    st.session_state.complaint_english,
                    st.session_state.answers,
                )
            else:
                assessment = {
                    "triage_level": TRIAGE_URGENT,
                    "assessment": "AI not configured — demo mode.",
                    "red_flags": [], "risk_score": 5,
                    "recommended_action": "Please see a doctor.",
                    "time_sensitivity": "Soon",
                    "source_guidelines": [], "suspected_conditions": [],
                }
        st.session_state.assessment = assessment
        st.session_state.step = "triage"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — TRIAGE (emergency number + hospital selection)
# ══════════════════════════════════════════════════════════════════════════════
def page_triage() -> None:
    _inject_rtl()

    assessment = st.session_state.assessment
    level      = assessment.get("triage_level", TRIAGE_URGENT)
    emg        = _emergency_number()

    # ── Emergency banner ──────────────────────────────────────────────────
    if level == TRIAGE_EMERGENCY:
        st.markdown(f"""
<div style="background:#7f1d1d;border-left:5px solid #dc2626;border-radius:14px;padding:1.1rem 1.3rem;margin:0.2rem 0 1rem 0;">
  <p style="font-size:1.4rem;font-weight:800;color:#fef2f2;margin:0 0 0.2rem 0;">🚨 {t("Go to emergency immediately")}</p>
  <p style="font-size:1rem;color:#fecaca;margin:0;">{t("Your symptoms require urgent care — do not wait")}</p>
</div>
""", unsafe_allow_html=True)
        _call_num = emg["number"]
        _call_lbl = emg["label"]
        _or_below = t("or select a hospital below")
        st.markdown(f"""
<div style="text-align:center;margin:0.5rem 0 1rem 0;">
  <a href="tel:{_call_num}" style="background:#dc2626;color:white;padding:20px 48px;
     border-radius:14px;font-size:1.6rem;font-weight:800;text-decoration:none;
     display:inline-block;box-shadow:0 4px 16px rgba(220,38,38,0.4);">
    📞 CALL {_call_num}
  </a>
  <p style="color:#64748b;font-size:0.85rem;margin:0.5rem 0 0 0;">{_call_lbl} · Tap to call</p>
</div>
<div style="text-align:center;margin:0 0 0.8rem 0;">
  <p style="color:#94a3b8;font-size:0.9rem;">— {_or_below} —</p>
</div>
""", unsafe_allow_html=True)

    elif level == TRIAGE_URGENT:
        st.markdown(f"""
<div style="background:#78350f;border-left:5px solid #f59e0b;border-radius:14px;padding:1.1rem 1.3rem;margin:0.2rem 0 1rem 0;">
  <p style="font-size:1.25rem;font-weight:800;color:#fefce8;margin:0 0 0.2rem 0;">⚠️ {t("You need to go to hospital soon")}</p>
  <p style="font-size:0.95rem;color:#fde68a;margin:0;">{t("Please find a hospital within the next 30 minutes")}</p>
</div>
""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
<div style="background:#14532d;border-left:5px solid #22c55e;border-radius:14px;padding:1.1rem 1.3rem;margin:0.2rem 0 1rem 0;">
  <p style="font-size:1.2rem;font-weight:700;color:#f0fdf4;margin:0 0 0.2rem 0;">ℹ️ {t("You should see a doctor today")}</p>
  <p style="font-size:0.9rem;color:#bbf7d0;margin:0;">{t("Your symptoms are not immediately life-threatening")}</p>
</div>
""", unsafe_allow_html=True)

    # ── Hospital search ────────────────────────────────────────────────────
    st.markdown(f'<p style="font-size:1.1rem;font-weight:700;color:#f1f5f9;margin:0.5rem 0 0.3rem 0;">🏥 {t("Nearest Emergency Hospitals")}</p>', unsafe_allow_html=True)

    lat = st.session_state.patient_lat
    lon = st.session_state.patient_lon
    country = st.session_state.get("country", "DE")

    # Auto-search on first render
    if not st.session_state.nearby_hospitals:
        if lat and lon and maps_handler:
            with st.spinner("Finding nearest hospitals..."):
                hospitals = _find_hospitals(maps_handler, lat, lon, country)
                st.session_state.nearby_hospitals = hospitals
            st.rerun()
        elif not lat:
            # Manual coordinate entry
            st.caption("📍 GPS not available — enter approximate location")
            c1, c2 = st.columns(2)
            with c1:
                lat = st.number_input("Latitude", value=48.78, format="%.4f", key="manual_lat")
            with c2:
                lon = st.number_input("Longitude", value=9.18, format="%.4f", key="manual_lon")
            if st.button("Find Hospitals", type="primary", use_container_width=True, key="find_manual"):
                if maps_handler:
                    hospitals = _find_hospitals(maps_handler, lat, lon, country)
                    st.session_state.nearby_hospitals = hospitals
                    st.session_state.patient_lat = lat
                    st.session_state.patient_lon = lon
                    st.rerun()

    hospitals = st.session_state.nearby_hospitals

    if hospitals:
        for i, h in enumerate(hospitals):
            occupancy = _sim_occupancy(h["name"])
            occ_color = {"🟢": "#22c55e","🟡": "#eab308","🟠": "#f97316","🔴": "#ef4444"}.get(occupancy[:2], "#94a3b8")
            is_fastest = i == 0
            card_class = "fastest" if is_fastest else "second"
            rank_badge = "⭐ FASTEST" if is_fastest else f"#{i+1}"

            st.markdown(f"""
<div class="hosp-card {card_class}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.4rem;">
    <span style="font-size:1rem;font-weight:700;color:#f8fafc;">{rank_badge} {h['name']}</span>
  </div>
  <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0.4rem;">
    <span style="color:#94a3b8;font-size:0.95rem;">📏 {h['distance_km']} km</span>
    <span style="color:#94a3b8;font-size:0.95rem;">⏱ ~{h['eta_minutes']} min</span>
    <span style="color:{occ_color};font-size:0.9rem;font-weight:600;">{occupancy}</span>
  </div>
  <p style="color:#64748b;font-size:0.88rem;margin:0;">📍 {h.get('address','')}</p>
</div>
""", unsafe_allow_html=True)

            if st.button(f"Go to {h['name']}", key=f"sel_{i}", use_container_width=True,
                         type="primary" if is_fastest else "secondary"):
                eta_info = {
                    "hospital_name": h["name"],
                    "hospital_lat":  h["lat"],
                    "hospital_lon":  h["lon"],
                    "eta_minutes":   h["eta_minutes"],
                    "distance_km":   h["distance_km"],
                    "address":       h.get("address", ""),
                    "route_summary": h.get("route_summary", ""),
                    "occupancy":     occupancy,
                }
                st.session_state.selected_hospital = h
                st.session_state.eta_info = eta_info
                _do_notify(st.session_state.patient_lat, st.session_state.patient_lon, eta_info, h["name"])
                st.session_state.step = "result"
                st.rerun()
    else:
        if lat:
            st.info("Searching for hospitals...")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — RESULT (instructions, reg number, tracking note)
# ══════════════════════════════════════════════════════════════════════════════
def page_result() -> None:
    _inject_rtl()

    assessment = st.session_state.assessment or {}
    eta        = st.session_state.eta_info or {}
    record     = st.session_state.patient_record or {}
    level      = assessment.get("triage_level", TRIAGE_URGENT)
    reg_no     = st.session_state.reg_number or _gen_reg_number()
    emg        = _emergency_number()

    # ── Confirmation banner ───────────────────────────────────────────────
    if level == TRIAGE_EMERGENCY:
        st.markdown(f"""
<div style="background:#7f1d1d;border-left:5px solid #dc2626;border-radius:14px;padding:1.1rem 1.3rem;margin:0.3rem 0 0.8rem 0;">
  <p style="font-size:1.3rem;font-weight:800;color:#fef2f2;margin:0 0 0.2rem 0;">🚨 {t("Hospital notified — head there now!")}</p>
  <p style="font-size:0.95rem;color:#fecaca;margin:0;">{t("They are preparing for your arrival")}</p>
</div>""", unsafe_allow_html=True)
    elif level == TRIAGE_URGENT:
        st.markdown(f"""
<div style="background:#78350f;border-left:5px solid #f59e0b;border-radius:14px;padding:1.1rem 1.3rem;margin:0.3rem 0 0.8rem 0;">
  <p style="font-size:1.2rem;font-weight:800;color:#fefce8;margin:0 0 0.2rem 0;">✅ {t("Hospital notified")}</p>
  <p style="font-size:0.9rem;color:#fde68a;margin:0;">{t("Please follow the instructions below")}</p>
</div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
<div style="background:#0c4a6e;border-left:5px solid #0ea5e9;border-radius:14px;padding:1.1rem 1.3rem;margin:0.3rem 0 0.8rem 0;">
  <p style="font-size:1.2rem;font-weight:700;color:#f0f9ff;margin:0 0 0.2rem 0;">✅ {t("Your information has been sent")}</p>
  <p style="font-size:0.9rem;color:#bae6fd;margin:0;">{t("See instructions below before leaving")}</p>
</div>""", unsafe_allow_html=True)

    # ── Hospital + ETA ───────────────────────────────────────────────────
    if eta:
        occ = eta.get("occupancy", "")
        st.markdown(f"""
<div style="background:#1e293b;border-radius:12px;padding:0.9rem 1rem;margin:0.3rem 0 0.8rem 0;">
  <p style="font-size:1.05rem;font-weight:700;color:#f1f5f9;margin:0 0 0.3rem 0;">🏥 {eta.get('hospital_name','')}</p>
  <p style="color:#94a3b8;font-size:0.88rem;margin:0 0 0.2rem 0;">📍 {eta.get('address','')}</p>
  <div style="display:flex;gap:1rem;flex-wrap:wrap;">
    <span style="color:#7dd3fc;font-size:0.95rem;">📏 {eta.get('distance_km','?')} km</span>
    <span style="color:#7dd3fc;font-size:0.95rem;">⏱ ~{eta.get('eta_minutes','?')} min</span>
    <span style="color:#86efac;font-size:0.9rem;">{occ}</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Registration number ───────────────────────────────────────────────
    st.markdown(f'<p style="font-size:0.9rem;font-weight:600;color:#94a3b8;margin:0 0 0.2rem 0;text-transform:uppercase;letter-spacing:0.06em;">{t("Your hospital registration number")}</p>', unsafe_allow_html=True)
    st.markdown(f'<div class="reg-box">{reg_no}</div>', unsafe_allow_html=True)
    st.markdown(f'<p style="color:#64748b;font-size:0.82rem;margin:0 0 0.8rem 0;text-align:center;">{t("Show this number at the hospital reception when you arrive")}</p>', unsafe_allow_html=True)

    # ── Emergency call (for EMERGENCY level) ────────────────────────────
    if level == TRIAGE_EMERGENCY:
        st.markdown(f"""
<div style="text-align:center;margin:0.5rem 0 1rem 0;">
  <a href="tel:{emg['number']}" style="background:#dc2626;color:white;padding:16px 40px;
     border-radius:12px;font-size:1.4rem;font-weight:800;text-decoration:none;
     display:inline-block;">
    📞 CALL {emg['number']}
  </a>
</div>
""", unsafe_allow_html=True)

    # ── Pre-arrival advice ────────────────────────────────────────────────
    advice = st.session_state.pre_arrival_advice
    if advice:
        do_list   = advice.get("do_list",   [])
        dont_list = advice.get("dont_list", [])
        if do_list or dont_list:
            border = {"EMERGENCY": "#dc2626", "URGENT": "#f59e0b", "ROUTINE": "#22c55e"}.get(level, "#3b82f6")
            st.markdown(f'<div style="border:2px solid {border};border-radius:14px;padding:1rem 1.2rem;margin:0.5rem 0;">', unsafe_allow_html=True)
            st.markdown(f"**⏱ {t('Before you arrive')}**")
            if do_list:
                st.markdown(f"**✅ {t('DO:')}**")
                for item in do_list:
                    st.markdown(f'<p class="do-item">✓ {item}</p>', unsafe_allow_html=True)
            if dont_list:
                st.markdown(f"**❌ {t('DO NOT:')}**")
                for item in dont_list:
                    st.markdown(f'<p class="dont-item">✗ {item}</p>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("⏳ Personalised advice being prepared...")

    # ── Location tracking note ─────────────────────────────────────────────
    _loc_keep  = t("Keep your location enabled while travelling")
    _loc_track = t("your care team tracks your arrival in real time")
    st.markdown(f"""
<div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:0.9rem 1rem;margin:0.8rem 0;">
  <p style="color:#94a3b8;font-size:0.88rem;margin:0;">
    📍 <strong style="color:#cbd5e1;">{_loc_keep}</strong> —
    {_loc_track}.
  </p>
</div>
""", unsafe_allow_html=True)

    st.divider()
    if st.button(f"🔄 {t('New assessment')}", type="primary", use_container_width=True, key="restart"):
        reset(); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🚑 CodeZero")
        st.caption("AI pre-hospital triage")
        st.divider()

        # ── Active patient card ──────────────────────────────────────────
        profile = st.session_state.get("patient_profile")
        if profile:
            age  = get_age(profile.get("date_of_birth", ""))
            hn   = st.session_state.health_number
            flag = {"DE": "🇩🇪", "TR": "🇹🇷", "UK": "🇬🇧"}.get(
                profile.get("nationality", ""), "🌍")
            st.markdown(
                f'''<div style="background:#1e293b;border-radius:10px;
                padding:0.6rem 0.8rem;margin-bottom:0.5rem;">
  <p style="color:#94a3b8;font-size:0.7rem;margin:0;text-transform:uppercase;
     letter-spacing:0.06em;">Active Patient</p>
  <p style="color:#f1f5f9;font-weight:700;margin:0.1rem 0;">
    {flag} {profile.get("first_name","")} {profile.get("last_name","")}</p>
  <p style="color:#64748b;font-size:0.78rem;margin:0;">
    {hn} &nbsp;·&nbsp; {profile.get("blood_type","?")} &nbsp;·&nbsp;
    {age}y &nbsp;·&nbsp; {profile.get("sex","")}</p>
</div>''', unsafe_allow_html=True)

        # ── Demo profile switcher ────────────────────────────────────────
        with st.expander("🔄 Switch demo profile"):
            all_nums = list_demo_health_numbers()
            opts = {}
            for hn in all_nums:
                p = get_patient(hn)
                if not p: continue
                flag = {"DE": "🇩🇪", "TR": "🇹🇷", "UK": "🇬🇧"}.get(
                    p.get("nationality", ""), "")
                opts[f"{flag} {p['first_name']} {p['last_name']} ({hn})"] = hn
            chosen = st.selectbox(
                "", list(opts.keys()),
                label_visibility="collapsed", key="sb_profile_sel")
            if st.button("Load →", use_container_width=True, key="sb_load_btn"):
                _load_profile(opts[chosen])
                # Reset the flow (keep profile, clear everything else)
                for k, v in _DEFAULTS.items():
                    if k not in ("health_number", "patient_profile",
                                 "detected_language", "country", "demographics"):
                        st.session_state[k] = v
                st.session_state[_TC] = {}
                st.session_state.step = "input"
                st.rerun()

        st.divider()

        # ── Step indicator ───────────────────────────────────────────────
        step   = st.session_state.step
        steps  = ["input", "photos", "questions", "triage", "result"]
        labels = [f"🎤 {t('Symptoms')}", f"📷 {t('Photos')}", f"❓ {t('Questions')}", f"🏥 {t('Hospital')}", f"✅ {t('Done')}"]
        cur = steps.index(step) if step in steps else -1
        for i, (s, lab) in enumerate(zip(steps, labels)):
            icon = "✅" if cur > i else ("▶" if s == step else "○")
            st.markdown(f"{icon} {lab}")

        st.divider()
        for svc, ok in _svc_status.items():
            st.markdown(f"{'✅' if ok else '⚠️'} {svc} — *{'Live' if ok else 'Demo'}*")
        st.divider()
        st.caption(f"⚠️ {t('Demo only. Call 112 for real emergencies.')}")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    _ensure_profile()          # auto-assign random profile on first run
    render_sidebar()
    step = st.session_state.step
    if   step == "input":        page_input()
    elif step == "photos":       page_photos()
    elif step == "demographics": page_demographics()
    elif step == "questions":    page_questions()
    elif step == "triage":       page_triage()
    elif step == "result":       page_result()
    else:                        page_input()

if __name__ == "__main__":
    main()