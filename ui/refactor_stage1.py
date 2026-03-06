import re

filepath = "e:/3. projects/CodeZero/ui/patient_app_v8.html"
with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Inject Emergency Banner and move .hn-wrap into #page-lang
# We find where `<div class="lang-list">` starts.
lang_list_marker = '<div class="lang-list">'

injection = """
            <!-- Emergency Banner -->
            <div id="emergency-banner" style="background:var(--danger-l); border: 2px solid var(--danger-m); color:var(--danger-text); padding: 15px; border-radius: var(--r); margin-bottom: 20px; width: 100%; text-align: left; display: flex; align-items: flex-start; gap: 12px; box-shadow: var(--sh-sm);">
                <i data-lucide="alert-triangle" style="width: 24px; height: 24px; flex-shrink: 0; margin-top: 2px;"></i>
                <div style="font-size: 0.9rem; line-height: 1.4; font-weight: 600;">
                    <strong style="display: block; font-size: 1rem; margin-bottom: 4px;">EMERGENCY CHECK</strong>
                    If this is a severe emergency (e.g., chest pain, severe bleeding, or difficulty breathing), call 112 immediately.
                </div>
            </div>

            <div class="hn-wrap" style="width: 100%; margin-bottom: 24px;">
                <div class="hn-label">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                    <span id="wl_hnLabel">Select your Health Record</span><span class="req" id="wl_hnReq">*</span>
                </div>
                <button class="hn-select-btn" id="hnSelectBtn" onclick="toggleHnDropdown()">
                    <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                        style="color:var(--text-3);flex-shrink:0">
                        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                        <polyline points="9 22 9 12 15 12 15 22" />
                    </svg>
                    <span class="hn-val placeholder" id="hnSelectVal" data-placeholder="true">Select your Health Record...</span>
                    <span class="hn-chevron">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M6 9l6 6 6-6" />
                        </svg>
                    </span>
                </button>
                <div class="hn-dropdown" id="hnDropdown"></div>
                <div class="hn-hint">
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 8v4M12 16h.01" />
                    </svg>
                    <span id="wl_hnHintText">Required for triage integration</span>
                </div>
            </div>

            <div class="lang-list">
"""

text = text.replace(lang_list_marker, injection)

# 2. Delete the #page-welcome AND the old .hn-wrap inside it
# We remove everything from `<!-- PAGE: WELCOME -->` down to the end of `#page-welcome` block before `<!-- PAGE: INPUT -->`
start_idx = text.find('<!-- PAGE: WELCOME -->')
end_idx = text.find('<!-- PAGE: INPUT -->')
if start_idx != -1 and end_idx != -1:
    # also add system logic hints that were at the bottom of welcome
    bottom_notices = """
            <p id="wl_system_notice" style="text-align:center;font-size:0.85rem;color:var(--text-2);margin-top:16px;">
            </p>
            <p id="wl_demo" style="text-align:center;font-size:.78rem;color:var(--text-3);margin-top:10px"></p>
        </div>
"""
    # Replace end of page-language to include the notices
    end_lang_idx = text.find('</div>', text.find('id="langBtn_tr"'))
    end_lang_idx = text.find('</div>', end_lang_idx + 1) + 6 # close lang-Choice-card then lang-list
    
    # Actually wait. Let's just do regex or split.
    text = text[:start_idx] + bottom_notices + "\\n        " + text[end_idx:]

# 3. Change `selectLanguage` logic to enforce health record -> navigate to input
old_select = """
                    setTimeout(() => {
                        document.getElementById('page-lang').classList.remove('active');
                        goToPage('welcome');
                        checkAIStatus();
                    }, 200);"""

new_select = """
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
                        goToPage('input');
                        checkAIStatus();
                    }, 400);"""

text = text.replace(old_select, new_select)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)

print("Refactor stage 1 complete.")
