import re

filepath = "e:/3. projects/CodeZero/ui/patient_app_v8.html"
with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update Translations for new tab names
# Let's just update `rs_tab_status`, `rs_tab_instructions`, `rs_tab_contact` in EN, DE, TR blocks
old_en = "rs_tab_status: 'Check-in Auth', rs_tab_instructions: 'Instructions', rs_tab_contact: 'Emergency Contact'"
new_en = "rs_tab_status: 'Action', rs_tab_instructions: 'Journey', rs_tab_contact: 'Arrival'"

# We can replace the strings directly since they are uniquely formatted in a single block.
def replace_trans(lang_block, t0_old, t1_old, t2_old, t0_new, t1_new, t2_new):
    global text
    text = text.replace(f"rs_tab_status: '{t0_old}'", f"rs_tab_status: '{t0_new}'")
    text = text.replace(f"rs_tab_instructions: '{t1_old}'", f"rs_tab_instructions: '{t1_new}'")
    text = text.replace(f"rs_tab_contact: '{t2_old}'", f"rs_tab_contact: '{t2_new}'")

replace_trans('en', 'Check-in Auth', 'Instructions', 'Emergency Contact', 'Action', 'Journey', 'Arrival')
replace_trans('tr', 'Giriş İzni', 'Talimatlar', 'Acil Kişi', 'Aksiyon', 'Yolculuk', 'Varış')
replace_trans('de', 'Check-in Freigabe', 'Anweisungen', 'Notfallkontakt', 'Aktion', 'Reise', 'Ankunft')

# Check if TR and DE have the same translations (they don't exist exactly like that in the current file).
# Let's do it using regex to be safe.
import sys
import re

for lang, (t0, t1, t2) in [
    ('en', ('Action', 'Journey', 'Arrival')),
    ('de', ('Aktion', 'Reise', 'Ankunft')),
    ('tr', ('Aksiyon', 'Yolculuk', 'Varış'))
]:
    # Regex find lines starting with rs_tab_status: '...'
    text = re.sub(r"rs_tab_status:\s*'[^']+'", f"rs_tab_status: '{t0}'", text)
    text = re.sub(r"rs_tab_instructions:\s*'[^']+'", f"rs_tab_instructions: '{t1}'", text)
    text = re.sub(r"rs_tab_contact:\s*'[^']+'", f"rs_tab_contact: '{t2}'", text)
    break # Actually wait, the regex above will replace ALL languages with the EN one which is bad
          # I need to target the EN, TR, DE blocks separately.

# Clean regex replacement:
def update_tabs(lang, text, t0, t1, t2):
    # Find the block for the language
    start = text.find(f"{lang}: {{")
    if start == -1: return text
    
    # End of language block is roughly the next language key or end of TX
    end = text.find("},", start)
    if end == -1: end = len(text)
    
    block = text[start:end]
    block = re.sub(r"rs_tab_status:\s*'[^']+'", f"rs_tab_status: '{t0}'", block)
    block = re.sub(r"rs_tab_instructions:\s*'[^']+'", f"rs_tab_instructions: '{t1}'", block)
    block = re.sub(r"rs_tab_contact:\s*'[^']+'", f"rs_tab_contact: '{t2}'", block)
    
    return text[:start] + block + text[end:]

text = update_tabs('en', text, 'Action', 'Journey', 'Arrival')
text = update_tabs('de', text, 'Aktion', 'Reise', 'Ankunft')
text = update_tabs('tr', text, 'Aksiyon', 'Yolculuk', 'Varış')


# 2. Re-write the `renderResult()` function entirely
# We will match `function renderResult()` until `renderTriageBannerInternal(triageLevel);`

