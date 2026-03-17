/* =============================================
   TAKEOPTION DASHBOARD — dashboard.js
   Fetch dynamique, Slide-in Panel, Utilitaires
   ============================================= */

let slideInOpen = false;

/* ---- Live Clock ---- */
function updateClock() {
  const el = document.getElementById('topbar-time');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toUTCString().replace('GMT', 'UTC').slice(5, 25);
}
updateClock();
setInterval(updateClock, 1000);

/* ---- Toasts ---- */
function showToast(message, type = 'info', duration = 3000) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const icons = {
    success: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`,
    error:   `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`,
    info:    `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`,
  };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('toast-out');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  }, duration);
}

/* ============================================================
   BOT STATUS
   Route : /api/state → {status, pairs_count, min_score, ...}
   ============================================================ */
let _currentBotStatus = 'stopped';

async function fetchBotStatus() {
  try {
    const res = await fetch('/api/state');
    if (!res.ok) throw new Error(res.status);
    return await res.json();
  } catch (err) {
    console.warn("Erreur /api/state:", err);
    return null;
  }
}

function updateStatusUIText(state) {
  if (!state) return;
  _currentBotStatus = state.status || 'stopped';

  const statusEl  = document.getElementById('sidebar-status-label');
  const topSpan   = document.querySelector('#topbar-bot-status span:last-child');
  const dots      = document.querySelectorAll('.status-dot');
  const pairsEl   = document.getElementById('topbar-pairs-count');

  const labels = { running: 'EN COURS', paused: 'EN PAUSE', stopped: 'ARRÊTÉ', waiting: 'EN ATTENTE' };
  const clsMap = { running: 'running', paused: 'paused', stopped: 'stopped', waiting: 'running' };
  const text   = labels[_currentBotStatus] || _currentBotStatus.toUpperCase();
  const cls    = clsMap[_currentBotStatus]  || 'stopped';

  if (statusEl) statusEl.textContent = text;
  if (topSpan)  topSpan.textContent  = text;
  dots.forEach(d => d.className = `status-dot ${cls}`);

  if (pairsEl && state.pairs_count !== undefined)
    pairsEl.textContent = `${state.pairs_count} paires actives`;

  /* Boutons de contrôle */
  const btnStart = document.getElementById('btn-bot-start');
  const btnPause = document.getElementById('btn-bot-pause');
  if (btnStart && btnPause) {
    const isRunning = _currentBotStatus === 'running' || _currentBotStatus === 'waiting';
    btnStart.style.display = isRunning ? 'none'   : 'inline-flex';
    btnPause.style.display = isRunning ? 'inline-flex' : 'none';
  }
}

/* ============================================================
   BOT CONTROLS  (Start / Pause / Stop)
   Routes: POST /api/start  /api/pause  /api/stop
   ============================================================ */
async function botAction(endpoint, confirmMsg) {
  if (confirmMsg && !confirm(confirmMsg)) return;
  try {
    const res = await fetch(endpoint, { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' });
    const ok = res.ok;
    if (ok) {
      const labels = { '/api/start': 'Bot démarré ✅', '/api/pause': 'Bot mis en pause ⏸', '/api/stop': 'Bot arrêté 🛑' };
      showToast(labels[endpoint] || 'OK', 'success');
      setTimeout(refreshCycle, 1000);
    } else {
      showToast(`Erreur ${endpoint} (${res.status})`, 'error');
    }
  } catch (e) {
    showToast(`Erreur réseau : ${e.message}`, 'error');
  }
}

/* ============================================================
   DASHBOARD : recupere les stats + l'historique
   Routes : GET /api/stats      → {day_pnl, win_rate, n_open, ...}
            GET /api/paper_history → [trade, ...]
   ============================================================ */
async function fetchDashboardData() {
  try {
    const [statsRes, histRes] = await Promise.all([
      fetch('/api/stats'),
      fetch('/api/paper_history'),
    ]);

    const stats  = statsRes.ok  ? await statsRes.json()  : null;
    const trades = histRes.ok   ? await histRes.json()   : [];

    renderSummaryCards(stats, trades);
    renderTradesTable(trades);
    renderSignalsList(trades);
  } catch(err) {
    console.error("Erreur fetch dashboard:", err);
  }
}

/* ---- Cards ---- */
function renderSummaryCards(stats, trades) {
  /* Stats en temps réel depuis /api/stats */
  if (stats) {
    const pnl = stats.day_pnl ?? 0;
    document.getElementById('sum-open-trades').textContent = (stats.n_open ?? 0).toString();
    document.getElementById('sum-win-rate').textContent    = `${stats.win_rate ?? 0}%`;
    document.getElementById('sum-win-rate-sub').textContent = `${stats.wins ?? 0} gains / ${stats.n_closed ?? 0} clos`;

    const pnlEl = document.getElementById('sum-day-pnl');
    if (pnlEl) {
      pnlEl.textContent  = `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}$`;
      pnlEl.className    = `card-value ${pnl > 0 ? 'positive' : (pnl < 0 ? 'negative' : 'neutral')}`;
    }
    const pnlSub = document.getElementById('sum-day-pnl-sub');
    if (pnlSub) pnlSub.textContent = `${stats.n_closed ?? 0} trades clos aujourd'hui`;
  }

  /* Compteur trades actifs depuis l'historique */
  const actives = trades.filter(t => t.status === 'active' || t.status === 'pending');
  const subEl = document.getElementById('sum-open-trades-sub');
  if (subEl) subEl.textContent = `${actives.filter(t=>t.direction==='LONG'||t.direction==='BUY'||t.direction==='ACHAT').length} long · ${actives.filter(t=>t.direction==='SHORT'||t.direction==='SELL'||t.direction==='VENTE').length} short`;
  const badge = document.getElementById('badge-active-trades-count');
  if (badge) badge.textContent = `${actives.length} ouverts`;
}

