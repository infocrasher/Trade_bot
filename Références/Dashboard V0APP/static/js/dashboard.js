/* =============================================
   ALGOTRADER DASHBOARD — dashboard.js
   All shared utilities: clock, status, table sort, toast
   ============================================= */

/* ---- Live Clock ---- */
function updateClock() {
  const el = document.getElementById('topbar-time');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toUTCString().replace('GMT', 'UTC').slice(5, 25);
}
updateClock();
setInterval(updateClock, 1000);

/* ---- Bot Status (mock: reads from a data attr or defaults to RUNNING) ---- */
(function initBotStatus() {
  const BOT_STATE = document.body.dataset.botState || 'running'; // running | paused | stopped
  const label     = { running: 'RUNNING', paused: 'PAUSED', stopped: 'STOPPED' }[BOT_STATE] || 'RUNNING';

  // Sidebar dot
  const sidebarDot   = document.getElementById('sidebar-status-dot');
  const sidebarLabel = document.getElementById('sidebar-status-label');
  if (sidebarDot) {
    sidebarDot.className = 'status-dot ' + BOT_STATE;
    sidebarLabel.textContent = label;
  }

  // Topbar badge
  const topbarBadge = document.getElementById('topbar-bot-status');
  if (topbarBadge) {
    const dot = topbarBadge.querySelector('.status-dot');
    if (dot) dot.className = 'status-dot ' + BOT_STATE;
    const span = topbarBadge.querySelector('span:last-child');
    if (span) span.textContent = label;
  }
})();

/* ---- Toast Notifications ---- */
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

/* ---- Sortable Tables ---- */
function initTableSort(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;

  const headers = table.querySelectorAll('thead th[data-col]');
  let sortedCol  = null;
  let sortAsc    = true;

  headers.forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;

      // Toggle direction
      if (sortedCol === col) {
        sortAsc = !sortAsc;
      } else {
        sortAsc    = true;
        sortedCol  = col;
      }

      // Update header classes
      headers.forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
      th.classList.add(sortAsc ? 'sorted-asc' : 'sorted-desc');

      // Sort rows
      const tbody = table.querySelector('tbody');
      const rows  = Array.from(tbody.querySelectorAll('tr'));
      const colIndex = Array.from(th.parentElement.children).indexOf(th);

      rows.sort((a, b) => {
        const aText = a.cells[colIndex]?.textContent.trim() || '';
        const bText = b.cells[colIndex]?.textContent.trim() || '';

        // Numeric sort if both look like numbers
        const aNum = parseFloat(aText.replace(/[^0-9.\-]/g, ''));
        const bNum = parseFloat(bText.replace(/[^0-9.\-]/g, ''));
        if (!isNaN(aNum) && !isNaN(bNum)) {
          return sortAsc ? aNum - bNum : bNum - aNum;
        }

        return sortAsc
          ? aText.localeCompare(bText)
          : bText.localeCompare(aText);
      });

      rows.forEach(r => tbody.appendChild(r));
    });
  });
}

/* ---- Auto-init sortable tables on page load ---- */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('table[id]').forEach(t => initTableSort(t.id));
});