result_js = """
                function renderResult() {
                    const assessmentData = S.assessment || {};
                    const selectedHosp = S.selectedHospital;
                    if (!selectedHosp) return;

                    const triageLevel = (assessmentData.triage_level || 'URGENT').toUpperCase();
                    const resultPage = document.getElementById('page-result');
                    if (!resultPage) return;

                    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(S.regNumber)}`;

                    resultPage.innerHTML = `
                <div id="resultEmergencyCall"></div>
                
                <div class="result-tabs" style="margin-bottom: 20px;">
                    <button class="result-tab-btn active" onclick="switchResultTab(0)">
                        <i data-lucide="shield-alert" style="width:14px; height:14px; margin-right:4px;"></i>
                        ${t('rs_tab_status')}
                    </button>
                    <button class="result-tab-btn" onclick="switchResultTab(1)">
                        <i data-lucide="map" style="width:14px; height:14px; margin-right:4px;"></i>
                        ${t('rs_tab_instructions')}
                    </button>
                    <button class="result-tab-btn" onclick="switchResultTab(2)">
                        <i data-lucide="building-2" style="width:14px; height:14px; margin-right:4px;"></i>
                        ${t('rs_tab_contact')}
                    </button>
                </div>

                <!-- TAB 0: Action (Triage & Hospital Details) -->
                <div class="result-tab-panel active" id="resultTab0">
                    <div id="resultBanner" style="margin-bottom:14px;"></div>

                    <div class="card" style="margin-bottom:16px; border-left: 6px solid var(--success) !important;">
                        <p style="font-size:1.1rem; font-weight:800; color:var(--text); margin-bottom:4px; display:flex; align-items:center; gap:8px;">
                            <i data-lucide="hospital" style="width:18px; height:18px; color:var(--medical-blue)"></i>
                            ${escHtml(selectedHosp.name)}
                        </p>
                        <p style="font-size:.8rem; color:var(--text-2); margin-bottom:12px; padding-left: 26px;">
                            ${escHtml(selectedHosp.address || '')}
                        </p>
                        <div style="display:flex; gap:8px; flex-wrap:wrap; padding-left: 26px;">
                            <span class="hosp-chip" style="display:flex; align-items:center; gap:4px;">
                                <i data-lucide="navigation" style="width:12px; height:12px;"></i> ${selectedHosp.distance_km} km
                            </span>
                            <span class="hosp-chip" style="display:flex; align-items:center; gap:4px; color:var(--medical-blue); font-weight:700;">
                                <i data-lucide="timer" style="width:12px; height:12px;"></i> ~${selectedHosp.eta_minutes} min
                            </span>
                            <span class="hosp-chip" style="display:flex; align-items:center; gap:4px;">
                                <i data-lucide="info" style="width:12px; height:12px;"></i> ${escHtml(selectedHosp.occupancy_label || '')}
                            </span>
                        </div>
                    </div>
                    
                    <div id="resultAdvice"></div>
                </div>

                <!-- TAB 1: Journey (Navigation & Tracking) -->
                <div class="result-tab-panel" id="resultTab1">
                    <button class="btn btn-secondary" onclick="window.open('https://www.google.com/maps/dir/?api=1&destination=${selectedHosp.lat},${selectedHosp.lon}')" style="margin-bottom:24px; gap:8px; border-color:var(--medical-primary); color:var(--medical-primary); font-weight:700; height: 56px;">
                        <i data-lucide="map-pin" style="width:18px; height:18px;"></i>
                        ${t('rs_openNav')}
                    </button>
                    
                    <div class="card" style="background:var(--accent-blue) !important; border:none; text-align:center; padding:20px !important;">
                        <div style="display:flex; align-items:center; justify-content:center; gap:10px;">
                            <div class="live-glow"></div>
                            <span style="font-weight:800; font-size:16px; color:var(--medical-blue); display:flex; align-items:center; gap:6px;">
                                <i data-lucide="radio" style="width:18px; height:18px;"></i>
                                ${t('rs_liveTrackingTitle')}
                            </span>
                        </div>
                        <p style="font-size:13px; color:var(--medical-blue); opacity:0.8; margin:8px 0 0;">${t('rs_liveTrackingSub')}</p>
                    </div>
                </div>

                <!-- TAB 2: Arrival (QR Check-In & Contact) -->
                <div class="result-tab-panel" id="resultTab2">
                    <div class="digital-pass" style="margin-bottom: 20px;">
                        <div style="background: var(--medical-blue); color: white; padding: 14px; text-align: center; font-weight: 800; font-size: 0.7rem; letter-spacing: 1.5px; text-transform: uppercase; display: flex; align-items: center; justify-content: center; gap: 6px;">
                            <i data-lucide="shield-check" style="width:14px; height:14px;"></i>
                            ${t('rs_checkinAuth')}
                        </div>
                        <div style="padding: 24px 20px; text-align: center;">
                            <div style="display: flex; flex-direction: column; align-items: center; margin-bottom: 16px;">
                                <i data-lucide="fingerprint" style="width:20px; height:20px; color:var(--text-3); margin-bottom:6px;"></i>
                                <div style="font-size: 0.65rem; color: var(--text-2); font-weight: 700; letter-spacing: 1px; text-transform: uppercase;">${t('rs_patientId')}</div>
                                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; font-weight: 800; color: var(--medical-blue);">${S.regNumber}</div>
                            </div>
                            
                            <div style="background: var(--ios-bg); display: inline-block; padding: 12px; border-radius: 18px; margin-bottom: 20px; border: 1px solid var(--border);">
                                <img src="${qrUrl}" alt="QR Code" style="width:130px; height:130px; border-radius:8px; display: block;">
                            </div>

                            <div style="border-top: 2px dashed var(--ios-bg); margin: 0 -20px 20px; position: relative;"></div>

                            <div style="display: flex; align-items: center; justify-content: center; text-align:center; gap: 8px; color: var(--text-2); font-size: 0.8rem; font-weight: 600; line-height: 1.4;">
                                <i data-lucide="scan-face" style="width:16px; height:16px; color:var(--medical-blue); flex-shrink:0;"></i>
                                <span>${t('rs_passFooter')}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card" style="margin-bottom:16px; border:none; background:var(--blue-light);">
                        <h2 style="font-size:1rem; font-weight:800; margin-bottom:10px; display:flex; align-items:center; gap:8px; color:var(--medical-blue);">
                            <i data-lucide="user-plus" style="width:20px; height:20px;"></i>
                            ${t('rs_contactTitle')}
                        </h2>
                        <button class="btn btn-primary" id="rs_contactBtn" onclick="notifyContact()" style="height:50px; gap:10px;">
                            <i data-lucide="send" style="width:16px; height:16px;"></i>
                            ${t('rs_contactSendBtn')}
                        </button>
                    </div>
                </div>
                
                <div class="divider"></div>
                <button class="btn btn-secondary" onclick="location.reload()" style="margin-bottom:8px; font-weight:700;">
                    <i data-lucide="refresh-cw" style="width:16px; height:16px; margin-right:6px;"></i>
                    ${t('rs_newBtn')}
                </button>
                <p style="text-align:center; font-size:.7rem; color:var(--text-4); margin-top:10px;">
                    <i data-lucide="info" style="width:12px; height:12px; vertical-align:middle; margin-right:2px;"></i>
                    ${t('rs_demo')}
                </p>
            `;
"""

start_marker = "                function renderResult() {"
end_marker = "                    renderTriageBannerInternal(triageLevel);"

start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx != -1 and end_idx != -1:
    text = text[:start_idx] + result_js + "\\n" + text[end_idx:]

with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)

print("Refactor stage 3 complete.")