/* ---- Table Trades Actifs ---- */
function renderTradesTable(trades) {
  const actives = trades.filter(t => t.status === 'active' || t.status === 'pending');
  /* Diagnostic Log */
  const table = document.getElementById('active-trades-table');
  let tbody = table ? table.querySelector('tbody') : null;
  
  if (!tbody && table) {
    console.log("[Dashboard] Création d'un tbody dynamique car non trouvé dans le DOM");
    tbody = document.createElement('tbody');
    table.appendChild(tbody);
  }

  if (!tbody) {
    console.warn("[Dashboard] Table 'active-trades-table' introuvable !");
    return;
  }

  console.log(`[Dashboard] Rendu table actifs: ${actives.length} trades vers ${tbody.id || 'un tbody sans id'}`);
  tbody.innerHTML = '';

  if (actives.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--text-muted);">Aucun trade actif</td></tr>`;
    return;
  }
  actives.forEach(t => {
    const tr = document.createElement('tr');
    tr.className = 'clickable-row';
    tr.dataset.raw = JSON.stringify(t);
    // Mapping des vrais champs paper_trades.json
    const entry   = t.entry ?? t.entry_price ?? t.entry_trigger ?? '-';
    const sl      = t.sl    ?? t.stop_loss  ?? '-';
    const tp      = t.tp1   ?? t.take_profit ?? '-';
    const pnlPips = t.pnl_pips ?? t.pnl_r   ?? 0;
    const openAt  = t.opened_at ?? t.created_at ?? t.entry_time ?? '-';
    const profile = t.profile_id ?? (t.narrative && t.narrative.includes('MSS') ? 'Pure PA' : null) ?? 'Unknown';
    const pnlVal  = parseFloat(pnlPips || 0);
    const pnlFmt  = (pnlVal >= 0 ? '+' : '') + pnlVal.toFixed(1);
    const pnlCls  = pnlVal >= 0 ? 'pnl-pos' : 'pnl-neg';
    const dirBadge = (t.direction === 'LONG' || t.direction === 'BUY' || t.direction === 'ACHAT') ? 'badge-long' : 'badge-short';
    tr.innerHTML = `
      <td class="td-primary">${t.pair}</td>
      <td><span class="badge ${getBadgeClass(profile)}">${formatProfileName(profile)}</span></td>
      <td><span class="badge ${dirBadge}">${t.direction}</span></td>
      <td class="td-mono">${entry}</td>
      <td class="${pnlCls}">${pnlFmt} pips</td>
      <td class="td-mono">${sl}</td>
      <td class="td-mono">${tp}</td>
      <td class="td-mono">${openAt}</td>
    `;
    tr.addEventListener('click', () => openSlideIn({...t, profile_id: profile}, 'TRADE'));
    tbody.appendChild(tr);
  });
}

