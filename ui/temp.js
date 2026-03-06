

        function notifyContact() {
            const btn = document.getElementById("rs_contactBtn");
            if (!btn) return;

            const orig = btn.innerHTML;
            btn.innerHTML = `<i data-lucide="loader-2" class="spin" style="width:18px; height:18px;"></i> Sending...`;
            lucide.createIcons();

            setTimeout(() => {
                btn.classList.remove("btn-secondary");
                btn.style.background = "var(--success)";
                btn.style.color = "#fff";
                btn.style.borderColor = "var(--success)";
                btn.innerHTML = `<i data-lucide="check-circle" style="width:18px; height:18px;"></i> Contact Notified`;
                lucide.createIcons();
            }, 1500);
        }
    


            // Auto-detect API base: same origin when served via hospital_server.py (ngrok or local)
            // Falls back to localhost:8001 when opened as a standalone file
            const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
                ? 'http://localhost:8001'
                : location.origin;
            // ═══════════════════════════════════════════════════════════
            // DEMO PATIENTS per language
            // ═══════════════════════════════════════════════════════════
            const DEMO_PATIENTS = {
                tr: [
                    { id: 'DEMO-TR-001', name: 'Ahmet Yılmaz', detail: 'E · 61y · B+ · T2DM, HT' },
                    { id: 'DEMO-TR-002', name: 'Fatma Kaya', detail: 'K · 48y · A+ · Romatoid Artrit' },
                    { id: 'DEMO-TR-003', name: 'Mustafa Demir', detail: 'E · 76y · O+ · KAH post-KABG' },
                    { id: 'DEMO-TR-004', name: 'Zeynep Şahin', detail: 'K · 36y · AB+ · Epilepsi' },
                    { id: 'DEMO-TR-005', name: 'Mehmet Çelik', detail: 'E · 54y · A- · KOAH' },
                    { id: 'DEMO-TR-006', name: 'Ayşe Arslan', detail: 'K · 41y · B- · Hashimoto' },
                    { id: 'DEMO-TR-007', name: 'Ali Doğan', detail: 'E · 68y · O- · Prostat Ca post-op' },
                    { id: 'DEMO-TR-008', name: 'Elif Yıldız', detail: 'K · 24y · A+ · Demir eksikliği anemisi' },
                    { id: 'DEMO-TR-009', name: 'İbrahim Koç', detail: 'E · 82y · AB+ · Parkinson' },
                    { id: 'DEMO-TR-010', name: 'Hatice Öztürk', detail: 'K · 58y · O+ · Osteoporoz' },
                ],
                de: [
                    { id: 'DEMO-DE-001', name: 'Klaus Müller', detail: 'M · 68y · A+ · KHK, Hypertonie' },
                    { id: 'DEMO-DE-002', name: 'Anna Schneider', detail: 'W · 41y · O+ · T1DM, Insulinpumpe' },
                    { id: 'DEMO-DE-003', name: 'Heinrich Weber', detail: 'M · 55y · B+ · COPD Grad 2' },
                    { id: 'DEMO-DE-004', name: 'Sophie Fischer', detail: 'W · 34y · AB+ · Migräne mit Aura' },
                    { id: 'DEMO-DE-005', name: 'Wolfgang Bauer', detail: 'M · 81y · O- · VHF, Schrittmacher' },
                    { id: 'DEMO-DE-006', name: 'Lena Wagner', detail: 'W · 26y · A- · Anaphylaxie (Biene)' },
                    { id: 'DEMO-DE-007', name: 'Thomas Becker', detail: 'M · 63y · B- · T2DM, Adipositas' },
                    { id: 'DEMO-DE-008', name: 'Mia Schmitt', detail: 'W · 28y · O+ · Asthma moderat' },
                    { id: 'DEMO-DE-009', name: 'Franz Kraus', detail: 'M · 74y · A+ · CKD Grad 3, Gicht' },
                    { id: 'DEMO-DE-010', name: 'Emma Zimmermann', detail: 'W · 51y · AB- · Hypothyreose' },
                ],
                en: [
                    { id: 'DEMO-UK-001', name: 'James Wilson', detail: 'M · 71y · O+ · IHD, Heart Failure EF40%' },
                    { id: 'DEMO-UK-002', name: 'Emily Clarke', detail: 'F · 38y · O- · Moderate Asthma' },
                    { id: 'DEMO-UK-003', name: 'Robert Johnson', detail: 'M · 81y · A+ · COPD+T2DM+HTN' },
                    { id: 'DEMO-UK-004', name: 'Charlotte Brown', detail: "F · 34y · B+ · Crohn's Disease" },
                    { id: 'DEMO-UK-005', name: 'William Taylor', detail: 'M · 66y · AB+ · HTN, Gout' },
                    { id: 'DEMO-UK-006', name: 'Olivia Martin', detail: 'F · 25y · A- · T1DM, Insulin Pump' },
                    { id: 'DEMO-UK-007', name: 'George White', detail: 'M · 56y · B- · Bipolar Disorder' },
                    { id: 'DEMO-UK-008', name: 'Isabella Davies', detail: 'F · 43y · O+ · Migraine, Endometriosis' },
                    { id: 'DEMO-UK-009', name: 'Henry Moore', detail: 'M · 88y · A+ · Aortic Stenosis, AF' },
                    { id: 'DEMO-UK-010', name: 'Amelia Garcia', detail: 'F · 49y · AB- · SLE' },
                ],
            };

            const symptoms = [
                { id: 'chest_pain' },
                { id: 'shortness_breath' },
                { id: 'headache' },
                { id: 'fever' },
                { id: 'dizziness' },
                { id: 'abdominal_pain' },
                { id: 'fainting' },
                { id: 'severe_bleeding' },
                { id: 'allergic_reaction' },
                { id: 'vomiting_diarrhea' },
                { id: 'numbness_weakness' },
                { id: 'altered_consciousness' }
            ];

            function renderSymptoms() {
                const grid = document.getElementById('symptomGrid');
                if (!grid) return;
                grid.innerHTML = symptoms.map(s => `
                <div class="symptom-card" onclick="toggleSymptom(this, '${s.id}')">
                    ${t('sym_' + s.id)}
                </div>
            `).join('');
            }

            function toggleSymptom(el, id) {
                el.classList.toggle('selected');
                const selectedNodes = document.querySelectorAll('.symptom-card.selected');

                // Semptomları diziye al
                const selectedTexts = Array.from(selectedNodes).map(node => node.textContent.trim());

                // Eğer ses kaydı varsa, üzerine semptomları ekle
                let finalComplaint = "";
                if (S.voiceTranscript) {
                    finalComplaint = S.voiceTranscript + (selectedTexts.length > 0 ? ", " : "");
                }
                finalComplaint += selectedTexts.join(', ');

                S.complaint = finalComplaint;
                enableContinue(S.complaint.length > 0);
            }

            function enableContinue(on) {
                const btn = document.getElementById('btnContinueInput');
                if (btn) {
                    btn.disabled = !on;
                    btn.style.opacity = on ? '1' : '0.45';
                    btn.style.cursor = on ? 'pointer' : 'not-allowed';
                }
            }

            document.addEventListener('DOMContentLoaded', () => {
                renderSymptoms();
                lucide.createIcons();
            });
            // ═══════════════════════════════════════════════════════════
            // TRANSLATIONS
            // ═══════════════════════════════════════════════════════════
            const TX = {
                en: {
                    topbarLang: 'EN',
                    wl_whatLabel: 'What is VitalNavAI?',
                    wl_whatDesc: 'When you face a medical emergency, VitalNavAI uses AI to:',
                    wl_b1: 'Inform you and the hospital about your condition <strong>before you arrive</strong>',
                    wl_b2: 'Minimise your <strong>waiting time</strong> at the emergency room',
                    wl_b3: 'Direct you to the <strong>most appropriate hospital</strong> near you',
                    wl_howLabel: 'How to use',
                    wl_s1: '<strong style="color:var(--navy)">🎤 Speak</strong> — describe your symptoms clearly in your own words.',
                    wl_s2: '<strong style="color:var(--navy)">❓ Questions</strong> — answer a few short follow-up questions.',
                    wl_s3: '<strong style="color:var(--navy)">🏥 Hospital</strong> — the best hospital is selected and notified.',
                    wl_demo: 'Demo only. Call 112 for real emergencies.',
                    wl_hnLabel: 'Select your health number for Demo', wl_hnReq: 'REQUIRED',
                    wl_hnHintText: 'Your medical history will be linked to this visit',
                    btnStart: 'Start →',
                    inp_title: 'Describe your symptoms',
                    inp_sub: 'Use voice or select symptoms below.',
                    inp_orSelect: 'Or select symptoms',
                    micStatus: 'Tap to Speak',
                    sym_chest_pain: 'Chest Pain',
                    sym_shortness_breath: 'Shortness of Breath',
                    sym_headache: 'Severe Headache',
                    sym_fever: 'High Fever',
                    sym_dizziness: 'Dizziness',
                    sym_abdominal_pain: 'Abdominal Pain',
                    sym_fainting: 'Fainting',
                    sym_severe_bleeding: 'Severe/Unstoppable Bleeding',
                    sym_allergic_reaction: 'Severe Allergic Reaction',
                    sym_vomiting_diarrhea: 'Persistent Vomiting or Diarrhea',
                    sym_numbness_weakness: 'Body Numbness or Weakness',
                    sym_altered_consciousness: 'Altered Consciousness',
                    micLabelRec: 'Listening...',
                    micSubRec: 'Tap to stop',
                    micLabelDone: 'Recorded',
                    micSubDone: 'Tap to record again',
                    transcriptLang: 'AI Transcript',
                    inputSpinnerText: 'Processing voice...',
                    inp_continueTxt: 'Start Analysis',
                    inp_examples: ['Chest pain', 'Difficulty breathing', 'Severe headache', 'High fever', 'Dizziness', 'Abdominal pain', 'Nausea / vomiting', 'Leg swelling', 'Back pain', 'Fainting', 'Palpitations', 'Allergic reaction'],
                    ph_title: 'Add photos or video',
                    ph_sub: '<span style="color: var(--primary); font-weight: 900; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; background: rgba(10,132,255,0.1); padding: 4px 10px; border-radius: 8px;">Optional</span><br><span style="font-size: 1.05rem; color: var(--text-2); line-height: 1.5; display: block; margin-top: 12px;">If you have a visible wound, rash, swelling, or if a short video clip can help explain your condition, please upload it. This helps the medical team prepare before your arrival.</span>',
                    ph_continueTxt: 'Continue',
                    ph_addPhoto: 'Photo', ph_addVideo: 'Video', ph_skip: 'Skip →',
                    questionsIntro: 'To assess your condition better, please answer the short questions in the next section.\n\nAI is generating personalised questions, please wait…',
                    questionsSpinnerText: 'Generating questions…',
                    aiMode_real: '🤖 AI-generated questions', aiMode_mock: '⚠️ Demo mode — AI offline',
                    fq_onset: 'When did your symptoms start?',
                    fq_onset_now: 'Just now (< 15 min)', fq_onset_1h: 'Within the last hour', fq_onset_6h: '1–6 hours ago', fq_onset_24h: '6–24 hours ago', fq_onset_days: 'More than a day ago',
                    fq_pain_scale: 'How would you rate your pain on a scale of 1–10?',
                    fq_breathing: 'Are you having difficulty breathing right now?',
                    fq_fever: 'What is your approximate temperature?',
                    fq_nausea: 'Are you experiencing nausea or vomiting?',
                    fq_conditions: 'Do you have any known medical conditions?',
                    fq_cond_none: 'None', fq_cond_heart: 'Heart disease', fq_cond_diab: 'Diabetes', fq_cond_bp: 'High blood pressure', fq_cond_other: 'Other',
                    fq_medications: 'Are you currently taking any medications?',
                    fq_allergies: 'Do you have any known drug allergies?',
                    fq_yes: 'Yes', fq_no: 'No', fq_unsure: 'Not sure',
                    q_back: 'Back', q_next: 'Next', q_of: 'of', q_done: 'Done →',
                    cs_title: 'Almost done', cs_sub: 'Review what will be shared with the hospital',
                    cs_consentLabel: 'Data sharing consent',
                    cs_consentDesc: 'Do you consent to sharing the following with the hospital?',
                    cs_line1: 'Symptom description and Q&A answers',
                    cs_photoLine: 'Media: {n} file(s) attached',
                    cs_line3: 'AI triage assessment and risk level',
                    cs_line4: 'Real-time location (live tracking)',
                    cs_yes: '✅ Yes — share my information', cs_no: '❌ No — do not share my data',
                    consentWarning: 'You must consent to proceed.',
                    assessSpinnerText: 'Analysing your symptoms with AI…',
                    cs_btnTxt: 'Get my assessment →',
                    cs_secureText: 'Your data is processed securely.',
                    gps_waitTitle: 'Detecting your location…',
                    gps_waitSub: 'Tap <strong>Allow</strong> when your browser asks.',
                    gps_deniedTitle: '🔒 Location access required',
                    gps_deniedDesc: 'We need your location to find the nearest hospital.',
                    gps_deniedSteps: '① Tap the 🔒 lock in your browser bar<br>② Site settings → Location → <strong>Allow</strong><br>③ Come back and tap Retry',
                    gps_retryBtn: '🔄 Retry',
                    gpsDetecting: 'Detecting location…', gpsOk: 'Location confirmed', gpsDenied: 'Location denied',
                    tr_nearestLabel: 'Current traffic &amp; hospital occupancy — choose one of the recommended hospitals',
                    tr_adviceLabel: 'Before you arrive', tr_fastest: '⭐ Best choice',
                    tr_hospSpinner: 'Finding best hospitals…', tr_noHosp: 'No hospitals found nearby.', tr_notifying: 'Notifying hospital…',
                    tr_emg_title: '🚨 Go to emergency immediately', tr_emg_sub: 'Your symptoms require urgent care — do not wait',
                    tr_urg_title: '⚠️ You need hospital care soon', tr_urg_sub: 'Please find a hospital within the next 30 minutes',
                    tr_rtn_title: 'ℹ️ You should see a doctor today', tr_rtn_sub: 'Your symptoms are not immediately life-threatening',
                    tr_orBelow: '— or select a hospital below —',
                    tr_doLabel: '✅ DO:', tr_dontLabel: "❌ DON'T:",
                    rs_regLabel: 'Your registration number', rs_regHint: 'Show this at hospital reception on arrival.',
                    rs_notified_emg: '🚨 Hospital notified — head there now!', rs_notified_sub_emg: 'They are preparing for your arrival',
                    rs_notified_urg: '✅ Hospital notified', rs_notified_sub_urg: 'Please follow the instructions below',
                    rs_notified_rtn: '✅ Your information has been sent', rs_notified_sub_rtn: 'See instructions below before leaving',
                    rs_trackTitle: 'Keep location enabled while travelling', rs_trackSub: 'Your care team tracks your arrival in real time.',
                    rs_newBtn: 'New assessment',
                    rs_passFooter: 'Show this pass to the triage nurse or scan your QR code at the hospital entrance upon arrival.',
                    rs_tab_status: 'Action',
                    rs_tab_instructions: 'Journey',
                    rs_tab_contact: 'Arrival',
                    rs_openNav: 'Open Navigation', rs_liveTrackingTitle: 'LIVE TRACKING ACTIVE', rs_liveTrackingSub: 'The medical team is monitoring your GPS for arrival.', rs_passFooter: 'Show this pass to the triage nurse immediately upon arrival.',
                    wl_langHeroSub: 'AI Emergency Assistant', inp_backBtn: 'Back', ph_backBtn: 'Back', gps_privacyText: 'Your location is only used to find the most suitable hospital. Your identity is kept confidential.', rs_contactTitle: 'Notify Contact Person', rs_contactDesc: 'The following will be sent to your emergency contact:', rs_contactItem1: 'Your triage status & registration number', rs_contactItem2: 'Assigned hospital name & address', rs_contactItem3: 'Your current location (one-time share)', rs_contactSendBtn: 'Send notification now', rs_demo: '⚠️ Demo only. Call 112 for real emergencies.', rs_prelimNotice: '⚠️ This is a preliminary assessment. The final decision rests with healthcare personnel.',
                    aiChecking: 'Checking AI…', aiConnected: '🤖 AI connected — real-time analysis', aiDemo: '⚙️ Demo mode — AI not configured',
                    adv_call112: 'Call 112 immediately or have someone call for you', adv_sit_still: 'Sit or lie down and do not move', adv_stay_calm: 'Stay calm and breathe slowly', adv_rest: 'Rest and avoid physical exertion', adv_someone_with_you: 'Have someone accompany you to the hospital', adv_bring_meds: 'Bring all current medications with you', adv_bring_id: 'Bring your ID and insurance card', adv_no_drive: 'Do NOT drive yourself to the hospital', adv_no_eat: 'Do not eat or drink anything until examined', adv_chest_loose: 'Loosen tight clothing around your chest', adv_chest_no_stress: 'Avoid physical or emotional stress', adv_bleed_pressure: 'Apply firm pressure to the wound with a clean cloth', adv_bleed_no_remove: 'Do not remove any object embedded in a wound', adv_breath_upright: 'Sit upright — do not lie flat', adv_breath_no_lie: 'Do not lie flat — this worsens breathing', adv_head_dark: 'Rest in a quiet, dark room if possible', adv_head_no_screen: 'Avoid screens, bright lights and loud noise', adv_proceed_er: 'Go to the emergency room as soon as possible',
                    hnPlaceholder: 'Choose your health record…',
                    tr_aiRoutingTitle: 'AI Smart Routing',
                    tr_aiRoutingSub: 'We route you based on real-time data.',
                    tr_liveTraffic: 'Traffic',
                    tr_erCapacity: 'ER Density',
                    tr_selectHospital: 'Select a Recommended Hospital',
                    tr_traffic_clear: 'Clear', tr_traffic_medium: 'Moderate', tr_traffic_heavy: 'Heavy',
                    tr_er_low: 'Low', tr_er_medium: 'Medium', tr_er_high: 'High', tr_er_full: 'Full',
                    wl_system_notice: 'This system has been developed to determine medical priorities.',
                    cs_data_secure: 'Your data is processed securely.',
                    rs_patientId: 'Patient Identifier',
                    rs_checkinAuth: 'CHECK-IN AUTHORIZATION'

                },
                de: {
                    topbarLang: 'DE',
                    wl_whatLabel: 'Was ist VitalNavAI?',
                    wl_whatDesc: 'Bei einem medizinischen Notfall nutzt VitalNavAI KI, um:',
                    wl_b1: 'Sie und das Krankenhaus über Ihren Zustand <strong>vor Ihrer Ankunft</strong> zu informieren',
                    wl_b2: 'Ihre <strong>Wartezeit</strong> in der Notaufnahme zu minimieren',
                    wl_b3: 'Sie zum <strong>nächstgelegenen geeigneten Krankenhaus</strong> zu leiten',
                    wl_howLabel: 'So verwenden Sie die App',
                    wl_s1: '<strong style="color:var(--navy)">🎤 Sprechen</strong> — beschreiben Sie Ihre Symptome in Ihren eigenen Worten.',
                    wl_s2: '<strong style="color:var(--navy)">❓ Fragen</strong> — beantworten Sie kurze Folgefragen.',
                    wl_s3: '<strong style="color:var(--navy)">🏥 Krankenhaus</strong> — das beste Krankenhaus wird ausgewählt und benachrichtigt.',
                    wl_demo: 'Nur Demo. Im Notfall 112 anrufen.',
                    wl_hnLabel: 'Krankenakte auswählen', wl_hnReq: 'PFLICHTFELD',
                    wl_hnHintText: 'Ihre Krankengeschichte wird mit diesem Besuch verknüpft',
                    btnStart: 'Starten →',
                    inp_title: 'Beschreiben Sie Ihre Symptome',
                    inp_sub: 'Sprechen Sie oder wählen Sie Symptome.',
                    inp_orSelect: 'Oder Symptome wählen',
                    micStatus: 'Tippen zum Sprechen',
                    sym_chest_pain: 'Brustschmerzen',
                    sym_shortness_breath: 'Atemnot',
                    sym_headache: 'Starke Kopfschmerzen',
                    sym_fever: 'Hohes Fieber',
                    sym_dizziness: 'Schwindel',
                    sym_abdominal_pain: 'Bauchschmerzen',
                    sym_fainting: 'Ohnmacht',
                    sym_severe_bleeding: 'Unstillbare Blutung',
                    sym_allergic_reaction: 'Schwere allergische Reaktion',
                    sym_vomiting_diarrhea: 'Anhaltendes Erbrechen/Durchfall',
                    sym_numbness_weakness: 'Taubheitsgefühl oder Schwäche',
                    sym_altered_consciousness: 'Bewusstseinsveränderung',
                    micLabelRec: 'Hören zu...',
                    micSubRec: 'Stoppen tippen',
                    micLabelDone: 'Aufgezeichnet',
                    micSubDone: 'Erneut aufnehmen tippen',
                    transcriptLang: 'KI-Transkript',
                    inputSpinnerText: 'Stimme wird verarbeitet...',
                    inp_continueTxt: 'Analyse starten',
                    inp_examples: ['Brustschmerzen', 'Atemnot', 'Starke Kopfschmerzen', 'Hohes Fieber', 'Schwindel', 'Bauchschmerzen'],
                    ph_title: 'Fotos oder Video hinzufügen',
                    ph_sub: '<span style="color: var(--primary); font-weight: 900; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; background: rgba(10,132,255,0.1); padding: 4px 10px; border-radius: 8px;">Optional</span><br><span style="font-size: 1.05rem; color: var(--text-2); line-height: 1.5; display: block; margin-top: 12px;">Wenn Sie eine sichtbare Wunde, einen Ausschlag oder eine Schwellung haben oder ein kurzes Video Ihren Zustand besser erklären kann, laden Sie es bitte hoch. Dies hilft dem medizinischen Team bei der Vorbereitung.</span>',
                    ph_continueTxt: 'Weiter',
                    ph_addPhoto: 'Foto', ph_addVideo: 'Video', ph_skip: 'Überspringen →',
                    questionsIntro: 'Um Ihren Zustand besser beurteilen zu können, beantworten Sie bitte die kurzen Fragen im nächsten Abschnitt.\n\nKI generiert personalisierte Fragen, bitte warten…',
                    questionsSpinnerText: 'Fragen werden generiert…',
                    aiMode_real: '🤖 KI-generierte Fragen', aiMode_mock: '⚠️ Demo-Modus — KI offline',
                    fq_onset: 'Wann haben Ihre Beschwerden begonnen?',
                    fq_onset_now: 'Gerade eben (< 15 Min)', fq_onset_1h: 'Innerhalb der letzten Stunde', fq_onset_6h: 'Vor 1–6 Stunden', fq_onset_24h: 'Vor 6–24 Stunden', fq_onset_days: 'Vor mehr als einem Tag',
                    fq_pain_scale: 'Wie stark sind Ihre Schmerzen (Skala 1–10)?',
                    fq_breathing: 'Haben Sie gerade Atemschwierigkeiten?', fq_fever: 'Wie hoch ist Ihre ungefähre Körpertemperatur?',
                    fq_nausea: 'Leiden Sie unter Übelkeit oder Erbrechen?', fq_conditions: 'Haben Sie bekannte Vorerkrankungen?',
                    fq_cond_none: 'Keine', fq_cond_heart: 'Herzerkrankung', fq_cond_diab: 'Diabetes', fq_cond_bp: 'Bluthochdruck', fq_cond_other: 'Sonstiges',
                    fq_medications: 'Nehmen Sie derzeit Medikamente ein?', fq_allergies: 'Haben Sie bekannte Medikamentenallergien?',
                    fq_yes: 'Ja', fq_no: 'Nein', fq_unsure: 'Nicht sicher',
                    q_back: 'Zurück', q_next: 'Weiter', q_of: 'von', q_done: 'Fertig →',
                    cs_title: 'Fast fertig', cs_sub: 'Überprüfen Sie, was mit dem Krankenhaus geteilt wird',
                    cs_consentLabel: 'Einwilligung zur Datenweitergabe',
                    cs_consentDesc: 'Stimmen Sie zu, die folgenden Informationen zu teilen?',
                    cs_line1: 'Symptombeschreibung und Antworten', cs_photoLine: 'Medien: {n} Datei(en) beigefügt',
                    cs_line3: 'KI-Triage-Bewertung und Risikostufe', cs_line4: 'Echtzeit-Standort (Live-Tracking)',
                    cs_yes: '✅ Ja — Informationen teilen', cs_no: '❌ Nein — nicht teilen',
                    consentWarning: 'Sie müssen zustimmen, um fortzufahren.',
                    assessSpinnerText: 'Symptome werden mit KI analysiert…', cs_btnTxt: 'Bewertung erhalten →',
                    cs_secureText: 'Ihre Daten werden sicher verarbeitet.',
                    gps_waitTitle: 'Standort wird erkannt…', gps_waitSub: 'Tippen Sie auf <strong>Zulassen</strong>, wenn Ihr Browser danach fragt.',
                    gps_deniedTitle: '🔒 Standortzugriff erforderlich', gps_deniedDesc: 'Wir benötigen Ihren Standort, um das nächste Krankenhaus zu finden.',
                    gps_deniedSteps: '① Auf das 🔒-Symbol tippen<br>② Seiteneinstellungen → Standort → <strong>Zulassen</strong><br>③ Zurückkehren und Erneut versuchen tippen',
                    gps_retryBtn: '🔄 Erneut versuchen',
                    gpsDetecting: 'Standort wird erkannt…', gpsOk: 'Standort bestätigt', gpsDenied: 'Standort verweigert',
                    tr_nearestLabel: 'Empfohlene Krankenhäuser basierend auf aktuellem Verkehr und Notaufnahme-Auslastung',
                    tr_adviceLabel: 'Vor Ihrer Ankunft', tr_fastest: '⭐ Beste Wahl',
                    tr_hospSpinner: 'Beste Krankenhäuser werden gesucht…', tr_noHosp: 'Keine Krankenhäuser in der Nähe gefunden.', tr_notifying: 'Krankenhaus wird benachrichtigt…',
                    tr_emg_title: '🚨 Sofort in die Notaufnahme', tr_emg_sub: 'Ihre Symptome erfordern sofortige Versorgung — nicht warten',
                    tr_urg_title: '⚠️ Baldiger Krankenhausbesuch nötig', tr_urg_sub: 'Bitte innerhalb der nächsten 30 Minuten ein Krankenhaus aufsuchen',
                    tr_rtn_title: 'ℹ️ Heute einen Arzt aufsuchen', tr_rtn_sub: 'Ihre Symptome sind nicht unmittelbar lebensbedrohlich',
                    tr_orBelow: '— oder unten ein Krankenhaus auswählen —', tr_doLabel: '✅ TUN:', tr_dontLabel: '❌ NICHT TUN:',
                    rs_regLabel: 'Ihre Registrierungsnummer', rs_regHint: 'Zeigen Sie diese an der Krankenhausrezeption.',
                    rs_notified_emg: '🚨 Krankenhaus informiert — jetzt fahren!', rs_notified_sub_emg: 'Sie bereiten sich auf Ihre Ankunft vor',
                    rs_notified_urg: '✅ Krankenhaus informiert', rs_notified_sub_urg: 'Bitte folgen Sie den Anweisungen unten',
                    rs_notified_rtn: '✅ Ihre Informationen wurden gesendet', rs_notified_sub_rtn: 'Lesen Sie die Anweisungen vor der Abfahrt',
                    rs_trackTitle: 'Standort während der Fahrt aktiviert lassen', rs_trackSub: 'Ihr Pflegeteam verfolgt Ihre Ankunft in Echtzeit.',
                    rs_newBtn: 'Neue Bewertung',
                    rs_passFooter: 'Zeigen Sie diesen Pass der Triage-Schwester oder scannen Sie den QR-Code am Krankenhauseingang.',
                    rs_tab_status: 'Aktion',
                    rs_tab_instructions: 'Reise',
                    rs_tab_contact: 'Ankunft',
                    rs_openNav: 'Navigation öffnen', rs_liveTrackingTitle: 'LIVE-TRACKING AKTIV', rs_liveTrackingSub: 'Das Team überwacht Ihre GPS-Position für die Ankunft.', rs_passFooter: 'Zeigen Sie diesen Pass sofort der Triage-Schwester bei Ankunft.',
                    wl_langHeroSub: 'KI-Notfallassistent', inp_backBtn: 'Zurück', ph_backBtn: 'Zurück', gps_privacyText: 'Ihr Standort wird nur verwendet, um das geeignetste Krankenhaus zu finden. Ihre Identität bleibt vertraulich.', rs_contactTitle: 'Kontaktperson benachrichtigen', rs_contactDesc: 'Folgendes wird an Ihren Notfallkontakt gesendet:', rs_contactItem1: 'Ihr Triagstatus & Registrierungsnummer', rs_contactItem2: 'Name & Adresse des Krankenhauses', rs_contactItem3: 'Ihr aktueller Standort (einmalig)', rs_contactSendBtn: 'Benachrichtigung senden', rs_demo: '⚠️ Nur Demo. Im Notfall 112 anrufen.',
                    aiChecking: 'KI-Status wird geprüft…', aiConnected: '🤖 KI verbunden — Echtzeit-Analyse', aiDemo: '⚙️ Demo-Modus — KI nicht konfiguriert',
                    adv_call112: 'Rufen Sie sofort 112 an oder lassen Sie jemanden rufen', adv_sit_still: 'Setzen oder legen Sie sich hin und bewegen Sie sich nicht', adv_stay_calm: 'Bleiben Sie ruhig und atmen Sie langsam', adv_rest: 'Ruhen Sie sich aus und vermeiden Sie körperliche Anstrengung', adv_someone_with_you: 'Lassen Sie sich von jemandem ins Krankenhaus begleiten', adv_bring_meds: 'Bringen Sie alle aktuellen Medikamente mit', adv_bring_id: 'Bringen Sie Ausweis und Krankenversicherungskarte mit', adv_no_drive: 'Fahren Sie NICHT selbst ins Krankenhaus', adv_no_eat: 'Essen oder trinken Sie nichts bis zur Untersuchung', adv_chest_loose: 'Lockern Sie enge Kleidung um die Brust', adv_chest_no_stress: 'Vermeiden Sie körperlichen oder emotionalen Stress', adv_bleed_pressure: 'Drücken Sie mit einem sauberen Tuch fest auf die Wunde', adv_bleed_no_remove: 'Entfernen Sie keinen in der Wunde steckenden Gegenstand', adv_breath_upright: 'Sitzen Sie aufrecht — legen Sie sich nicht hin', adv_breath_no_lie: 'Legen Sie sich nicht flach hin — das verschlimmert die Atmung', adv_head_dark: 'Ruhen Sie sich in einem ruhigen, dunklen Raum aus', adv_head_no_screen: 'Vermeiden Sie Bildschirme, helles Licht und Lärm', adv_proceed_er: 'Gehen Sie so schnell wie möglich in die Notaufnahme',
                    hnPlaceholder: 'Krankenakte auswählen…',
                    tr_aiRoutingTitle: 'KI Smart Routing',
                    tr_aiRoutingSub: 'Wir leiten Sie basierend auf Echtzeitdaten weiter.',
                    tr_liveTraffic: 'Verkehr',
                    tr_erCapacity: 'ER Auslastung',
                    tr_selectHospital: 'Wählen Sie ein Krankenhaus',
                    tr_traffic_clear: 'Frei', tr_traffic_medium: 'Mäßig', tr_traffic_heavy: 'Viel',
                    tr_er_low: 'Wenig', tr_er_medium: 'Mittel', tr_er_high: 'Hoch', tr_er_full: 'Voll',
                    wl_system_notice: 'Dieses System wurde entwickelt, um medizinische Prioritäten zu bestimmen.',
                    cs_data_secure: 'Ihre Daten werden sicher verarbeitet.',
                    rs_patientId: 'Patientenkennung',
                    rs_checkinAuth: 'CHECK-IN ERLAUBNIS'
                },
                tr: {
                    topbarLang: 'TR',
                    wl_whatLabel: 'VitalNavAI nedir?',
                    wl_whatDesc: 'Tıbbi bir acil durumda <strong>VitalNavAI</strong> yapay zekayı şunlar için kullanır:',
                    wl_b1: 'Sizi ve hastaneyi durumunuz hakkında <strong>varmadan önce</strong> bilgilendirmek',
                    wl_b2: 'Acil servisteki <strong>bekleme sürenizi</strong> en aza indirmek',
                    wl_b3: 'Sizi <strong>en uygun yakın hastaneye</strong> yönlendirmek',
                    wl_howLabel: 'Nasıl kullanılır',
                    wl_s1: '<strong style="color:var(--navy)">🎤 Konuşun</strong> — belirtilerinizi kendi kelimelerinizle açıkça anlatın.',
                    wl_s2: '<strong style="color:var(--navy)">❓ Sorular</strong> — birkaç kısa takip sorusunu yanıtlayın.',
                    wl_s3: '<strong style="color:var(--navy)">🏥 Hastane</strong> — en uygun hastane seçilir ve bilgilendirilir.',
                    wl_demo: "Yalnızca demo. Gerçek acillerde 112'yi arayın.",
                    wl_hnLabel: 'Sağlık kaydınızı seçin', wl_hnReq: 'ZORUNLU',
                    wl_hnHintText: 'Tıbbi geçmişiniz bu ziyaretle ilişkilendirilecek',
                    btnStart: 'Başlayın →',
                    inp_title: 'Rahatsızlığınızı anlatın',
                    inp_sub: 'Sesli olarak anlatın veya rahatsızlığınızı seçin.',
                    inp_orSelect: 'Veya rahatsızlığınızı seçin',
                    micStatus: 'Dokunun ve Konuşun',
                    sym_chest_pain: 'Göğüs Ağrısı',
                    sym_shortness_breath: 'Nefes Darlığı',
                    sym_headache: 'Şiddetli Baş Ağrısı',
                    sym_fever: 'Yüksek Ateş',
                    sym_dizziness: 'Baş Dönmesi',
                    sym_abdominal_pain: 'Karın Ağrısı',
                    sym_fainting: 'Bayılma',
                    sym_severe_bleeding: 'Durdurulamayan Kanama',
                    sym_allergic_reaction: 'Şiddetli Alerjik Reaksiyon',
                    sym_vomiting_diarrhea: 'Sürekli Kusma veya İshal',
                    sym_numbness_weakness: 'Uyuşma veya Güçsüzlük',
                    sym_altered_consciousness: 'Bilinç Değişikliği',
                    micLabelRec: 'Dinleniyor...',
                    micSubRec: 'Durdurmak için dokunun',
                    micLabelDone: 'Kaydedildi',
                    micSubDone: 'Yeniden kaydetmek için dokunun',
                    transcriptLang: 'Ses Metne Dönüştürme',
                    inputSpinnerText: 'Ses işleniyor...',
                    inp_continueTxt: 'Analizi Başlat',
                    inp_examples: ['Göğüs ağrısı', 'Nefes darlığı', 'Şiddetli baş ağrısı', 'Yüksek ateş', 'Baş dönmesi', 'Karın ağrısı', 'Bulantı / kusma', 'Bacak şişliği', 'Sırt ağrısı', 'Bayılma', 'Çarpıntı', 'Alerjik reaksiyon'],
                    ph_title: 'Fotoğraf veya video ekleyin',
                    ph_sub: '<span style="color: var(--primary); font-weight: 900; text-transform: uppercase; font-size: 0.85rem; letter-spacing: 1px; background: rgba(10,132,255,0.1); padding: 4px 10px; border-radius: 8px;">İsteğe Bağlı</span><br><span style="font-size: 1.05rem; color: var(--text-2); line-height: 1.5; display: block; margin-top: 12px;">Görünür bir yara, döküntü, şişlik varsa veya kısa bir video durumunuzu daha iyi açıklayacaksa lütfen yükleyin. Bu, sağlık ekibinin siz gelmeden önce hazırlık yapmasına yardımcı olur.</span>',
                    ph_continueTxt: 'Devam Et',
                    ph_addPhoto: 'Fotoğraf', ph_addVideo: 'Video', ph_skip: 'Atla →',
                    questionsIntro: 'Durumunuzu daha iyi değerlendirebilmem için sonraki kısımdaki kısa sorulara lütfen cevap verin.\n\nYapay zeka tarafından sorular oluşturuluyor, lütfen bekleyin…',
                    questionsSpinnerText: 'Sorular oluşturuluyor…',
                    aiMode_real: '🤖 Yapay zeka soruları', aiMode_mock: '⚠️ Demo modu — YZ çevrimdışı',
                    fq_onset: 'Şikayetleriniz ne zaman başladı?',
                    fq_onset_now: 'Az önce (< 15 dk)', fq_onset_1h: 'Son bir saat içinde', fq_onset_6h: '1–6 saat önce', fq_onset_24h: '6–24 saat önce', fq_onset_days: 'Bir günden fazla önce',
                    fq_pain_scale: 'Ağrınızı 1-10 skalasında nasıl değerlendirirsiniz?',
                    fq_breathing: 'Şu anda nefes almakta güçlük çekiyor musunuz?', fq_fever: 'Yaklaşık ateşiniz nedir?',
                    fq_nausea: 'Bulantı veya kusma yaşıyor musunuz?', fq_conditions: 'Bilinen bir kronik hastalığınız var mı?',
                    fq_cond_none: 'Yok', fq_cond_heart: 'Kalp hastalığı', fq_cond_diab: 'Diyabet', fq_cond_bp: 'Yüksek tansiyon', fq_cond_other: 'Diğer',
                    fq_medications: 'Şu anda herhangi bir ilaç kullanıyor musunuz?', fq_allergies: 'Bilinen ilaç alerjiniz var mı?',
                    fq_yes: 'Evet', fq_no: 'Hayır', fq_unsure: 'Emin değilim',
                    q_back: 'Geri', q_next: 'İleri', q_of: '/', q_done: 'Bitti →',
                    cs_title: 'Neredeyse bitti', cs_sub: 'Hastaneyle paylaşılacakları inceleyin',
                    cs_consentLabel: 'Veri paylaşım onayı',
                    cs_consentDesc: 'Aşağıdaki bilgileri hastaneyle paylaşmayı onaylıyor musunuz?',
                    cs_line1: 'Semptom açıklaması ve soru yanıtları', cs_photoLine: 'Medya: {n} dosya eklendi',
                    cs_line3: 'Yapay zeka triaj değerlendirmesi ve risk düzeyi', cs_line4: 'Gerçek zamanlı konum (canlı takip)',
                    cs_yes: '✅ Evet — bilgilerimi paylaş', cs_no: '❌ Hayır — paylaşma',
                    consentWarning: 'Devam etmek için onay vermelisiniz.',
                    assessSpinnerText: 'Semptomlarınız yapay zeka ile analiz ediliyor…', cs_btnTxt: 'Değerlendirmemi al →',
                    cs_secureText: 'Verileriniz güvenli bir şekilde işlenmektedir.',
                    gps_waitTitle: 'Konumunuz algılanıyor…', gps_waitSub: "Tarayıcınız sorduğunda <strong>İzin Ver</strong>'e dokunun.",
                    gps_deniedTitle: '🔒 Konum erişimi gerekli', gps_deniedDesc: 'En yakın hastaneyi bulmak için konumunuza ihtiyacımız var.',
                    gps_deniedSteps: "① Adres çubuğundaki 🔒 simgesine dokunun<br>② Site ayarları → Konum → <strong>İzin Ver</strong><br>③ Geri dönün ve Yeniden Dene'ye dokunun",
                    gps_retryBtn: '🔄 Yeniden dene',
                    gpsDetecting: 'Konum algılanıyor…', gpsOk: 'Konum doğrulandı', gpsDenied: 'Konum reddedildi',
                    tr_nearestLabel: 'Mevcut <strong>trafik</strong> durumu ve hastane acillerinin <strong>yoğunluk</strong> durumuna göre tavsiye edilen hastaneler',
                    tr_adviceLabel: 'Varmadan önce', tr_fastest: '⭐ En iyi seçim',
                    tr_hospSpinner: 'En uygun hastaneler aranıyor…', tr_noHosp: 'Yakında hastane bulunamadı.', tr_notifying: 'Hastane bilgilendiriliyor…',
                    tr_emg_title: '🚨 Hemen acile gidin', tr_emg_sub: 'Semptomlarınız acil bakım gerektiriyor — beklemeyin',
                    tr_urg_title: '⚠️ En kısa sürede hastaneye gitmelisiniz', tr_urg_sub: 'Lütfen 30 dakika içinde bir hastane bulun',
                    tr_rtn_title: 'ℹ️ Bugün bir doktora görünün', tr_rtn_sub: 'Semptomlarınız hemen hayati tehlike oluşturmuyor',
                    tr_orBelow: '— veya aşağıdan hastane seçin —', tr_doLabel: '✅ YAPILACAKLAR:', tr_dontLabel: '❌ YAPILMAYACAKLAR:',
                    rs_regLabel: 'Kayıt numaranız', rs_regHint: 'Varışta hastane resepsiyonunda gösterin.',
                    rs_notified_emg: '🚨 Hastane bildirildi — hemen yola çıkın!', rs_notified_sub_emg: 'Geliişinize hazırlanıyorlar',
                    rs_notified_urg: '✅ Hastane bilgilendirildi', rs_notified_sub_urg: 'Lütfen aşağıdaki talimatları izleyin',
                    rs_notified_rtn: '✅ Bilgileriniz gönderildi', rs_notified_sub_rtn: 'Ayrılmadan önce talimatları okuyun',
                    rs_trackTitle: 'Yolculuk sırasında konumu açık bırakın', rs_trackSub: 'Bakım ekibiniz varışınızı gerçek zamanlı takip eder.',
                    rs_newBtn: 'Yeni değerlendirme',
                    rs_passFooter: 'Varışta bu kartı görevliye gösterin veya girişteki cihaza QR kodunuzu okutun.',
                    rs_tab_status: 'Aksiyon',
                    rs_tab_instructions: 'Yolculuk',
                    rs_tab_contact: 'Varış',
                    rs_openNav: 'Navigasyonu Aç', rs_liveTrackingTitle: 'CANLI TAKİP AKTİF', rs_liveTrackingSub: 'Sağlık ekibi varışınızı GPS ile izliyor.', rs_passFooter: 'Varışta bu kartı görevliye gösterin veya girişteki cihaza QR kodunuzu okutun.',
                    wl_langHeroSub: 'YZ Acil Asistanı', inp_backBtn: 'Geri', ph_backBtn: 'Geri', gps_privacyText: 'Konumunuz yalnızca en uygun hastaneyi bulmak için kullanılmaktadır. Kimliğiniz gizli tutulmaktadır.', rs_contactTitle: 'Bu bilgiler kayıtlı ACİL kişinize gönderilecek', rs_contactDesc: 'Acil kişinize şunlar gönderilecek:', rs_contactItem1: 'Triyaj durumunuz ve kayıt numarası', rs_contactItem2: 'Atanan hastane adı ve adresi', rs_contactItem3: 'Mevcut konumunuz (tek seferlik)', rs_contactSendBtn: 'Bildirimi gönder', rs_demo: "⚠️ Yalnızca demo. Gerçek acillerde 112'yi arayın.",
                    aiChecking: 'Yapay zeka durumu kontrol ediliyor…', aiConnected: '🤖 Yapay zeka bağlı — gerçek zamanlı analiz', aiDemo: '⚙️ Demo modu — YZ yapılandırılmamış',
                    adv_call112: "Hemen 112'yi arayın veya birine aratın", adv_sit_still: 'Oturun ya da uzanın ve hareket etmeyin', adv_stay_calm: 'Sakin olun ve yavaş nefes alın', adv_rest: 'Dinlenin ve fiziksel efordan kaçının', adv_someone_with_you: 'Hastaneye birinin eşliğinde gidin', adv_bring_meds: 'Kullandığınız tüm ilaçları yanınıza alın', adv_bring_id: 'Kimliğinizi ve sigorta kartınızı getirin', adv_no_drive: 'Hastaneye KENDİNİZ araba kullanarak gitmeyin', adv_no_eat: 'Muayene edilene kadar hiçbir şey yemeyin ya da içmeyin', adv_chest_loose: 'Göğsünüzün etrafındaki dar giysileri gevşetin', adv_chest_no_stress: 'Fiziksel veya duygusal stresten kaçının', adv_bleed_pressure: 'Temiz bir bezle yaraya sıkıca bastırın', adv_bleed_no_remove: 'Yaraya saplanmış bir nesneyi çıkarmayın', adv_breath_upright: 'Dik oturun — yatmayın', adv_breath_no_lie: 'Düz yatmayın — solunumu kötüleştirir', adv_head_dark: 'Mümkünse sakin, karanlık bir odada dinlenin', adv_head_no_screen: 'Ekranlardan, parlak ışıktan ve gürültüden kaçının', adv_proceed_er: 'En kısa sürede acil servise gidin',
                    hnPlaceholder: 'Sağlık kaydınızı seçin…',
                    tr_aiRoutingTitle: 'Akıllı Yönlendirme',
                    tr_aiRoutingSub: 'Gerçek zamanlı verilere dayanarak en uygun hastaneyi belirliyoruz.',
                    tr_liveTraffic: 'Trafik',
                    tr_erCapacity: 'Acil Yoğunluğu',
                    tr_selectHospital: 'Önerilen Hastanelerden Birini Seçin',
                    tr_traffic_clear: 'Açık', tr_traffic_medium: 'Yoğun', tr_traffic_heavy: 'Çok Yoğun',
                    tr_er_low: 'Az', tr_er_medium: 'Orta', tr_er_high: 'Fazla', tr_er_full: 'Dolu',
                    wl_system_notice: 'Bu sistem tıbbi öncelikleri belirlemek amacıyla geliştirilmiştir.',
                    cs_data_secure: 'Verileriniz güvenli bir şekilde işlenmektedir.',
                    rs_patientId: 'Hasta Kimlik Numarası',
                    rs_checkinAuth: 'GİRİŞ YETKİSİ'
                },
            };

            // ═══════════════════════════════════════════════════════════
            // STATE
            // ═══════════════════════════════════════════════════════════
            const S = {
                lang: 'en', complaint: '', complaintEN: '', detectedLang: 'en-GB',
                selectedLang: null, photos: [], questions: [], answers: [], qIdx: 0,
                aiMode: null, dataConsent: null, assessment: null,
                lat: null, lon: null, country: 'DE', hospitals: [], selectedHospital: null,
                regNumber: null, healthNumber: null,
            };

            // ═══════════════════════════════════════════════════════════
            // LANG HELPERS
            // ═══════════════════════════════════════════════════════════
            function t(key, vars) {
                let s = (TX[S.lang] || TX.en)[key] || TX.en[key] || key;
                if (vars) Object.keys(vars).forEach(k => { s = s.replace('{' + k + '}', vars[k]); });
                return s;
            }

            function applyLang() {
                const lb = document.getElementById('topbarLangBadge');
                lb.textContent = t('topbarLang'); lb.style.display = '';

                // innerHTML elements
                ['wl_whatLabel', 'wl_whatDesc', 'wl_b1', 'wl_b2', 'wl_b3', 'wl_howLabel', 'wl_s1', 'wl_s2', 'wl_s3', 'wl_demo',
                    'cs_title', 'cs_sub', 'cs_consentLabel', 'cs_consentDesc', 'cs_line1', 'cs_line3', 'cs_line4', 'cs_yes', 'cs_no',
                    'assessSpinnerText', 'cs_btnTxt', 'gps_waitTitle', 'gps_waitSub', 'gps_deniedTitle', 'gps_deniedDesc',
                    'gps_deniedSteps', 'gps_retryBtn', 'tr_nearestLabel', 'tr_adviceLabel', 'rs_regLabel', 'rs_regHint',
                    'rs_trackTitle', 'rs_trackSub', 'rs_newBtn', 'rs_demo', 'ph_sub'].forEach(id => {
                        const el = document.getElementById(id); if (el) el.innerHTML = t(id);
                    });

                // Text content elements (Added wl_system_notice here)
                ['inp_title', 'inp_sub', 'inp_orSelect', 'inp_continueTxt', 'micStatus', 'micSub', 'inputSpinnerText', 'ph_title',
                    'ph_addPhoto', 'ph_addVideo', 'ph_continueTxt', 'wl_hnLabel', 'wl_hnReq',
                    'wl_hnHintText', 'btnStart', 'wl_langHeroSub', 'gps_privacy', 'rs_prelimNotice',
                    'rs_contactTitle', 'rs_contactDesc', 'rs_contactItem1', 'rs_contactItem2', 'rs_contactItem3',
                    'rs_contactSendBtn', 'cs_secureText',
                    'tr_aiRoutingTitle', 'tr_aiRoutingSub', 'tr_liveTraffic', 'tr_erCapacity', 'tr_selectHospital',
                    'wl_system_notice', 'cs_data_secure'
                ].forEach(id => {
                    const el = document.getElementById(id); if (el) el.textContent = t(id);
                });

                const gpsPri = document.getElementById('gps_privacy'); if (gpsPri) gpsPri.textContent = t('gps_privacyText');
                const ct = document.getElementById('complaintText'); if (ct) ct.placeholder = t('inp_placeholder');
                const ml = document.getElementById('micLabel'); if (ml) ml.textContent = t('micLabelIdle');
                const qst = document.getElementById('questionsSpinnerText'); if (qst) qst.textContent = t('questionsSpinnerText');
                const qi = document.getElementById('qIntroText'); if (qi) qi.innerHTML = t('questionsIntro').replace(/\n/g, '<br><br>');
                renderHnDropdown();
                const sp = document.getElementById('hnSelectVal');
                if (sp && sp.dataset.placeholder === 'true') { sp.textContent = t('hnPlaceholder'); sp.classList.add('placeholder'); }

                renderExampleChips();
                updateConsentPage();

                // FIX: Re-render symptom grid when language changes
                renderSymptoms();

                const qb = document.getElementById('q_back'); if (qb) qb.textContent = t('q_back');
                const qn = document.getElementById('q_next'); if (qn) qn.textContent = t('q_next');
            }

            function selectLanguage(lang) {
                S.lang = lang;
                const map = { en: 'en-GB', de: 'de-DE', tr: 'tr-TR' };
                S.detectedLang = map[lang] || 'en-GB';
                S.selectedLang = S.detectedLang;
                S.healthNumber = null;

                ['en', 'de', 'tr'].forEach(l => {
                    const btn = document.getElementById('langBtn_' + l);
                    if (btn) btn.classList.toggle('selected', l === lang);
                });

                applyLang();

                if (!S.healthNumber) {
                    const sp = document.getElementById('hnSelectBtn');
                    if (sp) {
                        sp.style.borderColor = 'var(--danger)'; sp.style.boxShadow = '0 0 0 3px rgba(220,38,38,.15)';
                        setTimeout(() => { sp.style.borderColor = ''; sp.style.boxShadow = ''; }, 2000);
                    }
                    const warn = {
                        en: 'Please select your health record to continue.',
                        de: 'Bitte wählen Sie Ihre Krankenakte aus.',
                        tr: 'Devam etmek için sağlık kaydınızı seçin.'
                    };
                    toast(warn[lang] || warn.en, 'warn');
                    // Deselect lang button
                    const btn = document.getElementById('langBtn_' + lang);
                    if (btn) btn.classList.remove('selected');
                    return;
                }

                setTimeout(() => {
                    document.getElementById('page-lang').classList.remove('active');
                    goToPage('chat');
                    checkAIStatus();
                }, 400);
            }

            // ═══════════════════════════════════════════════════════════
            // HEALTH NUMBER DROPDOWN
            // ═══════════════════════════════════════════════════════════
            function renderHnDropdown() {
                const dd = document.getElementById('hnDropdown');
                const patients = DEMO_PATIENTS[S.lang] || DEMO_PATIENTS.en;
                dd.innerHTML = patients.map(p => `
    <div class="hn-item" onclick="selectHn('${p.id}','${escHtml(p.name)}')">
      <span class="hn-item-num">${p.id}</span>
      <div><div class="hn-item-name">${escHtml(p.name)}</div><div class="hn-item-detail">${escHtml(p.detail)}</div></div>
    </div>`).join('');
            }
            function toggleHnDropdown() {
                const dd = document.getElementById('hnDropdown');
                const btn = document.getElementById('hnSelectBtn');
                const open = dd.classList.toggle('open');
                btn.classList.toggle('open', open);
            }
            function selectHn(id, name) {
                S.healthNumber = id;
                const val = document.getElementById('hnSelectVal');
                val.textContent = `${id} — ${name}`;
                val.classList.remove('placeholder');
                val.dataset.placeholder = 'false';
                document.getElementById('hnDropdown').classList.remove('open');
                document.getElementById('hnSelectBtn').classList.remove('open');
            }
            document.addEventListener('click', e => {
                if (!e.target.closest('.hn-wrap')) {
                    document.getElementById('hnDropdown')?.classList.remove('open');
                    document.getElementById('hnSelectBtn')?.classList.remove('open');
                }
            });

            // ═══════════════════════════════════════════════════════════
            // EXAMPLE CHIPS (multi-selectable)
            // ═══════════════════════════════════════════════════════════
            const _selectedChips = new Set();
            function renderExampleChips() {
                const chips = document.getElementById('exampleChips');
                const examples = t('inp_examples');
                if (!chips || !Array.isArray(examples)) return;
                _selectedChips.clear();
                chips.innerHTML = examples.map(ex =>
                    `<span class="complaint-chip" id="chip_${ex.replace(/\s/g, '_')}" onclick="toggleChip('${escHtml(ex)}')">${escHtml(ex)}</span>`
                ).join('');
            }
            function toggleChip(text) {
                const id = 'chip_' + text.replace(/\s/g, '_');
                const el = document.getElementById(id);
                if (_selectedChips.has(text)) {
                    _selectedChips.delete(text);
                    if (el) el.classList.remove('selected');
                } else {
                    _selectedChips.add(text);
                    if (el) el.classList.add('selected');
                }
                if (_selectedChips.size > 0) {
                    const combined = Array.from(_selectedChips).join(', ');
                    S.complaint = combined;
                    document.getElementById('complaintText').value = '';
                    document.getElementById('transcriptText').textContent = combined;
                    document.getElementById('transcriptBox').classList.add('visible');
                    enableContinue(true);
                } else {
                    S.complaint = document.getElementById('complaintText').value.trim() || '';
                    document.getElementById('transcriptBox').classList.remove('visible');
                    enableContinue(!!S.complaint);
                }
            }
            function useExample(text) {
                const ta = document.getElementById('complaintText');
                ta.value = text; S.complaint = text;
                document.getElementById('transcriptBox').classList.remove('visible');
                enableContinue(true); ta.focus();
            }

            // ═══════════════════════════════════════════════════════════
            // NAVIGATION
            // ═══════════════════════════════════════════════════════════
            const STEP_MAP = { lang: 0, chat: 1, consent: 2, triage: 3, result: 4 };
            function goToPage(name) {
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                const el = document.getElementById('page-' + name); if (el) el.classList.add('active');
                S.currentPage = name;
                const idx = STEP_MAP[name] ?? -1;
                for (let i = 0; i < 5; i++) {
                    const s = document.getElementById('ps' + i); if (!s) continue;
                    s.className = 'progress-step';
                    if (i < idx) s.classList.add('done');
                    else if (i === idx) s.classList.add('active');
                }
                window.scrollTo(0, 0);
                lucide.createIcons();
            }

            function startApp() {
                if (!S.healthNumber) {
                    const sp = document.getElementById('hnSelectBtn');
                    if (sp) {
                        sp.style.borderColor = 'var(--red)'; sp.style.boxShadow = '0 0 0 3px rgba(239,68,68,.15)';
                        setTimeout(() => { sp.style.borderColor = ''; sp.style.boxShadow = ''; }, 2000);
                    }
                    const warn = {
                        en: 'Please select your health record to continue.',
                        de: 'Bitte wählen Sie Ihre Krankenakte aus, um fortzufahren.',
                        tr: 'Devam etmek için lütfen sağlık kaydınızı seçin.'
                    };
                    toast(warn[S.lang] || warn.en, 'warn'); return;
                }
                goToPage('chat');
            }

            function startOver() {
                Object.assign(S, {
                    complaint: '', complaintEN: '', detectedLang: S.selectedLang || 'en-GB', photos: [],
                    questions: [], answers: [], qIdx: 0, dataConsent: null, assessment: null, lat: null, lon: null,
                    hospitals: [], selectedHospital: null, regNumber: null, aiMode: null
                });
                const ct = document.getElementById('complaintText'); if (ct) ct.value = '';
                document.getElementById('transcriptBox').classList.remove('visible');
                enableContinue(false);
                document.getElementById('mediaGrid').innerHTML = '';
                updateMediaCount();
                document.getElementById('mediaAddRow').style.display = '';
                document.getElementById('photoInput').value = '';
                document.getElementById('videoInput').value = '';
                goToPage('chat');
            }

            // ═══════════════════════════════════════════════════════════
            // AI STATUS
            // ═══════════════════════════════════════════════════════════
            async function checkAIStatus() {
                const dot = document.getElementById('aiDot'), txt = document.getElementById('aiStatusText');
                txt.textContent = t('aiChecking'); dot.style.background = 'var(--s300)';
                try {
                    const r = await fetch(API + '/api/patient/questions', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ complaint: '__health_check__', detected_language: 'en-US' })
                    });
                    if (r.ok) { S.aiMode = 'real'; dot.style.background = 'var(--green)'; txt.textContent = t('aiConnected'); }
                    else throw new Error();
                } catch (e) { S.aiMode = 'mock'; dot.style.background = 'var(--orange)'; txt.textContent = t('aiDemo'); }
            }

            // ═══════════════════════════════════════════════════════════
            // MIC RECORDING
            // ═══════════════════════════════════════════════════════════
            let mediaRec = null, audioChunks = [], isRecording = false;
            let webSpeechRec = null, webSpeechResult = '';

            async function toggleRecording() {
                if (isRecording) {
                    stopRecording();
                } else {
                    await startRecording();
                }
            }

            function startWebSpeech(langCode) {
                const SR = window.SpeechRecognition || window.webkitSpeechRecognition; if (!SR) return;
                webSpeechRec = new SR();
                webSpeechRec.continuous = true; webSpeechRec.interimResults = true;
                webSpeechRec.lang = langCode || 'tr-TR';
                // Do NOT reset webSpeechResult here — keep any previous result until confirmed done
                webSpeechRec.onresult = e => {
                    let interim = '', final = '';
                    for (let i = 0; i < e.results.length; i++) {
                        if (e.results[i].isFinal) final += e.results[i][0].transcript + ' ';
                        else interim += e.results[i][0].transcript;
                    }
                    // Update result: prefer final, fall back to interim display
                    if (final.trim()) webSpeechResult = final.trim();
                    const display = (final || interim).trim();
                    if (display) {
                        document.getElementById('transcriptText').textContent = display;
                        document.getElementById('transcriptBox').classList.add('visible');
                        document.getElementById('transcriptLang').textContent = '🎤 ' + t('micLabelRec');
                    }
                };
                webSpeechRec.onerror = e => {
                    // 'no-speech' and 'aborted' are normal — don't clear result
                    if (e.error !== 'no-speech' && e.error !== 'aborted') {
                        console.warn('Web Speech error:', e.error);
                    }
                };
                webSpeechRec.onend = () => {
                    // Auto-restart if still recording (some browsers stop after silence)
                    if (isRecording && webSpeechRec === null) return; // manually stopped
                    if (isRecording) {
                        try { webSpeechRec.start(); } catch (_) { }
                    }
                };
                try { webSpeechRec.start(); } catch (e) { console.warn('WebSpeech start failed:', e); }
            }
            function stopWebSpeech() {
                if (webSpeechRec) {
                    const r = webSpeechRec;
                    webSpeechRec = null; // set null first so onend doesn't restart
                    try { r.stop(); } catch (e) { }
                }
            }

            async function startRecording() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRec = new MediaRecorder(stream); audioChunks = [];
                    mediaRec.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
                    mediaRec.onstop = processAudio; mediaRec.start(100); isRecording = true;
                    startWebSpeech(S.selectedLang || S.detectedLang || 'tr-TR');
                    setMicState('recording');
                } catch (e) {
                    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
                    if (SR) { isRecording = true; startWebSpeech(S.selectedLang || S.detectedLang || 'tr-TR'); setMicState('recording'); return; }
                    const msgs = {
                        NotAllowedError: { en: 'Microphone access denied.', de: 'Mikrofonzugriff verweigert.', tr: 'Mikrofon erişimi reddedildi.' },
                        NotFoundError: { en: 'No microphone found.', de: 'Kein Mikrofon gefunden.', tr: 'Mikrofon bulunamadı.' },
                        NotReadableError: { en: 'Microphone is used by another app.', de: 'Mikrofon wird verwendet.', tr: 'Mikrofon başka uygulama tarafından kullanılıyor.' }
                    };
                    const m = msgs[e.name] || { en: 'Microphone unavailable — please type.', de: 'Mikrofon nicht verfügbar.', tr: 'Mikrofon kullanılamıyor — lütfen yazın.' };
                    toast(m[S.lang] || m.en, 'warn');
                }
            }
            function stopRecording() {
                // Snapshot Web Speech result BEFORE stopping (prevents race condition)
                const wsr = webSpeechResult;

                // Stop Web Speech first, then give it 400ms to fire final onresult
                if (webSpeechRec) { try { webSpeechRec.stop(); } catch (e) { } webSpeechRec = null; }

                if (mediaRec && mediaRec.state !== 'inactive') {
                    // mediaRec.onstop → processAudio handles the rest
                    mediaRec.stop();
                    mediaRec.stream.getTracks().forEach(tr => tr.stop());
                } else if (isRecording && !mediaRec) {
                    // Web Speech only mode (no MediaRecorder)
                    isRecording = false; setMicState('idle');
                    // Wait briefly for any final Web Speech result
                    setTimeout(() => {
                        const finalResult = (webSpeechResult || wsr || '').trim();
                        if (finalResult) { setComplaintFromAudio(finalResult, S.selectedLang || S.detectedLang); }
                        else { const m = { en: 'No audio captured — please type.', de: 'Keine Aufnahme.', tr: 'Ses alınamadı — lütfen yazın.' }; toast(m[S.lang] || m.en, 'warn'); }
                        webSpeechResult = '';
                    }, 400);
                    return;
                }
                isRecording = false; setMicState('idle');
            }
            function setMicState(state) {
                const wf = document.getElementById('waveformBars');
                const btn = document.getElementById('micBtn');
                const statusTxt = document.getElementById('micStatus');
                const subTxt = document.querySelector('#voiceUI div div:last-child'); // Alt metin

                if (state === 'recording') {
                    if (wf) wf.style.display = 'flex';
                    if (btn) btn.classList.add('recording');
                    if (statusTxt) statusTxt.textContent = t('micLabelRec');
                    if (subTxt) subTxt.textContent = t('micSubRec');
                } else {
                    if (wf) wf.style.display = 'none';
                    if (btn) btn.classList.remove('recording');
                    // Eğer şikayet varsa "Tekrar kaydedin", yoksa "Dokun ve Konuş" yazsın
                    if (statusTxt) statusTxt.textContent = S.complaint ? t('micLabelDone') : t('micLabelIdle');
                }
            }
            async function processAudio() {
                await new Promise(r => setTimeout(r, 350));
                const wsr = (webSpeechResult || '').trim();
                const blob = new Blob(audioChunks, { type: 'audio/webm;codecs=opus' });

                const spinner = document.getElementById('inputSpinner');
                const spinnerText = document.getElementById('inputSpinnerText');

                if (spinner) spinner.classList.add('visible');

                const procMessages = { en: 'Processing audio…', de: 'Audio wird verarbeitet…', tr: 'Ses işleniyor…' };
                if (spinnerText) spinnerText.textContent = procMessages[S.lang] || procMessages.en;

                try {
                    if (blob.size > 500) {
                        const form = new FormData();
                        form.append('audio', blob, 'complaint.webm');

                        const r = await fetch(API + '/api/patient/transcribe', { method: 'POST', body: form });
                        const d = await r.json();

                        if (d.text && d.text.trim()) {
                            S.detectedLang = d.language || S.selectedLang || 'en-GB';
                            setComplaintFromAudio(d.text.trim(), d.language);
                            webSpeechResult = '';
                            return;
                        }
                    }

                    if (wsr) {
                        setComplaintFromAudio(wsr, S.selectedLang || S.detectedLang);
                        webSpeechResult = '';
                    } else {
                        const m = { en: 'Could not understand audio — please type.', de: 'Audio nicht verstanden.', tr: 'Ses anlaşılamadı — lütfen yazın.' };
                        toast(m[S.lang] || m.en, 'warn');
                        setMicState('idle');
                    }
                } catch (e) {
                    console.error("Transcription Error:", e);
                    if (wsr) {
                        setComplaintFromAudio(wsr, S.selectedLang || S.detectedLang);
                    } else {
                        const m = { en: 'Network error — please type.', de: 'Netzwerkfehler.', tr: 'Bağlantı hatası — lütfen yazın.' };
                        toast(m[S.lang] || m.en, 'warn');
                        setMicState('idle');
                    }
                } finally {
                    if (spinner) spinner.classList.remove('visible');
                }
            }

            const LANG_NAMES = { 'en-US': 'English', 'en-GB': 'English', 'de-DE': 'Deutsch', 'tr-TR': 'Türkçe', 'ar-SA': 'العربية', 'fr-FR': 'Français', 'es-ES': 'Español', 'it-IT': 'Italiano' };

            function setComplaintFromAudio(text, langCode) {
                if (!text || text.trim().length === 0) return;

                S.voiceTranscript = text.trim();

                updateFinalComplaint();

                const tText = document.getElementById('transcriptText');
                const tBox = document.getElementById('transcriptBox');
                const tLang = document.getElementById('transcriptLang');

                if (tText) tText.textContent = `"${S.voiceTranscript}"`;
                if (tBox) tBox.style.display = 'block';
                if (tLang) tLang.textContent = '✓ ' + t('transcriptLang');

                enableContinue(true);
                setMicState('idle');
            }

            function updateFinalComplaint() {
                const selectedNodes = document.querySelectorAll('.symptom-card.selected');
                const selectedTexts = Array.from(selectedNodes).map(node => node.textContent.trim());

                let combined = S.voiceTranscript || "";
                if (selectedTexts.length > 0) {
                    combined += (combined ? ", " : "") + selectedTexts.join(', ');
                }
                S.complaint = combined;
            }

            function onComplaintType() {
                const val = document.getElementById('complaintText').value.trim();
                if (val) { S.complaint = val; document.getElementById('transcriptBox').classList.remove('visible'); }
                enableContinue(!!(val || S.complaint));
            }

            function enableContinue(on) {
                const btn = document.getElementById('btnContinueInput');
                btn.disabled = !on; btn.style.opacity = on ? '1' : '0.45';
            }

            function submitComplaint() {
                if (!S.complaint.trim()) return;
                S.photos = []; S.questions = []; S.answers = []; S.qIdx = 0; S.dataConsent = null; S.assessment = null;
                document.getElementById('mediaGrid').innerHTML = ''; updateMediaCount();
                document.getElementById('mediaAddRow').style.display = '';
                goToPage('photos');
            }

            // ═══════════════════════════════════════════════════════════
            // MEDIA
            // ═══════════════════════════════════════════════════════════
            function onMediaAdded(evt, type) {
                const file = evt.target.files[0]; if (!file) return;
                const reader = new FileReader();
                reader.onload = e => {
                    if (S.photos.length >= 3) return;
                    S.photos.push({ dataUrl: e.target.result, mime: file.type, type });
                    renderMediaGrid();
                };
                reader.readAsDataURL(file); evt.target.value = '';
            }
            function removeMedia(idx) { S.photos.splice(idx, 1); renderMediaGrid(); }
            function renderMediaGrid() {
                document.getElementById('mediaGrid').innerHTML = S.photos.map((m, i) => {
                    const isVid = m.type === 'video' || m.mime?.startsWith('video/');
                    return `<div class="media-thumb">
      ${isVid ? `<video src="${m.dataUrl}" style="width:100%;height:100%;object-fit:cover"></video><span class="vid-badge">VIDEO</span>`
                            : `<img src="${m.dataUrl}" alt="">`}
      <button class="remove" onclick="removeMedia(${i})">✕</button>
    </div>`;
                }).join('');
                updateMediaCount();
                document.getElementById('mediaAddRow').style.display = S.photos.length >= 3 ? 'none' : '';
            }
            function updateMediaCount() { document.getElementById('mediaCount').textContent = `${S.photos.length} / 3`; }
            function skipPhotos() { loadQuestions(); }
            function continueFromPhotos() { loadQuestions(); }

            // ═══════════════════════════════════════════════════════════
            // FALLBACK QUESTIONS
            // ═══════════════════════════════════════════════════════════
            function generateFallbackQuestions(complaint) {
                const c = complaint.toLowerCase(); const qs = [];
                qs.push({ question: t('fq_onset'), type: 'multiple_choice', options: [t('fq_onset_now'), t('fq_onset_1h'), t('fq_onset_6h'), t('fq_onset_24h'), t('fq_onset_days')] });
                if (/pain|ache|hurt|ağrı|schmerz/i.test(c)) qs.push({ question: t('fq_pain_scale'), type: 'scale', options: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'] });
                if (/breath|chest|lung|nefes|göğüs|atemlos|brust/i.test(c)) qs.push({ question: t('fq_breathing'), type: 'yes_no', options: [t('fq_yes'), t('fq_no'), t('fq_unsure')] });
                if (/fever|ateş|fieber/i.test(c)) qs.push({ question: t('fq_fever'), type: 'multiple_choice', options: ['< 37.5°C', '37.5–38.5°C', '38.5–39.5°C', '> 39.5°C', t('fq_unsure')] });
                if (/nause|vomit|dizzy|headache|baş|kopf|kusm/i.test(c)) qs.push({ question: t('fq_nausea'), type: 'yes_no', options: [t('fq_yes'), t('fq_no'), t('fq_unsure')] });
                qs.push({ question: t('fq_conditions'), type: 'multiple_choice', options: [t('fq_cond_none'), t('fq_cond_heart'), t('fq_cond_diab'), t('fq_cond_bp'), t('fq_cond_other')] });
                qs.push({ question: t('fq_medications'), type: 'yes_no', options: [t('fq_yes'), t('fq_no'), t('fq_unsure')] });
                qs.push({ question: t('fq_allergies'), type: 'yes_no', options: [t('fq_yes'), t('fq_no'), t('fq_unsure')] });
                return qs;
            }

            // ═══════════════════════════════════════════════════════════
            // LOAD QUESTIONS
            // ═══════════════════════════════════════════════════════════
            async function loadQuestions() {
                goToPage('questions');
                document.getElementById('questionsSpinner').classList.add('visible');
                document.getElementById('questionsContainer').style.display = 'none';
                document.getElementById('questionNav').style.display = 'none';
                document.getElementById('aiModeBadge').style.display = 'none';
                document.getElementById('qIntroCard').style.display = 'block';
                const qi = document.getElementById('qIntroText');
                if (qi) qi.innerHTML = t('questionsIntro').replace(/\n/g, '<br><br>');
                try {
                    const r = await fetch(API + '/api/patient/questions', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ complaint: S.complaint, complaint_en: S.complaintEN, detected_language: S.detectedLang })
                    });
                    const d = await r.json();
                    S.questions = d.questions || []; S.complaintEN = d.complaint_en || S.complaint;
                    S.aiMode = S.questions.length >= 4 ? 'real' : 'mock';
                } catch (e) { S.questions = []; S.complaintEN = S.complaint; S.aiMode = 'mock'; }
                finally { document.getElementById('questionsSpinner').classList.remove('visible'); }
                if (!S.questions.length) { S.questions = generateFallbackQuestions(S.complaint || ''); S.aiMode = 'mock'; }
                if (!S.questions.length) { goToPage('consent'); updateConsentPage(); return; }
                document.getElementById('qIntroCard').style.display = 'none';
                const badge = document.getElementById('aiModeBadge');
                const inner = document.getElementById('aiModeBadgeInner');
                const dot = document.getElementById('aiBadgeDot');
                const badgeTxt = document.getElementById('aiBadgeText');
                if (S.aiMode === 'real') { inner.style.cssText = 'background:var(--green-l);border:1px solid var(--green-m)'; dot.style.background = 'var(--green)'; badgeTxt.style.color = 'var(--green)'; badgeTxt.textContent = t('aiMode_real'); }
                else { inner.style.cssText = 'background:#fff7ed;border:1px solid #fed7aa'; dot.style.background = 'var(--orange)'; badgeTxt.style.color = 'var(--orange)'; badgeTxt.textContent = t('aiMode_mock'); }
                badge.style.display = 'flex';
                S.answers = []; S.qIdx = 0; renderQuestion();
            }

            // ═══════════════════════════════════════════════════════════
            // OPTION TRANSLATIONS
            // ═══════════════════════════════════════════════════════════
            const OPTION_TRANS = { 'just now': { tr: 'Az önce', de: 'Gerade eben' }, '< 1 hour ago': { tr: '< 1 saat önce', de: 'Vor < 1 Stunde' }, '1–6 hours ago': { tr: '1–6 saat önce', de: 'Vor 1–6 Stunden' }, '6–24 hours ago': { tr: '6–24 saat önce', de: 'Vor 6–24 Stunden' }, '> 1 day': { tr: '1 günden fazla', de: 'Mehr als 1 Tag' }, 'suddenly': { tr: 'Aniden', de: 'Plötzlich' }, 'gradually over minutes': { tr: 'Dakikalar içinde yavaşça', de: 'Langsam über Minuten' }, 'gradually over hours': { tr: 'Saatler içinde yavaşça', de: 'Langsam über Stunden' }, 'gradually over days': { tr: 'Günler içinde yavaşça', de: 'Langsam über Tage' }, 'yes': { tr: 'Evet', de: 'Ja' }, 'no': { tr: 'Hayır', de: 'Nein' }, 'not sure': { tr: 'Emin değilim', de: 'Nicht sicher' }, 'unsure': { tr: 'Emin değilim', de: 'Nicht sicher' }, 'maybe': { tr: 'Belki', de: 'Vielleicht' }, 'mild': { tr: 'Hafif', de: 'Leicht' }, 'moderate': { tr: 'Orta', de: 'Mäßig' }, 'severe': { tr: 'Şiddetli', de: 'Schwer' }, 'head/neck': { tr: 'Baş/boyun', de: 'Kopf/Hals' }, 'chest': { tr: 'Göğüs', de: 'Brust' }, 'abdomen': { tr: 'Karın', de: 'Bauch' }, 'back': { tr: 'Sırt', de: 'Rücken' }, 'arms': { tr: 'Kollar', de: 'Arme' }, 'legs': { tr: 'Bacaklar', de: 'Beine' }, 'whole body': { tr: 'Tüm vücut', de: 'Ganzer Körper' }, 'none': { tr: 'Hiçbiri', de: 'Keines' }, 'none of the above': { tr: 'Hiçbiri', de: 'Nichts davon' }, 'within the last hour': { tr: 'Son bir saat içinde', de: 'In der letzten Stunde' }, 'a few hours ago': { tr: 'Birkaç saat önce', de: 'Vor einigen Stunden' }, 'yesterday': { tr: 'Dün', de: 'Gestern' }, 'several days ago': { tr: 'Birkaç gün önce', de: 'Vor mehreren Tagen' } };

            function translateOption(opt, langCode) {
                if (!langCode || langCode.startsWith('en')) return opt;
                const lk = langCode.startsWith('tr') ? 'tr' : langCode.startsWith('de') ? 'de' : null;
                if (!lk) return opt;
                const r = OPTION_TRANS[opt.toLowerCase().trim()];
                return (r && r[lk]) ? r[lk] : opt;
            }

            // ═══════════════════════════════════════════════════════════
            // RENDER QUESTION
            // ═══════════════════════════════════════════════════════════
            function renderQuestion() {
                let q = S.questions[S.qIdx];
                if (typeof q === 'string') q = { question: q, type: 'yes_no', options: [] };
                const total = S.questions.length;
                let { question, type, options } = q;
                if (type === 'free_text' || !options || !options.length) {
                    const ql = question.toLowerCase();
                    const _lang = S.detectedLang || S.selectedLang || 'en-GB';
                    const _to = o => translateOption(o, _lang);
                    if (/when|how long|since|start|began|wann|wie lange|başlad/.test(ql)) { type = 'multiple_choice'; options = ['Just now', '< 1 hour ago', '1–6 hours ago', '6–24 hours ago', '> 1 day'].map(_to); }
                    else if (/how|rate|scale|severity|pain|wie stark|schmerz|şiddet|ağrı/.test(ql)) { type = 'scale'; options = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']; }
                    else if (/where|location|wo |nerede/.test(ql)) { type = 'multiple_choice'; options = ['Head/neck', 'Chest', 'Abdomen', 'Back', 'Arms', 'Legs', 'Whole body'].map(_to); }
                    else { type = 'yes_no'; options = ['Yes', 'No', 'Not sure'].map(_to); }
                }
                const container = document.getElementById('questionsContainer');
                container.style.display = 'block';
                const prevAns = S.answers[S.qIdx]?.originalAnswer;
                container.innerHTML = `
    <div class="q-header">
      <span class="q-counter">${S.qIdx + 1} ${t('q_of')} ${total}</span>
      <div class="q-bar"><div class="q-fill" style="width:${Math.round(((S.qIdx + 1) / total) * 100)}%"></div></div>
    </div>
    <p class="q-text">${escHtml(question)}</p>
    <div class="${type === 'scale' ? '' : 'radio-group'}" id="qOptions"></div>`;
                const opts = document.getElementById('qOptions');
                const _lc = S.detectedLang || S.selectedLang || 'en-GB';
                const displayOpts = options.map(opt => ({ display: translateOption(opt, _lc), value: opt }));

                if (type === 'scale') {
                    const grid1 = document.createElement('div'); grid1.className = 'scale-row';
                    const grid2 = document.createElement('div'); grid2.className = 'scale-row';
                    displayOpts.forEach(({ display, value }, idx) => {
                        const pill = document.createElement('div');
                        pill.className = 'scale-pill' + (prevAns === value || prevAns === display ? ' selected' : '');
                        pill.textContent = display;
                        pill.onclick = () => {
                            S.answers[S.qIdx] = { question, question_en: q.question_en || q.question || question, answer: value, originalAnswer: display };
                            document.querySelectorAll('.scale-pill').forEach(p => p.classList.remove('selected'));
                            pill.classList.add('selected');
                            const nxt = document.getElementById('btnQNext'); nxt.disabled = false; nxt.style.opacity = '1';
                        };
                        (idx < 5 ? grid1 : grid2).appendChild(pill);
                    });
                    opts.appendChild(grid1); opts.appendChild(grid2);
                } else {
                    displayOpts.forEach(({ display, value }) => {
                        const pill = document.createElement('label');
                        pill.className = 'radio-pill' + (prevAns === value || prevAns === display ? ' selected' : '');
                        pill.innerHTML = `<div class="radio-dot"></div><span>${escHtml(display)}</span>`;
                        pill.onclick = () => {
                            S.answers[S.qIdx] = { question, question_en: q.question_en || q.question || question, answer: value, originalAnswer: display };
                            document.querySelectorAll('#qOptions .radio-pill').forEach(p => p.classList.remove('selected'));
                            pill.classList.add('selected');
                            const nxt = document.getElementById('btnQNext'); nxt.disabled = false; nxt.style.opacity = '1';
                        };
                        opts.appendChild(pill);
                    });
                }

                document.getElementById('questionNav').style.display = 'flex';
                const btnBack = document.getElementById('btnQBack'); btnBack.style.display = 'none'; // Hidden per UI request
                const btnNext = document.getElementById('btnQNext');

                const hasAns = !!S.answers[S.qIdx] && (!Array.isArray(S.answers[S.qIdx].answer) || S.answers[S.qIdx].answer.length > 0);
                btnNext.disabled = !hasAns; btnNext.style.opacity = hasAns ? '1' : '0.45';
                const isLast = S.qIdx === total - 1;
                btnNext.querySelector('span').textContent = isLast ? t('q_done').replace('→', '').trim() : t('q_next');
                if (btnBack.querySelector('span')) btnBack.querySelector('span').textContent = t('q_back');
            }
            function prevQuestion() { if (S.qIdx > 0) { S.qIdx--; renderQuestion(); } }
            function nextQuestion() {
                if (!S.answers[S.qIdx]) return;
                if (S.qIdx < S.questions.length - 1) { S.qIdx++; renderQuestion(); }
                else { goToPage('consent'); updateConsentPage(); }
            }

            // ═══════════════════════════════════════════════════════════
            // CONSENT
            // ═══════════════════════════════════════════════════════════
            function updateConsentPage() {
                const secEl = document.getElementById('cs_secureText'); if (secEl) secEl.textContent = t('cs_secureText');
                const pl = document.getElementById('cs_photoLine');
                if (pl) pl.textContent = t('cs_photoLine', { n: S.photos.length });
            }
            function setConsent(val) {
                S.dataConsent = val;
                document.getElementById('consentYes').classList.toggle('selected', val === true);
                document.getElementById('consentNo').classList.toggle('selected', val === false);
                ['consentYesDot', 'consentNoDot'].forEach((id, i) => {
                    const el = document.getElementById(id); const active = (i === 0 ? val === true : val === false);
                    el.style.background = active ? (i === 0 ? 'var(--green)' : 'var(--red)') : '';
                    el.style.borderColor = active ? (i === 0 ? 'var(--green)' : 'var(--red)') : '';
                });
                document.getElementById('consentWarning').style.display = 'none';
            }

            // ═══════════════════════════════════════════════════════════
            // FALLBACK ASSESSMENT
            // ═══════════════════════════════════════════════════════════
            function buildFallbackAssessment(complaint, answers) {
                const c = (complaint || '').toLowerCase(); const a = (answers || []).map(x => (x.answer || '').toLowerCase()).join(' '); const text = c + ' ' + a;
                let level = 'ROUTINE', score = 3;
                if (/chest pain|heart attack|stroke|unconscious|not breathing|anaphyla|severe bleeding|crushing|thunderclap|göğüs ağrısı|nefes alamıyorum|brustschmerz/i.test(text)) { level = 'EMERGENCY'; score = 9; }
                else if (/vomit|fever|dizz|faint|headache|abdominal|shortness|severe|bleed|ateş|kusma|baş ağrısı|schmerz|fieber/i.test(text)) { level = 'URGENT'; score = 6; }
                const doList = [], dontList = [];
                if (level === 'EMERGENCY') { doList.push(t('adv_call112'), t('adv_sit_still'), t('adv_stay_calm')); dontList.push(t('adv_no_drive'), t('adv_no_eat')); }
                else if (level === 'URGENT') { doList.push(t('adv_rest'), t('adv_someone_with_you'), t('adv_bring_meds')); dontList.push(t('adv_no_drive'), t('adv_no_eat')); }
                else { doList.push(t('adv_rest'), t('adv_bring_meds'), t('adv_bring_id')); }
                if (/chest|heart|brust|göğüs/i.test(text)) { doList.push(t('adv_chest_loose')); dontList.push(t('adv_chest_no_stress')); }
                if (/bleed|kanama|blutung/i.test(text)) { doList.push(t('adv_bleed_pressure')); dontList.push(t('adv_bleed_no_remove')); }
                if (/breath|nefes|atem/i.test(text)) { doList.push(t('adv_breath_upright')); dontList.push(t('adv_breath_no_lie')); }
                if (/head|baş ağrı|kopfschmerz/i.test(text)) { doList.push(t('adv_head_dark')); dontList.push(t('adv_head_no_screen')); }
                return { triage_level: level, risk_score: score, do_list: doList, dont_list: dontList, suspected_conditions: [], recommended_action: t('adv_proceed_er'), ai_mode: 'fallback' };
            }

            // ═══════════════════════════════════════════════════════════
            // SUBMIT CONSENT → AI Assessment
            // ═══════════════════════════════════════════════════════════
            async function submitConsent() {
                if (!S.dataConsent) {
                    document.getElementById('consentWarning').style.display = 'block';
                    document.getElementById('consentWarning').textContent = t('consentWarning'); return;
                }
                document.getElementById('assessSpinner').classList.add('visible');
                document.getElementById('assessSpinnerText').textContent = t('assessSpinnerText');
                document.getElementById('btnGetAssessment').disabled = true;
                const qaList = S.answers.map(a => ({ question: a.question, question_en: a.question_en || a.question, answer: a.answer, original_answer: a.originalAnswer }));
                try {
                    const r = await fetch(API + '/api/patient/assess', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            complaint: S.complaint, complaint_en: S.complaintEN, detected_language: S.detectedLang,
                            questions: S.questions.map(q => q.question_en ? q : (q.question || q)), answers: qaList, has_photo: S.photos.length > 0,
                            photo_count: S.photos.length, photo_base64: S.photos.length ? S.photos.map(p => p.dataUrl) : null,
                            photo_mime: S.photos.length ? S.photos[0].mime : null,
                            media: S.photos.length ? S.photos.map(p => ({ dataUrl: p.dataUrl, mime: p.mime || 'image/jpeg', type: p.type || 'photo' })) : null
                        })
                    });
                    S.assessment = await r.json();
                    if (S.assessment._qa_pairs && S.assessment._qa_pairs.length > 0) {
                        S.answersEN = S.assessment._qa_pairs.map(p => ({
                            question: p.question, question_en: p.question, answer: p.answer, original_answer: p.original_answer,
                        }));
                    } else {
                        S.answersEN = qaList;
                    }
                } catch (e) { S.assessment = buildFallbackAssessment(S.complaint || S.complaintEN || '', S.answers); S.answersEN = qaList; }
                finally { document.getElementById('assessSpinner').classList.remove('visible'); document.getElementById('btnGetAssessment').disabled = false; }
                goToPage('triage'); renderTriageBanner(); requestGPS();
            }

            // ═══════════════════════════════════════════════════════════
            // TRIAGE BANNER + ADVICE
            // ═══════════════════════════════════════════════════════════
            function renderTriageBanner() {
                const a = S.assessment || {}; const lvl = (a.triage_level || 'URGENT').toUpperCase();
                let cls, title, sub;
                if (lvl === 'EMERGENCY') { cls = 'emg'; title = t('tr_emg_title'); sub = t('tr_emg_sub'); }
                else if (lvl === 'URGENT') { cls = 'urg'; title = t('tr_urg_title'); sub = t('tr_urg_sub'); }
                else { cls = 'rtn'; title = t('tr_rtn_title'); sub = t('tr_rtn_sub'); }

                let html = `<div class="triage-banner ${cls}"><div class="triage-title">${title}</div><div class="triage-sub">${sub}</div></div>`;

                document.getElementById('triageBanner').innerHTML = html;
                if (typeof lucide !== 'undefined') lucide.createIcons();
            }

            // ═══════════════════════════════════════════════════════════
            // GPS
            // ═══════════════════════════════════════════════════════════
            function detectCountryFromCoords(lat, lon) {
                if (lat >= 47.2 && lat <= 55.1 && lon >= 5.9 && lon <= 15.1) return 'DE';
                if (lat >= 49.9 && lat <= 60.9 && lon >= -8.6 && lon <= 1.8) return 'UK';
                if (lat >= 35.8 && lat <= 42.1 && lon >= 26.0 && lon <= 44.8) return 'TR';
                return 'DE';
            }
            function setGPSStatus(state) {
                const pill = document.getElementById('gpsStatusPill');
                const txt = document.getElementById('gpsStatusTxt');
                pill.className = 'gps-status ' + state;
                txt.textContent = t(state === 'ok' ? 'gpsOk' : state === 'err' ? 'gpsDenied' : 'gpsDetecting');
            }
            function requestGPS() {
                if (S.lat && S.lon) { fetchHospitals(); return; }
                setGPSStatus('wait');
                document.getElementById('gpsWaiting').style.display = 'block';
                document.getElementById('gpsDenied').style.display = 'none';
                document.getElementById('hospitalList').innerHTML = '';
                if (!navigator.geolocation) { showGPSDenied(); return; }
                navigator.geolocation.getCurrentPosition(
                    pos => { S.lat = pos.coords.latitude; S.lon = pos.coords.longitude; S.country = detectCountryFromCoords(S.lat, S.lon); document.getElementById('gpsWaiting').style.display = 'none'; setGPSStatus('ok'); fetchHospitals(); },
                    () => showGPSDenied(), { timeout: 15000, enableHighAccuracy: true, maximumAge: 0 }
                );
            }
            function showGPSDenied() {
                setGPSStatus('err');
                document.getElementById('gpsWaiting').style.display = 'none';
                document.getElementById('gpsDenied').style.display = 'block';
                ['gps_deniedTitle', 'gps_deniedDesc', 'gps_retryBtn'].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = t(id); });
                const st = document.getElementById('gps_deniedSteps'); if (st) st.innerHTML = t('gps_deniedSteps');
            }
            function retryGPS() { S.lat = null; S.lon = null; document.getElementById('gpsDenied').style.display = 'none'; requestGPS(); }

            // ═══════════════════════════════════════════════════════════
            // HOSPITALS
            // ═══════════════════════════════════════════════════════════
            async function fetchHospitals() {
                const list = document.getElementById('hospitalList');
                list.innerHTML = `<div class="spinner-wrap visible" style="padding:16px 0"><div class="spinner"></div><div class="spinner-text">${t('tr_hospSpinner')}</div></div>`;
                try {
                    const r = await fetch(`${API}/api/patient/hospitals?lat=${S.lat}&lon=${S.lon}&country=${S.country}&n=3`);
                    if (!r.ok) throw new Error();
                    S.hospitals = await r.json(); if (!S.hospitals.length) throw new Error();
                    renderHospitals();
                } catch (e) {
                    list.innerHTML = `<div class="card red" style="text-align:center"><p style="font-size:.95rem;font-weight:700;color:var(--red);margin-bottom:8px">⚠️ ${t('tr_noHosp')}</p><button class="btn btn-secondary" onclick="fetchHospitals()">🔄 Retry</button></div>`;
                }
            }
            function renderHospitals() {
                const hl = document.getElementById('hospitalList');
                if (!hl) return;

                hl.innerHTML = S.hospitals.map((h, i) => {
                    const colors = { low: '#30D158', medium: '#FF9F0A', high: '#FF453A', full: '#8E8E93' };

                    // Acil Yoğunluğu Çevirisi
                    const occValue = (h.occupancy || 'medium').toLowerCase();
                    const dotColor = colors[occValue] || colors.medium;
                    const occText = t('tr_er_' + occValue) || h.occupancy_label || occValue;

                    // Trafik Yoğunluğu Hesaplaması (Basit Hız Formülü)
                    let speed = h.distance_km / (h.eta_minutes / 60);
                    let trafficLevel = 'clear';
                    if (speed < 20) trafficLevel = 'heavy';
                    else if (speed < 35) trafficLevel = 'medium';

                    const trafficColors = { clear: '#30D158', medium: '#FF9F0A', heavy: '#FF453A' };
                    const tColor = trafficColors[trafficLevel];
                    const tText = t('tr_traffic_' + trafficLevel);

                    return `
                <div class="hosp-card ${i === 0 ? 'best' : ''}" onclick="selectHospital(${i})" style="display:flex; justify-content:space-between; align-items:center; gap: 10px; padding: 20px !important;">
                    ${i === 0 ? `<div class="best-badge" style="top: -10px; left: 20px;">⭐ ${t('tr_fastest') || 'BEST CHOICE'}</div>` : ''}
                    
                    <div style="flex: 1; padding-right: 10px;">
                        <div class="hosp-name" style="padding-right:0; margin-bottom: 8px; font-size: 1.05rem; line-height: 1.2;">${h.name}</div>
                        <div class="hosp-addr" style="font-size: 0.75rem; margin-bottom: 10px;">
                            <i data-lucide="map-pin" style="width:12px; height:12px; color:var(--medical-blue)"></i>
                            ${h.address || ''}
                        </div>
                        <div style="display:flex; gap: 8px; flex-wrap: wrap;">
                            <div class="hosp-chip" style="font-size: 0.7rem; padding: 4px 10px;">
                                <i data-lucide="navigation" style="width:12px; height:12px;"></i> ${h.distance_km} km
                            </div>
                            <div class="hosp-chip" style="font-size: 0.7rem; padding: 4px 10px; color:var(--medical-blue); font-weight:800; background: var(--primary-l); border-color: var(--primary-m);">
                                <i data-lucide="timer" style="width:12px; height:12px;"></i> ~${h.eta_minutes} dk
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: flex; flex-direction: column; gap: 10px; text-align:right; min-width: 100px; border-left: 1.5px dashed var(--border); padding-left: 15px;">
                        
                        <div style="display:flex; align-items:center; justify-content:flex-end; gap:8px;">
                            <div style="display:flex; flex-direction:column; align-items:flex-end;">
                                <span style="font-size:0.55rem; color:var(--text-3); font-weight:800; text-transform:uppercase; letter-spacing:0.5px;">${t('tr_liveTraffic')}</span>
                                <span style="font-size:0.8rem; font-weight:800; color:${tColor}">${tText}</span>
                            </div>
                            <div style="background: ${tColor}15; border: 1px solid ${tColor}40; padding: 6px; border-radius: 10px; color: ${tColor}; display:flex;">
                                <i data-lucide="car" style="width:16px; height:16px;"></i>
                            </div>
                        </div>

                        <div style="display:flex; align-items:center; justify-content:flex-end; gap:8px;">
                            <div style="display:flex; flex-direction:column; align-items:flex-end;">
                                <span style="font-size:0.55rem; color:var(--text-3); font-weight:800; text-transform:uppercase; letter-spacing:0.5px;">${t('tr_erCapacity')}</span>
                                <span style="font-size:0.8rem; font-weight:800; color:${dotColor}">${occText}</span>
                            </div>
                            <div style="background: ${dotColor}15; border: 1px solid ${dotColor}40; padding: 6px; border-radius: 10px; color: ${dotColor}; display:flex;">
                                <i data-lucide="activity" style="width:16px; height:16px;"></i>
                            </div>
                        </div>
                        
                    </div>
                </div>`;
                }).join('');

                lucide.createIcons();
            }

            // ═══════════════════════════════════════════════════════════
            // SELECT HOSPITAL + SUBMIT
            // ═══════════════════════════════════════════════════════════
            async function selectHospital(idx) {
                S.selectedHospital = S.hospitals[idx];
                S.regNumber = genRegNumber();


                const list = document.getElementById('hospitalList');
                if (list) {
                    list.innerHTML = `<div class="spinner-wrap visible" style="padding:48px 0">
                    <div class="spinner"></div>
                    <div class="spinner-text">${t('tr_notifying')}</div>
                </div>`;
                }

                try {
                    const mediaArr = S.photos.length > 0 ? S.photos.map(p => ({ dataUrl: p.dataUrl, mime: p.mime || 'image/jpeg', type: p.type || 'photo' })) : null;
                    const qaList = (S.answersEN || S.answers || []).map(a => ({
                        question: a.question || '',
                        question_en: a.question_en || a.question || '',
                        answer: a.answer || '',
                        original_answer: a.original_answer || a.originalAnswer || a.answer || ''
                    })).filter(a => a.question && a.answer);

                    const response = await fetch(API + '/api/patient/submit', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            complaint: S.complaint,
                            complaint_en: S.complaintEN || S.complaint,
                            detected_language: S.detectedLang,
                            assessment: S.assessment,
                            hospital: S.selectedHospital,
                            lat: S.lat,
                            lon: S.lon,
                            answers: qaList,
                            has_photo: S.photos.length > 0,
                            photo_count: S.photos.length,
                            media: mediaArr,
                            reg_number: S.regNumber,
                            health_number: S.healthNumber || null,
                            data_consent: S.dataConsent
                        })
                    });

                    if (!response.ok) throw new Error('Submission failed');


                    renderResult();
                    goToPage('result');

                } catch (error) {
                    console.error("Submission error:", error);
                    toast("Connection error. Please try again.", "warn");
                    renderHospitals();
                }
            }

            // ═══════════════════════════════════════════════════════════
            // RESULT (Updated with Elegant UI & Lucide Icons)
            // ═══════════════════════════════════════════════════════════

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

                renderTriageBannerInternal(triageLevel);

                let doList = assessmentData.do_list || [];
                let dontList = assessmentData.dont_list || [];
                renderAdviceBlock('resultAdvice', doList, dontList, triageLevel);

                lucide.createIcons();

                if (typeof startLiveTracking === 'function') {
                    startLiveTracking();
                }
            }

            function switchResultTab(idx) {
                document.querySelectorAll('.result-tab-btn').forEach((btn, i) => {
                    btn.classList.toggle('active', i === idx);
                });
                document.querySelectorAll('.result-tab-panel').forEach((panel, i) => {
                    panel.classList.toggle('active', i === idx);
                });
            }

            // ═══════════════════════════════════════════════════════════
            // ADVICE BLOCK
            // ═══════════════════════════════════════════════════════════
            function renderAdviceBlock(containerId, doList, dontList, level) {
                const color = { EMERGENCY: 'var(--red)', URGENT: 'var(--orange)', ROUTINE: 'var(--green)' }[level] || 'var(--blue)';
                let html = `<div style="border:1.5px solid ${color};border-radius:var(--r-lg);padding:16px;margin-bottom:14px">`;
                if (doList.length) {
                    html += `<p style="font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:${color};margin-bottom:8px">${t('tr_doLabel')}</p>`;
                    html += `<ul class="advice-list">`;
                    doList.forEach(item => { html += `<li><span class="icon" style="color:var(--green)">✅</span>${escHtml(item)}</li>`; });
                    html += `</ul>`;
                }
                if (dontList.length) {
                    html += `<p style="font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--red);margin-top:12px;margin-bottom:8px">${t('tr_dontLabel')}</p>`;
                    html += `<ul class="advice-list">`;
                    dontList.forEach(item => { html += `<li><span class="icon" style="color:var(--red)">❌</span>${escHtml(item)}</li>`; });
                    html += `</ul>`;
                }
                html += `</div>`;
                const container = document.getElementById(containerId);
                if (container) container.innerHTML = html;
            }

            // ═══════════════════════════════════════════════════════════
            // UTILITIES
            // ═══════════════════════════════════════════════════════════
            function genRegNumber() {
                const now = new Date();
                const pad = n => String(n).padStart(2, '0');
                return `VN-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${Math.floor(1000 + Math.random() * 9000)}`;
            }
            function escHtml(s) {
                return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            }
            let _toastTimer = null;
            function toast(msg, type) {
                const el = document.getElementById('toast');
                el.textContent = msg;
                el.className = 'show';
                if (type === 'warn') el.style.background = 'var(--orange)';
                else el.style.background = 'var(--navy)';
                clearTimeout(_toastTimer);
                _toastTimer = setTimeout(() => { el.className = ''; }, 3200);
            }

            // ═══════════════════════════════════════════════════════════
            // LIVE GPS TRACKING (Client-side)
            // ═══════════════════════════════════════════════════════════
            let _trackingWatchId = null;

            function startLiveTracking() {
                if (!navigator.geolocation) {
                    console.warn("Geolocation is not supported by your browser.");
                    return;
                }

                // Clear any existing tracker to prevent duplicates
                if (_trackingWatchId !== null) {
                    navigator.geolocation.clearWatch(_trackingWatchId);
                }

                // Start continuously watching the patient's position
                _trackingWatchId = navigator.geolocation.watchPosition(
                    async (position) => {
                        const currentLat = position.coords.latitude;
                        const currentLon = position.coords.longitude;

                        // We need the registration number (patient_id) to update the backend
                        if (!S.regNumber) return;

                        try {
                            // Send the new coordinates to the FastAPI backend
                            await fetch(`${API}/api/patient/${S.regNumber}/location`, {
                                method: 'PATCH',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    lat: currentLat,
                                    lon: currentLon
                                })
                            });
                            console.log("Live location synced:", currentLat, currentLon);
                        } catch (error) {
                            console.error("Failed to sync live location:", error);
                        }
                    },
                    (error) => {
                        console.warn("Live tracking error or permission denied:", error);
                    },
                    {
                        enableHighAccuracy: true, // Use GPS chip for precise tracking
                        maximumAge: 5000,         // Accept cached positions up to 5 seconds old
                        timeout: 10000            // Timeout if no location is found
                    }
                );
            }

            // === V3 ENHANCEMENTS ===
            const _THEME_KEY = 'cz_theme';
            function applyTheme(t) { document.documentElement.setAttribute('data-theme', t); const sun = document.getElementById('themeIconSun'); const moon = document.getElementById('themeIconMoon'); if (sun) sun.style.display = t === 'dark' ? 'block' : 'none'; if (moon) moon.style.display = t === 'dark' ? 'none' : 'block'; }
            function toggleTheme() { const cur = document.documentElement.getAttribute('data-theme') || 'light'; const next = cur === 'dark' ? 'light' : 'dark'; localStorage.setItem(_THEME_KEY, next); applyTheme(next); }
            (function initTheme() { const saved = localStorage.getItem(_THEME_KEY); const sys = window.matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light'; applyTheme(saved || sys); })();
            const PAGE_STEPS = { 'page-lang': 0, 'page-welcome': 1, 'page-input': 2, 'page-photos': 2, 'page-questions': 3, 'page-consent': 4, 'page-triage': 5, 'page-result': 5 };
            const STEP_LBL = { en: ['', '', 'Step 2 of 5', 'Step 2 of 5', 'Step 3 of 5', 'Step 4 of 5', 'Step 5 of 5', 'Complete'], de: ['', '', 'Schritt 2/5', 'Schritt 2/5', 'Schritt 3/5', 'Schritt 4/5', 'Schritt 5/5', 'Fertig'], tr: ['', '', 'Adim 2/5', 'Adim 2/5', 'Adim 3/5', 'Adim 4/5', 'Adim 5/5', 'Tamam'] };
            // goToPage wrapper — uses IIFE to capture original before override (avoids hoisting conflict)
            window.goToPage = (function () { var _o = goToPage; return function (p) { _o(p); var st = PAGE_STEPS[p] || 0, f = document.getElementById('progressFill'), l = document.getElementById('progressLabel'), w = document.getElementById('progressBarWrap'); if (f) f.style.width = Math.round(st / 5 * 100) + '%'; var lk = (S.selectedLang || 'en').startsWith('tr') ? 'tr' : (S.selectedLang || 'en').startsWith('de') ? 'de' : 'en'; var si = { 'page-lang': 0, 'page-welcome': 1, 'page-input': 2, 'page-photos': 2, 'page-questions': 3, 'page-consent': 4, 'page-triage': 6, 'page-result': 7 }[p] || 0; if (l) l.textContent = (STEP_LBL[lk] || STEP_LBL.en)[si] || ''; if (w) w.style.display = st === 0 ? 'none' : 'block'; }; })();
            document.getElementById('progressBarWrap') && (document.getElementById('progressBarWrap').style.display = 'none');
            const _sms = typeof setMicState === 'function' ? setMicState : null;
            window.setMicState = function (s) { if (_sms) _sms(s); const wf = document.getElementById('waveformBars'); if (wf) wf.classList.toggle('active', s === 'recording'); };
            document.addEventListener('click', function (e) { const pill = e.target.closest('.radio-pill') || e.target.closest('.scale-pill'); if (!pill) return; /* chatUserAnswer removed for linear flow */ }, true);
            if (typeof lucide !== 'undefined') lucide.createIcons();
            function notifyContact() {
                const btn = document.getElementById("rs_contactBtn");
                const orig = btn.innerHTML;
                btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin 1s linear infinite"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Sending...`;
                setTimeout(() => {
                    btn.classList.remove("btn-secondary");
                    btn.style.background = "var(--success)";
                    btn.style.color = "#fff";
                    btn.style.borderColor = "var(--success)";
                    btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Contact Notified`;
                }, 1500);
            }

            /**
             * Renders the triage status banner on the final result page.
             * Fixes the ReferenceError: renderTriageBannerInternal is not defined.
             */
            function renderTriageBannerInternal(level) {
                const banner = document.getElementById('resultBanner');
                if (!banner) return;

                let cls = level === 'EMERGENCY' ? 'emg' : level === 'URGENT' ? 'urg' : 'rtn';
                let title = t('rs_notified_' + cls.toLowerCase());

                banner.innerHTML = `
                <div class="triage-banner ${cls}" style="border-radius:20px; text-align:center; padding:24px; margin-bottom:20px; box-shadow: var(--sh);">
                    <div class="triage-title" style="justify-content:center; font-size:1.3rem; margin-bottom:8px;">
                        ${title}
                    </div>
                    <div style="font-size:0.9rem; opacity:0.9;">
                        ${level === 'EMERGENCY' ? 'Medical team has been alerted for your immediate arrival.' : 'Your information has been securely transmitted to the clinical team.'}
                    </div>
                </div>`;

                // Removed the "Call 112" button logic completely as requested.
                const callDiv = document.getElementById('resultEmergencyCall');
                if (callDiv) {
                    callDiv.innerHTML = '';
                }
            }
        