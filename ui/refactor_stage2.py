import re

filepath = "e:/3. projects/CodeZero/ui/patient_app_v8.html"
with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

# --- 1. Chat CSS ---
chat_css = """
        /* -- CHAT UI CSS -- */
        .chat-bubble {
            max-width: 85%;
            padding: 12px 16px;
            font-size: 0.95rem;
            line-height: 1.5;
            position: relative;
            animation: tabFadeIn 0.3s ease;
            word-wrap: break-word;
        }
        .ai-bubble {
            background-color: var(--primary-l);
            color: var(--primary-text);
            border-radius: 16px 16px 16px 4px;
            align-self: flex-start;
            border: 1px solid var(--primary-m);
            box-shadow: 0 2px 8px rgba(13,148,136,0.05);
        }
        .user-bubble {
            background-color: var(--ios-card);
            color: var(--text);
            border-radius: 16px 16px 4px 16px;
            align-self: flex-end;
            border: 1px solid var(--border);
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .chat-options-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .chat-opt-btn {
            background: var(--card);
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 8px 14px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .chat-opt-btn:hover {
            background: var(--primary);
            color: #fff;
        }
        .chat-media-preview {
            width: 100px;
            height: 100px;
            border-radius: 12px;
            object-fit: cover;
            margin-top: 8px;
            border: 2px solid var(--primary-l);
        }
"""
text = text.replace('/* ══ WELCOME / LANGUAGE PAGE (Elegant V5) ══ */', chat_css + '\\n        /* ══ WELCOME / LANGUAGE PAGE (Elegant V5) ══ */')

# --- 2. Chat HTML replacing INPUT, PHOTOS, QUESTIONS ---
chat_html = """
        <!-- PAGE: CHAT (Unified Assessment) -->
        <div class="page" id="page-chat" style="display:flex; flex-direction:column; height: 100dvh; background: var(--ios-bg);">
            <!-- Header -->
            <div style="padding: 15px 20px; background: var(--card); border-bottom: 1px solid var(--border); display:flex; align-items:center; gap: 12px; position: sticky; top:0; z-index: 10;">
                <div class="ai-robot-chat-icon" style="width: 40px; height: 40px; border-radius: 50%; background: var(--primary-l); display: flex; align-items: center; justify-content: center; overflow: hidden; border: 1px solid var(--primary-m);">
                    <img src="/docs/images/AIVoN.png" alt="AIVoN" style="width: 80%; height: 80%; object-fit: contain;">
                </div>
                <!-- Back Button inside header for early exit, hidden by default -->
                <div>
                    <h3 style="font-size: 1.1rem; font-weight: 800; color: var(--text); margin:0;" id="chatHeaderTitle">AIVoN</h3>
                    <div style="font-size: 0.75rem; color: var(--success); font-weight: 600; display:flex; align-items:center; gap:4px;">
                        <div style="width:6px; height:6px; background:var(--success); border-radius:50%;"></div>
                        <span id="chatHeaderSub">AI Assistant connected</span>
                    </div>
                </div>
                <button id="btnFinishChat" onclick="finishChatAssessment()" style="margin-left:auto; background: var(--success); color: white; border: none; padding: 8px 16px; border-radius: 99px; font-size: 0.85rem; font-weight: 700; cursor: pointer; display: none;">Finish</button>
            </div>

            <!-- Chat Messages Area -->
            <div id="chatMessages" style="flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; padding-bottom: 20px;">
                <div class="chat-bubble ai-bubble">
                    <p id="chat_intro">Please describe your symptoms, what happened, or select from the options below.</p>
                </div>
                <!-- Suggested symptom chips -->
                <div class="chat-options-grid" id="chatSymptomGrid"></div>
                
                <!-- Typing Indicator -->
                <div id="chatTyping" class="chat-bubble ai-bubble" style="display:none; width: 60px; justify-content:center; gap:4px;">
                    <div class="spinner" style="width: 14px; height:14px; border-width:2px;"></div>
                </div>
            </div>

            <!-- Input Area (Bottom) -->
            <div style="padding: 12px 20px 24px; background: var(--card); border-top: 1px solid var(--border); display:flex; flex-direction: column; gap: 12px;">
                <!-- Action Row (Camera, Image) -->
                <div style="display:flex; gap: 15px; align-items:center; margin-bottom: 5px;" id="chatActionRow">
                     <label style="color: var(--text-2); cursor: pointer; display:flex; align-items:center; gap:6px;">
                        <i data-lucide="camera" style="width: 20px; height: 20px;"></i>
                        <span id="chat_addPhoto" style="font-size:0.8rem; font-weight:600;">Photo</span>
                        <input type="file" id="chatPhotoInput" accept="image/*" capture="environment" onchange="onChatMediaAdded(event,'photo')" style="display:none">
                     </label>
                     <label style="color: var(--text-2); cursor: pointer; display:flex; align-items:center; gap:6px;">
                        <i data-lucide="video" style="width: 20px; height: 20px;"></i>
                        <span id="chat_addVideo" style="font-size:0.8rem; font-weight:600;">Video</span>
                        <input type="file" id="chatVideoInput" accept="video/*" capture="environment" onchange="onChatMediaAdded(event,'video')" style="display:none">
                     </label>
                     <div id="chatMicStatus" style="margin-left:auto; font-size: 0.8rem; font-weight:700; color:var(--danger); display:none; align-items:center; gap:6px;">
                        <div class="live-glow" style="background:var(--danger); box-shadow:0 0 8px var(--danger);"></div>
                        <span id="chatMicStatusTxt">Recording...</span>
                     </div>
                </div>

                <!-- Chat Input Bar -->
                <div style="display:flex; gap: 10px; align-items:center;">
                    <div style="flex:1; background: var(--ios-bg); border-radius: 20px; border: 1px solid var(--border); padding: 8px 16px; display:flex; align-items:center; min-height: 44px;">
                        <input type="text" id="chatInputText" placeholder="Type or speak..." style="width:100%; border:none; background:transparent; font-size:0.95rem; outline:none; font-family:var(--font-main);" onkeypress="if(event.key==='Enter') sendChatMessage()">
                    </div>
                    
                    <button id="chatMicBtn" onclick="toggleChatRecording()" style="width: 44px; height: 44px; border-radius: 50%; background: var(--primary); color: white; border:none; display:flex; align-items:center; justify-content:center; flex-shrink:0; cursor:pointer;">
                        <i data-lucide="mic" style="width: 20px; height: 20px;"></i>
                    </button>
                    <button id="chatSendBtn" onclick="sendChatMessage()" style="width: 44px; height: 44px; border-radius: 50%; background: var(--success); color: white; border:none; display:none; align-items:center; justify-content:center; flex-shrink:0; cursor:pointer;">
                        <i data-lucide="send" style="width: 20px; height: 20px;"></i>
                    </button>
                </div>
            </div>
        </div>
"""

start_input_idx = text.find('<!-- PAGE: INPUT -->')
end_questions_idx = text.find('<!-- PAGE: CONSENT -->')

if start_input_idx != -1 and end_questions_idx != -1:
    text = text[:start_input_idx] + chat_html + "\\n        " + text[end_questions_idx:]

with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)

print("Refactor stage 2 HTML complete.")