/* ---- Signaux Récents ---- */
function renderSignalsList(trades) {
  const sigList = document.querySelector('.signals-list');
  if (!sigList) return;
  sigList.innerHTML = '';

  const recents = [...trades].reverse().slice(0, 15);
  if (recents.length === 0) {
    sigList.innerHTML = `<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px;">Aucun historique récent</div>`;
    return;
  }
  recents.forEach(t => {
    const isActive = t.status === 'active' || t.status === 'pending' || t.status === 'closed';
    const badgeCls = isActive ? 'badge-approved' : 'badge-rejected';
    const txtApp   = t.status === 'closed' ? 'clôturé' : (isActive ? 'actif' : 'rejeté');
    const time = (t.opened_at ?? t.created_at ?? '').split(' ')[1]?.slice(0,5) ?? '--:--';
    const profile = t.profile_id ?? (t.narrative && t.narrative.includes('MSS') ? 'Pure PA' : null) ?? 'Unknown';
    const div = document.createElement('div');
    div.className = 'signal-item clickable-row';
    div.dataset.raw = JSON.stringify(t);
    div.innerHTML = `
      <span class="signal-pair">${t.pair}</span>
      <span class="badge ${getBadgeClass(profile)}" style="font-size:10px;padding:2px 7px;">${formatProfileName(profile, true)}</span>
      <span class="badge ${(t.direction==='LONG'||t.direction==='BUY'||t.direction==='ACHAT')?'badge-long':'badge-short'}" style="font-size:10px;padding:2px 7px;">${(t.direction==='LONG'||t.direction==='BUY'||t.direction==='ACHAT')?'L':'S'}</span>
      <span class="signal-score">${t.score ?? '--'}</span>
      <span class="badge ${badgeCls}">${txtApp}</span>
      <span class="signal-time">${time}</span>
    `;
    div.addEventListener('click', () => openSlideIn({...t, profile_id: profile}, 'SIGNAL'));
    sigList.appendChild(div);
  });
}

/* ---- Helpers UI ---- */
function getBadgeClass(profile) {
  if (!profile) return 'badge-legacy';
  const p = profile.toLowerCase();
  if (p.includes('ict'))     return 'badge-ict';
  if (p.includes('pa'))      return 'badge-pa';
  if (p.includes('elliott')) return 'badge-elliott';
  if (p.includes('vsa'))     return 'badge-vsa';
  return 'badge-legacy';
}
function formatProfileName(profile, short = false) {
  if (!profile) return short ? 'Unk' : 'Unknown';
  if (short) {
    if (profile.toLowerCase().includes('ict'))     return 'ICT';
    if (profile.toLowerCase().includes('pa'))      return 'PA';
    if (profile.toLowerCase().includes('elliott')) return 'ELT';
    if (profile.toLowerCase().includes('vsa'))     return 'VSA';
    return profile.substring(0, 3);
  }
  return profile;
}

/* ============================================================
   SLIDE-IN PANEL
   ============================================================ */
