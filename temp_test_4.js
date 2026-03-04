
        // â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        //  VitalNavAI Â· Clinical Cockpit Â· JavaScript
        // â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

        const TRIAGE_COLOR = { EMERGENCY: '#B91C1C', URGENT: '#D97706', ROUTINE: '#059669' };
        const TRIAGE_CLASS = { EMERGENCY: 'E', URGENT: 'U', ROUTINE: 'R' };
        const TRIAGE_BADGE = {
            EMERGENCY: '<span class="t-badge E">â— EMERGENCY</span>',
            URGENT: '<span class="t-badge U">â— URGENT</span>',
            ROUTINE: '<span class="t-badge R">â— ROUTINE</span>',
        };
        const FLAG = { DE: 'ðŸ‡©ðŸ‡ª', TR: 'ðŸ‡¹ðŸ‡·', UK: 'ðŸ‡¬ðŸ‡§', GB: 'ðŸ‡¬ðŸ‡§', FR: 'ðŸ‡«ðŸ‡·', IT: 'ðŸ‡®ðŸ‡¹', ES: 'ðŸ‡ªðŸ‡¸', NL: 'ðŸ‡³ðŸ‡±', PL: 'ðŸ‡µðŸ‡±', RU: 'ðŸ‡·ðŸ‡º' };
        const LANG_NAME = {
            'de-DE': 'Deutsch', 'tr-TR': 'TÃ¼rkÃ§e', 'en-GB': 'English',
            'en-US': 'English', 'fr-FR': 'FranÃ§ais', 'ar-SA': 'Ø§Ù„Ø¹Ø±Ø¨ÙŠØ©',
            'es-ES': 'EspaÃ±ol', 'it-IT': 'Italiano', 'nl-NL': 'Nederlands',
            'pl-PL': 'Polski', 'ru-RU': 'Ð ÑƒÑÑÐºÐ¸Ð¹', 'zh-CN': 'ä¸­æ–‡',
        };
        const STATUS_MAP = {
            incoming: 'Incoming', arrived: 'Arrived',
            in_treatment: 'In Treatment', discharged: 'Discharged'
        };

        let sortMode = 'triage', currentTab = 'incoming';
        let mapInstance = null, mapMarkers = [];
        const _patientCache = {};  // pid -> patient object cache for Medical History

        // â”€â”€ Clock â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        function tick() {
            const n = new Date();
            const d = n.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
            const t = n.toTimeString().slice(0, 8);
            document.getElementById('topbar-clock').textContent = d + '  ' + t;
        }
        setInterval(tick, 1000); tick();

        // â”€â”€ Tab switching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        function showTab(name) {
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));
            document.querySelectorAll('.nav-btn').forEach(b => { b.classList.remove('text-blue-400', 'bg-blue-900/30', 'text-slate-900', 'bg-slate-200'); b.classList.add('text-slate-300', 'hover:bg-slate-800', 'hover:text-white', 'dark:text-slate-300'); b.querySelector('.absolute')?.remove(); });
            document.getElementById('tab-' + name).classList.add('active');
            document.getElementById('nav-' + name).classList.add('active');
            currentTab = name;
            if (name === 'tracking') { initMap(); refreshTracking(); }
            if (name === 'admin') loadAdminTable();
            if (name === 'statistics') loadLiveStats();
            if (name === 'reports') loadReports();
            if (name === 'health') initHRChips();
        }

        function showSubtab(group, name, el) {
            document.querySelectorAll('#tab-' + group + ' .stab-pane').forEach(p => p.classList.add('hidden'));
            document.querySelectorAll('#tab-' + group + ' .stab').forEach(b => { b.classList.remove('text-blue-400', 'bg-blue-900/30', 'text-slate-900', 'bg-slate-200'); b.classList.add('text-slate-300', 'hover:bg-slate-800', 'hover:text-white', 'dark:text-slate-300'); b.querySelector('.absolute')?.remove(); });
            document.getElementById(group + '-' + name).classList.add('active');
            el.classList.add('active');
        }

        function setSort(s, el) {
            sortMode = s;
            document.querySelectorAll('.sort-btn').forEach(b => { b.classList.remove('text-blue-400', 'bg-blue-900/30', 'text-slate-900', 'bg-slate-200'); b.classList.add('text-slate-300', 'hover:bg-slate-800', 'hover:text-white', 'dark:text-slate-300'); b.querySelector('.absolute')?.remove(); });
            el.classList.add('active');
            loadPatients();
        }

        // â”€â”€ API helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        async function api(path, opts = {}) {
            const r = await fetch(path, opts);
            if (!r.ok) throw new Error(r.status);
            return r.json();
        }

        // â”€â”€ Refresh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        async function doRefresh() {
            await loadKPI();
            if (currentTab === 'incoming') loadPatients();
            if (currentTab === 'tracking') refreshTracking();
            if (currentTab === 'statistics') loadLiveStats();
            if (currentTab === 'reports') loadReports();
        }

        // â”€â”€ KPI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        async function loadKPI() {
            try {
                const s = await api('/api/stats');
                document.getElementById('k-total').textContent = s.total;
                document.getElementById('k-emg').textContent = s.emergencies;
                document.getElementById('k-urg').textContent = s.urgents;
                document.getElementById('k-rtn').textContent = s.routines;
                document.getElementById('k-enroute').textContent = s.en_route;
                document.getElementById('k-done').textContent = s.treated;
                const badge = document.getElementById('emg-nav-badge');
                if (s.emergencies > 0) { badge.textContent = s.emergencies; badge.style.display = 'flex'; }
                else { badge.style.display = 'none'; }
            } catch (e) { console.error('KPI failed', e); }
        }

        // â”€â”€ Patient list â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        async function loadPatients() {
            try {
                const pts = await api('/api/patients?sort=' + sortMode + '&limit=50');
                const countEl = document.getElementById('pt-count');
                if (countEl) countEl.textContent = pts.length + ' patient(s) in queue';
                renderPatientList(pts);
            } catch (e) {
                document.getElementById('patient-list').innerHTML =
                    '<div class="empty-state"><div class="empty-icon">âš ï¸</div><div class="empty-text">Unable to connect to server</div></div>';
            }
        }

        function renderPatientList(pts) {
            const el = document.getElementById('patient-list');
            if (!pts.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-icon">ðŸ“‹</div><div class="empty-text">No patients in queue</div></div>';
                return;
            }

            // Update cache
            pts.forEach(p => { if (p.patient_id) _patientCache[p.patient_id] = p; });

            // --- Smart diff: never destroy an existing card (would reset data-auto-hr and lose open tabs) ---
            const newIds = new Set(pts.map(p => p.patient_id).filter(Boolean));

            // 1. Remove cards that left the queue
            el.querySelectorAll('.pt-card[id^="card-"]').forEach(card => {
                const pid = card.id.slice(5);
                if (!newIds.has(pid)) card.remove();
            });

            // 2. For each incoming patient, add new card OR lightly update existing
            pts.forEach(p => {
                const pid = p.patient_id; if (!pid) return;
                const existing = document.getElementById('card-' + pid);

                if (existing) {
                    // Existing card: only patch the status pill â€” do NOT touch innerHTML (preserves open tabs)
                    const pill = existing.querySelector('.st-pill');
                    if (pill) {
                        pill.className = 'st-pill st-' + (p.status || 'incoming');
                        pill.textContent = STATUS_MAP[p.status] || p.status || 'Incoming';
                    }

                    // Patch ETA and Progress Bar from live updates
                    const etaEl = existing.querySelector('.pt-eta .eta-num');
                    const progEl = existing.querySelector('.pt-prog-fill');
                    if (etaEl) {
                        const eta = p.eta_minutes;
                        const etaTxt = eta ? (eta + ' min') : (p.arrival_time ? 'ARRIVED' : 'â€”');
                        const etaCls = eta && eta <= 5 ? 'crit' : eta && eta <= 15 ? 'urg' : 'ok';
                        etaEl.className = 'eta-num ' + etaCls;
                        etaEl.textContent = etaTxt;
                    }
                    if (progEl) {
                        const eta = p.eta_minutes;
                        const etaPct = eta ? Math.min(100, Math.max(3, 100 - (eta / 60) * 100)) : (p.arrival_time ? 100 : 0);
                        progEl.style.width = etaPct + '%';
                    }

                    // Maintain sort order
                    el.appendChild(existing);
                } else {
                    // New card: full render
                    const wrap = document.createElement('div');
                    wrap.innerHTML = buildCard(p);
                    const card = wrap.firstElementChild;
                    el.appendChild(card);
                    card.querySelectorAll('[data-toggle]').forEach(t =>
                        t.addEventListener('click', () => toggleDet(t.dataset.toggle)));
                    card.querySelectorAll('[data-dtab]').forEach(btn =>
                        btn.addEventListener('click', () => switchDtab(btn.dataset.pid, btn.dataset.dtab, btn)));
                }
            });
            // EMERGENCY ALERT EDGE GLOW
            const hasEmergency = pts.some(p => p.triage_level === 'EMERGENCY' && p.status === 'incoming');
            document.body.classList.toggle('emg-alert', hasEmergency);
        }

        function toggleDet(pid) {
            const det = document.getElementById('det-' + pid);
            const lbl = document.getElementById('exp-lbl-' + pid);
            const open = det.classList.toggle('open');
            if (lbl) lbl.textContent = open ? 'â–² Collapse' : 'â–¼ Full record';
        }

        function switchDtab(pid, tab, btnEl) {
            document.querySelectorAll('[data-pid="' + pid + '"].dtab').forEach(b => { b.classList.remove('text-blue-400', 'bg-blue-900/30', 'text-slate-900', 'bg-slate-200'); b.classList.add('text-slate-300', 'hover:bg-slate-800', 'hover:text-white', 'dark:text-slate-300'); b.querySelector('.absolute')?.remove(); });
            document.querySelectorAll('[data-ppid="' + pid + '"].dpane').forEach(p => p.classList.add('hidden'));
            btnEl.classList.add('active');
            const pane = document.getElementById('dp-' + pid + '-' + tab);
            if (pane) {
                pane.classList.add('active');
                // FIX: was checking 'health' but tab name is 'history'
                if (tab === 'history' && pane.dataset.autoHr === '1') {
                    pane.dataset.autoHr = '0';
                    const hn = pane.dataset.hn;
                    if (hn) {
                        loadHRInCard(hn, pid);
                    } else {
                        pane.innerHTML = '<div class="empty-state"><div class="empty-icon">ðŸªª</div><div class="empty-text">No health number on record</div></div>';
                    }
                }
            }
        }

        // â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        //  BUILD PATIENT CARD
        // â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
        function buildCard(p) {
  const tc = TC[p.triage_level] || 'R';
  const risk = p.risk_score;
  const rc = RC[p.triage_level] || '#10B981';
  const rp = risk != null ? Math.min(risk * 10, 100) : 0;
  const eta = p.eta_minutes;
  const etaf = eta != null ? eta + 'm ETA' : '';
  const name = p.full_name || p.patient_id;
  const pid = p.patient_id;
  const complaint = p.chief_complaint || p.complaint_text || 'No transcript recorded';
  const status = p.status || 'incoming';
  
  // Tailwind variants
  const barColors = { 'E':'bg-clinical-red', 'U':'bg-clinical-amber', 'R':'bg-clinical-emerald' };
  const badgeColors = { 
    'E':'bg-red-50 text-clinical-red border-red-200 dark:bg-red-900/20 dark:border-red-800', 
    'U':'bg-amber-50 text-clinical-amber border-amber-200 dark:bg-amber-900/20 dark:border-amber-800', 
    'R':'bg-emerald-50 text-clinical-emerald border-emerald-200 dark:bg-emerald-900/20 dark:border-emerald-800' 
  };
  const statusColors = {
    'incoming': 'bg-blue-100/50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 border-blue-200 dark:border-blue-800',
    'arrived': 'bg-emerald-100/50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800',
    'in_treatment': 'bg-purple-100/50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 border-purple-200 dark:border-purple-800',
    'discharged': 'bg-slate-100/50 text-slate-700 dark:bg-slate-800/50 dark:text-slate-400 border-slate-200 dark:border-slate-700'
  };
  const statusIcons = { 'incoming':'ambulance', 'arrived':'building', 'in_treatment':'stethoscope', 'discharged':'check-circle' };
  
  const statusLabel = {'incoming':'En Route','arrived':'Arrived','in_treatment':'In Treatment','discharged':'Discharged'}[status] || status;
  const lang = (p.language || '').split('-')[0].toUpperCase();
  const flag = FLAG[lang] || '';

  return `
  <div class="relative flex bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700 transition-all cursor-pointer group" onclick="openDetail('${pid}')" role="listitem">
    <!-- 5px Vertical Indicator Bar -->
    <div class="absolute left-0 top-0 bottom-0 w-[5px] ${barColors[tc]} z-10"></div>
    
    <div class="flex flex-1 p-4 pl-6 items-center gap-5">
      <!-- Avatar -->
      <div class="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 flex items-center justify-center shrink-0 overflow-hidden text-2xl shadow-inner">
         <img src="/api/patient_photo/${encodeURIComponent(p.health_number || pid)}" class="w-full h-full object-cover" onerror="this.parentElement.innerHTML='${p.sex === 'female' ? 'ðŸ‘©' : 'ðŸ‘¨'}'">
      </div>
      
      <!-- Patient Info -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
            <h3 class="font-bold text-lg text-slate-800 dark:text-slate-100 truncate pii">${h(name)}</h3>
            <span class="font-mono text-[10px] bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-slate-500 dark:text-slate-400 pii border border-slate-200 dark:border-slate-700">${h(pid)}</span>
        </div>
        <p class="text-sm text-slate-500 dark:text-slate-400 mt-1 line-clamp-1 flex items-center gap-1.5 object-contain">
            <i data-lucide="mic" class="w-3.5 h-3.5 shrink-0"></i>
            ${h(complaint)}
        </p>
        
        <!-- Tags Row -->
        <div class="flex items-center gap-2 mt-2.5 flex-wrap">
            <span class="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border ${statusColors[status]}">
                <i data-lucide="${statusIcons[status] || 'activity'}" class="w-3 h-3"></i> ${statusLabel}
            </span>
            ${etaf ? `<span class="flex items-center gap-1 bg-blue-50 text-blue-600 border border-blue-200 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800/50 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"><i data-lucide="clock" class="w-3 h-3"></i> ${etaf}</span>` : ''}
            ${flag ? `<span class="bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider">${flag} ${lang}</span>` : ''}
            ${(p.has_photo || p.photo_count > 0) ? `<span class="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"><i data-lucide="camera" class="w-3 h-3"></i> ${p.photo_count || 1}</span>` : ''}
        </div>
      </div>
      
      <!-- Triage Badge -->
      <div class="w-32 shrink-0 flex justify-center">
        <div class="border ${badgeColors[tc]} px-3 py-1 rounded-full text-xs font-bold tracking-wide flex items-center gap-1.5 shadow-sm">
            <i data-lucide="alert-circle" class="w-3.5 h-3.5"></i> ${tc === 'E' ? 'EMERGENCY' : tc === 'U' ? 'URGENT' : 'ROUTINE'}
        </div>
      </div>
      
      <!-- Risk Score -->
      <div class="w-32 shrink-0">
        <div class="flex items-center gap-3">
            <div class="flex-1 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-500" style="width:${rp}%;background:${rc}"></div>
            </div>
            <span class="font-mono text-xs font-bold" style="color:${rc}">${risk != null ? risk + '/10' : 'â€”'}</span>
        </div>
        <div class="text-[9px] font-bold text-slate-400 tracking-widest uppercase text-right mt-1.5">Risk Score</div>
      </div>
      
      <!-- Chevron -->
      <div class="pl-2 pr-1 text-slate-300 dark:text-slate-600 group-hover:text-blue-500 dark:group-hover:text-blue-400 transition-colors">
        <i data-lucide="chevron-right" class="w-5 h-5"></i>
      </div>
    </div>
  </div>`;
}
