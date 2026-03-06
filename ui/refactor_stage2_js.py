import re

filepath = "e:/3. projects/CodeZero/ui/patient_app_v8.html"
with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update STEP_MAP
text = text.replace(
    "const STEP_MAP = { lang: -1, welcome: -1, input: 0, photos: 1, questions: 2, consent: 2, triage: 3, result: 4 };",
    "const STEP_MAP = { lang: 0, chat: 1, consent: 2, triage: 3, result: 4 };"
)

# 2. Add Chat JS
chat_js = """
                // ═══════════════════════════════════════════════════════════
                // UNIFIED CHAT ENGINE
                // ═══════════════════════════════════════════════════════════
                let chatHistory = [];
                let chatStage = 'initial'; // initial, questioning
                
                function addChatBubble(text, sender, isLoading = false) {
                    const msgDiv = document.createElement('div');
                    msgDiv.className = `chat-bubble ${sender}-bubble`;
                    
                    if (isLoading) {
                        msgDiv.innerHTML = `<div class="spinner" style="width: 14px; height:14px; border-width:2px; display:inline-block;"></div>`;
                        msgDiv.id = 'chatTypingIndicator';
                    } else {
                        msgDiv.innerHTML = `<p>${escHtml(text)}</p>`;
                    }
                    
                    document.getElementById('chatMessages').insertBefore(msgDiv, document.getElementById('chatTyping'));
                    document.getElementById('chatMessages').scrollTop = document.getElementById('chatMessages').scrollHeight;
                    
                    return msgDiv;
                }

                function showTypingIndicator() {
                    document.getElementById('chatTyping').style.display = 'flex';
                    document.getElementById('chatMessages').scrollTop = document.getElementById('chatMessages').scrollHeight;
                }

                function hideTypingIndicator() {
                    document.getElementById('chatTyping').style.display = 'none';
                }

                function onChatMediaAdded(evt, type) {
                    const file = evt.target.files[0]; if (!file) return;
                    if (S.photos.length >= 3) {
                        toast(t('Media limit reached (3).'), 'warn');
                        return;
                    }
                    const reader = new FileReader();
                    reader.onload = e => {
                        S.photos.push({ dataUrl: e.target.result, mime: file.type, type });
                        // Add bubble for media
                        const isVid = type === 'video' || file.type.startsWith('video/');
                        const msgDiv = document.createElement('div');
                        msgDiv.className = `chat-bubble user-bubble`;
                        if (isVid) {
                            msgDiv.innerHTML = `<video src="${e.target.result}" class="chat-media-preview"></video><div style="font-size:0.75rem; color:var(--text-3); margin-top:4px;">Video attached</div>`;
                        } else {
                            msgDiv.innerHTML = `<img src="${e.target.result}" class="chat-media-preview"><div style="font-size:0.75rem; color:var(--text-3); margin-top:4px;">Photo attached</div>`;
                        }
                        document.getElementById('chatMessages').insertBefore(msgDiv, document.getElementById('chatTyping'));
                        document.getElementById('chatMessages').scrollTop = document.getElementById('chatMessages').scrollHeight;
                    };
                    reader.readAsDataURL(file); evt.target.value = '';
                }

                async function sendChatMessage(customText = null) {
                    const inputEl = document.getElementById('chatInputText');
                    let text = customText || inputEl.value.trim();
                    if (!text) return;
                    
                    inputEl.value = '';
                    addChatBubble(text, 'user');
                    
                    if (chatStage === 'initial') {
                        // First message = complaint
                        S.complaint += (S.complaint ? ", " : "") + text;
                        document.getElementById('chatSymptomGrid').style.display = 'none';
                        chatStage = 'questioning';
                        await initializeQuestions();
                    } else if (chatStage === 'questioning') {
                        // Answering a question
                        if (S.questions && S.qIdx < S.questions.length) {
                            const q = S.questions[S.qIdx];
                            S.answers.push({ 
                                question: q.question || q, 
                                question_en: q.question_en || q.question || q, 
                                answer: text, 
                                originalAnswer: text 
                            });
                            S.qIdx++;
                            askNextQuestion();
                        }
                    }
                }

                function submitQuickOption(val, text) {
                    sendChatMessage(text || val);
                }

                async function initializeQuestions() {
                    showTypingIndicator();
                    try {
                        const r = await fetch(API + '/api/patient/questions', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ complaint: S.complaint, complaint_en: S.complaintEN, detected_language: S.detectedLang })
                        });
                        const d = await r.json();
                        S.questions = d.questions || []; S.complaintEN = d.complaint_en || S.complaint;
                    } catch (e) { 
                        S.questions = []; S.complaintEN = S.complaint; 
                    }
                    
                    if (!S.questions.length) { 
                        S.questions = generateFallbackQuestions(S.complaint || '');
                    }
                    
                    hideTypingIndicator();
                    
                    if (!S.questions.length) { 
                        finishChatAssessment();
                        return; 
                    }
                    
                    S.answers = []; 
                    S.qIdx = 0; 
                    askNextQuestion();
                }

                function renderChatOptions(options) {
                    document.querySelectorAll('.chat-opt-btn.ephemeral').forEach(el => el.remove());
                    
                    if (!options || options.length === 0) return;
                    
                    const grid = document.createElement('div');
                    grid.className = 'chat-options-grid ephemeral';
                    grid.style.padding = '0 20px 10px 20px';
                    grid.style.alignSelf = 'flex-start';
                    
                    const _lc = S.detectedLang || S.selectedLang || 'en-GB';
                    
                    options.forEach(opt => {
                        const display = translateOption(opt, _lc);
                        const btn = document.createElement('button');
                        btn.className = 'chat-opt-btn';
                        btn.textContent = display;
                        btn.onclick = () => {
                            grid.remove();
                            submitQuickOption(opt, display);
                        };
                        grid.appendChild(btn);
                    });
                    
                    document.getElementById('chatMessages').insertBefore(grid, document.getElementById('chatTyping'));
                    document.getElementById('chatMessages').scrollTop = document.getElementById('chatMessages').scrollHeight;
                }

                function askNextQuestion() {
                    // Remove old ephemeral options
                    document.querySelectorAll('.chat-opt-btn.ephemeral').forEach(el => el.remove());
                    
                    if (S.qIdx >= S.questions.length) {
                        // Finished
                        addChatBubble(t('Thank you. Tap Finish to get your results.'), 'ai');
                        document.getElementById('btnFinishChat').style.display = 'block';
                        return;
                    }
                    
                    let q = S.questions[S.qIdx];
                    if (typeof q === 'string') q = { question: q, type: 'yes_no', options: [] };
                    
                    let { question, type, options } = q;
                    if (type === 'free_text' || !options || !options.length) {
                        const ql = question.toLowerCase();
                        const _lang = S.detectedLang || S.selectedLang || 'en-GB';
                        const _to = o => translateOption(o, _lang);
                        if (/when|how long|since|start|began|wann|wie lange|başlad/.test(ql)) { type = 'multiple_choice'; options = ['Just now', '< 1 hour ago', '1–6 hours ago', '6–24 hours ago', '> 1 day']; }
                        else if (/how|rate|scale|severity|pain|wie stark|schmerz|şiddet|ağrı/.test(ql)) { type = 'scale'; options = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']; }
                        else if (/where|location|wo |nerede/.test(ql)) { type = 'multiple_choice'; options = ['Head/neck', 'Chest', 'Abdomen', 'Back', 'Arms', 'Legs', 'Whole body']; }
                        else { type = 'yes_no'; options = ['Yes', 'No', 'Not sure']; }
                    }
                    
                    addChatBubble(question, 'ai');
                    renderChatOptions(options);
                }

                function finishChatAssessment() {
                    goToPage('consent'); 
                    updateConsentPage();
                }

                // Chat Microphone logic using WebSpeech
                let chatSpeechRec = null;
                let chatIsRecording = false;

                function toggleChatRecording() {
                    const micBtn = document.getElementById('chatMicBtn');
                    const micStatus = document.getElementById('chatMicStatus');
                    const inputEl = document.getElementById('chatInputText');
                    
                    if (chatIsRecording) {
                        chatIsRecording = false;
                        micBtn.style.background = 'var(--primary)';
                        micBtn.classList.remove('recording');
                        micStatus.style.display = 'none';
                        if (chatSpeechRec) { try { chatSpeechRec.stop(); } catch(e){} }
                        if (inputEl.value.trim()) {
                            // Optionally auto-send
                            sendChatMessage();
                        }
                    } else {
                        const SR = window.SpeechRecognition || window.webkitSpeechRecognition; 
                        if (!SR) { toast('Mic not supported in this browser.', 'warn'); return; }
                        
                        chatSpeechRec = new SR();
                        chatSpeechRec.continuous = true; 
                        chatSpeechRec.interimResults = true;
                        chatSpeechRec.lang = S.selectedLang || S.detectedLang || 'tr-TR';
                        
                        inputEl.value = '';
                        
                        chatSpeechRec.onresult = e => {
                            let interim = '', final = '';
                            for (let i = 0; i < e.results.length; i++) {
                                if (e.results[i].isFinal) final += e.results[i][0].transcript + ' ';
                                else interim += e.results[i][0].transcript;
                            }
                            inputEl.value = (final || interim).trim();
                        };
                        
                        chatSpeechRec.onerror = e => {
                            if (e.error !== 'no-speech' && e.error !== 'aborted') {
                                toast('Mic error: ' + e.error, 'warn');
                                toggleChatRecording();
                            }
                        };
                        
                        try { 
                            chatSpeechRec.start(); 
                            chatIsRecording = true;
                            micBtn.style.background = 'var(--danger)';
                            micBtn.classList.add('recording');
                            micStatus.style.display = 'flex';
                        } catch (e) {
                            console.warn('WebSpeech start failed:', e);
                        }
                    }
                }
"""

start_marker = "                // ═══════════════════════════════════════════════════════════\\n                // MIC RECORDING"
end_marker = "                // ═══════════════════════════════════════════════════════════\\n                // SUBMIT CONSENT"

start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx != -1 and end_idx != -1:
    text = text[:start_idx] + chat_js + "\\n" + text[end_idx:]

with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)

print("Refactor stage 2 JS complete.")