function openSlideIn(data, type) {
  slideInOpen = true;
  const panel = document.getElementById('slide-in-panel');
  if (!panel) return;
  panel.classList.add('open');
  document.getElementById('slide-in-title').textContent    = `${data.pair ?? '?'} · ${data.direction ?? '?'}`;
  document.getElementById('slide-in-subtitle').textContent = data.created_at ?? data.entry_time ?? 'Temps inconnu';

  /* Gates */
  const gatesCont = document.getElementById('slide-gates-container');
  gatesCont.innerHTML = '';
  if (data.active_gates?.length > 0) {
    data.active_gates.forEach(g => { gatesCont.innerHTML += `<span class="gate-badge">${g}</span>`; });
  } else {
    gatesCont.innerHTML = `<span class="text-muted" style="font-size:12px;">Aucun gate spécifié</span>`;
  }

  /* Convergence */
  document.getElementById('slide-convergence-state').textContent = data.convergence_state ?? 'Indépendant';
  document.getElementById('slide-profile-id').textContent        = data.profile_id ?? 'N/A';
  document.getElementById('slide-profile-version').textContent   = data.profile_version ? `v${data.profile_version}` : '--';

  /* TTL */
  const ttlBadge = document.getElementById('slide-ttl');
  if (data.ttl_seconds && data.status === 'pending') {
    ttlBadge.style.display = 'inline-flex';
    ttlBadge.textContent   = `TTL: ${data.ttl_seconds}s`;
  } else {
    ttlBadge.style.display = 'none';
  }

  /* Décision IA */
  const llmSection = document.getElementById('section-ai-decision');
  if (data.llm_decision) {
    llmSection.style.display = 'block';
    const b = document.getElementById('slide-ai-badge');
    b.textContent = data.llm_decision.decision;
    b.className   = `badge ${data.llm_decision.decision?.includes('approve') ? 'badge-approved' : 'badge-rejected'}`;
    document.getElementById('slide-ai-reason').textContent = data.llm_decision.reason ?? 'Aucune justification.';
  } else {
    llmSection.style.display = 'none';
  }

  /* Scores */
  const scoreSec = document.getElementById('section-scores');
  const scCont   = document.getElementById('slide-scores-container');
  if (data.scores_par_axe && Object.keys(data.scores_par_axe).length > 0) {
    scoreSec.style.display = 'block';
    scCont.innerHTML = '';
    for (const [ax, val] of Object.entries(data.scores_par_axe)) {
      scCont.innerHTML += `
        <div class="score-row">
          <span class="score-label">${ax}</span>
          <div class="score-bar-bg"><div class="score-bar-fill" style="width:${val}%;background:${val>60?'var(--green)':'var(--blue)'}"></div></div>
          <span class="score-value">${val}</span>
        </div>`;
    }
  } else {
    scoreSec.style.display = 'none';
  }

  /* Narrative */
  document.getElementById('slide-narrative-text').textContent = data.narrative ?? 'Aucune narrative textuelle associée.';
}

function closeSlideIn() {
  slideInOpen = false;
  const panel = document.getElementById('slide-in-panel');
  if (panel) panel.classList.remove('open');
}

document.addEventListener('DOMContentLoaded', () => {
  const closeBtn = document.getElementById('slide-in-close');
  if (closeBtn) closeBtn.addEventListener('click', closeSlideIn);

  document.addEventListener('click', (e) => {
    const panel = document.getElementById('slide-in-panel');
    if (slideInOpen && panel && !panel.contains(e.target) && !e.target.closest('.clickable-row')) {
      closeSlideIn();
    }
  });

  /* Boutons de contrôle */
  const btnStart = document.getElementById('btn-bot-start');
  const btnPause = document.getElementById('btn-bot-pause');
  const btnStop  = document.getElementById('btn-bot-stop');
  if (btnStart) btnStart.addEventListener('click', () => botAction('/api/start'));
  if (btnPause) btnPause.addEventListener('click', () => botAction('/api/pause'));
  if (btnStop)  btnStop.addEventListener('click',  () => botAction('/api/stop', '⛔ Arrêter le bot ? Cette action stoppera les cycles de trading.'));
});

/* ---- Sortable Tables ---- */
function initTableSort(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const headers = table.querySelectorAll('thead th[data-col]');
  let sortedCol = null, sortAsc = true;
  headers.forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (sortedCol === col) sortAsc = !sortAsc;
      else { sortAsc = true; sortedCol = col; }
      headers.forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
      th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');
      const tbody = table.querySelector('tbody');
      const rows  = Array.from(tbody.querySelectorAll('tr'));
      const idx   = Array.from(th.parentElement.children).indexOf(th);
      rows.sort((a, b) => {
        const aT = a.cells[idx]?.textContent.trim() || '';
        const bT = b.cells[idx]?.textContent.trim() || '';
        const aN = parseFloat(aT.replace(/[^0-9.\-]/g, ''));
        const bN = parseFloat(bT.replace(/[^0-9.\-]/g, ''));
        if (!isNaN(aN) && !isNaN(bN)) return sortAsc ? aN - bN : bN - aN;
        return sortAsc ? aT.localeCompare(bT) : bT.localeCompare(aT);
      });
      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

/* ============================================================
   MAIN REFRESH CYCLE
   ============================================================ */
async function refreshCycle() {
  const state = await fetchBotStatus();
  updateStatusUIText(state);

  /* Fetch Dashboard data seulement si on est sur la page principale */
  if (document.getElementById('active-trades-table')) {
    await fetchDashboardData();
    initTableSort('active-trades-table');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  refreshCycle();
  setInterval(refreshCycle, 10000);
});
