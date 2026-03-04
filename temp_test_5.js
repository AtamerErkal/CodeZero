
        // â•â• MEDIA LIGHTBOX + VIDEO THUMBNAIL â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

        function replaceWithVideoThumb(pid, idx, container) {
            fetch(`/api/illness_photo/${encodeURIComponent(pid)}/${idx}/type`)
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (!data) { container.style.display = 'none'; return; }
                    if (data.kind === 'video') {
                        container.innerHTML = `
          <video src="/api/illness_photo/${encodeURIComponent(pid)}/${idx}"
                 style="width:100%;height:100%;object-fit:cover;"
                 muted preload="metadata"
                 onloadedmetadata="this.currentTime=1">
          </video>
          <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;">
            <div style="background:rgba(0,0,0,.55);border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;">
              <span style="color:#fff;font-size:1rem;margin-left:3px;">â–¶</span>
            </div>
          </div>`;
                        container.setAttribute('onclick',
                            `openMediaLightbox('/api/illness_photo/${encodeURIComponent(pid)}/${idx}','${pid}',${idx})`);
                    } else {
                        container.style.display = 'none';
                    }
                })
                .catch(() => { container.style.display = 'none'; });
        }

        let _lbPid = null, _lbIdx = 0, _lbCount = 0;

        async function openMediaLightbox(url, pid, idx) {
            _lbPid = pid;
            _lbIdx = idx;
            if (_lbCount === 0 || _lbPid !== pid) {
                _lbCount = 0;
                for (let i = 0; i < 10; i++) {
                    try {
                        const r = await fetch(`/api/illness_photo/${encodeURIComponent(pid)}/${i}/type`);
                        if (!r.ok) break;
                        _lbCount = i + 1;
                    } catch { break; }
                }
            }
            _renderLightboxItem(pid, idx);
            const lb = document.getElementById('mediaLightbox');
            lb.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        function closeMediaLightbox() {
            document.getElementById('mediaLightbox').style.display = 'none';
            document.getElementById('mediaLightboxContent').innerHTML = '';
            document.body.style.overflow = '';
            _lbCount = 0;
        }

        async function _renderLightboxItem(pid, idx) {
            const content = document.getElementById('mediaLightboxContent');
            const nav = document.getElementById('mediaLightboxNav');
            content.innerHTML = '<div style="color:#fff;font-size:2rem">â³</div>';
            nav.innerHTML = '';
            try {
                const r = await fetch(`/api/illness_photo/${encodeURIComponent(pid)}/${idx}/type`);
                const data = r.ok ? await r.json() : null;
                const url = `/api/illness_photo/${encodeURIComponent(pid)}/${idx}`;
                if (data && data.kind === 'video') {
                    content.innerHTML = `<video src="${url}" controls autoplay
        style="max-width:90vw;max-height:78vh;border-radius:12px;background:#000;box-shadow:0 8px 40px rgba(0,0,0,.6);">
        Your browser does not support video.</video>`;
                } else {
                    content.innerHTML = `<img src="${url}" alt="Media ${idx + 1}"
        style="max-width:90vw;max-height:78vh;border-radius:12px;object-fit:contain;box-shadow:0 8px 40px rgba(0,0,0,.6);">`;
                }
            } catch {
                content.innerHTML = '<div style="color:#f87171;font-size:1rem;">Failed to load media</div>';
            }
            if (_lbCount > 1) {
                nav.innerHTML = `
      <button onclick="_navLightbox(-1)" style="background:rgba(255,255,255,.15);border:none;color:#fff;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:1.2rem;">â€¹</button>
      <div style="display:flex;gap:6px;align-items:center;">
        ${Array.from({ length: _lbCount }, (_, i) => `
          <div onclick="_navLightbox(${i - idx})" style="
            width:${i === idx ? '22px' : '8px'};height:8px;border-radius:99px;cursor:pointer;transition:all .2s;
            background:${i === idx ? '#fff' : 'rgba(255,255,255,.4)'};"></div>`).join('')}
      </div>
      <button onclick="_navLightbox(1)" style="background:rgba(255,255,255,.15);border:none;color:#fff;width:40px;height:40px;border-radius:50%;cursor:pointer;font-size:1.2rem;">â€º</button>`;
            }
        }

        function _navLightbox(delta) {
            _lbIdx = ((_lbIdx + delta) + _lbCount) % _lbCount;
            _renderLightboxItem(_lbPid, _lbIdx);
        }

        document.addEventListener('keydown', e => {
            if (document.getElementById('mediaLightbox').style.display === 'none') return;
            if (e.key === 'Escape') closeMediaLightbox();
            if (e.key === 'ArrowRight') _navLightbox(1);
            if (e.key === 'ArrowLeft') _navLightbox(-1);
        });

        // DARK MODE TOGGLE
        function toggleTheme() {
            const html = document.documentElement;
            html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
        }

        let selectedCardIdx = -1;
        document.addEventListener('keydown', e => {
            if (currentTab !== 'incoming') return;
            const cards = Array.from(document.querySelectorAll('.pt-card'));
            if (!cards.length) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (selectedCardIdx < cards.length - 1) selectedCardIdx++;
                highlightCard(cards);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (selectedCardIdx > 0) selectedCardIdx--;
                highlightCard(cards);
            } else if (e.key === 'Enter' && selectedCardIdx > -1) {
                e.preventDefault();
                const pid = cards[selectedCardIdx].id.replace('card-', '');
                toggleDet(pid);
            } else if (e.key === 'Escape') {
                document.querySelectorAll('.pt-det').forEach(d => d.classList.remove('open'));
            }
        });

        function highlightCard(cards) {
            cards.forEach((c, i) => {
                if (i === selectedCardIdx) {
                    c.style.transform = 'translateX(10px)';
                    c.style.boxShadow = 'var(--shadow-md)';
                    c.style.borderColor = 'var(--blue2)';
                    c.scrollIntoView({ behavior: 'smooth', block: 'center' });
                } else {
                    c.style.transform = 'none';
                    c.style.boxShadow = 'var(--shadow-sm)';
                    c.style.borderColor = 'var(--border)';
                }
            });
        }
    