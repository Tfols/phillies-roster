/* ── Phillies Roster App ─────────────────────────────────────────────────── */
'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let allPlayers = [];
let sortCol   = 'full_name';
let sortAsc   = true;

// ── DOM refs ───────────────────────────────────────────────────────────────
const tbody       = document.getElementById('playerBody');
const searchInput = document.getElementById('searchInput');
const posFilter   = document.getElementById('posFilter');
const yearInput   = document.getElementById('yearInput');
const statusFilt  = document.getElementById('statusFilter');
const clearBtn    = document.getElementById('clearBtn');
const rosterCount = document.getElementById('rosterCount');
const toast       = document.getElementById('toast');

// Stats bar
const statTotal    = document.getElementById('statTotal');
const statHave     = document.getElementById('statHave');
const statSigned   = document.getElementById('statSigned');
const statDont     = document.getElementById('statDont');
const statNoAuto   = document.getElementById('statNoAuto');
const statInPerson = document.getElementById('statInPerson');

// ── Bootstrap ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadPlayers();
  setupFilters();
  setupSort();
  registerSW();
});

// ── Load all players once ──────────────────────────────────────────────────
async function loadPlayers() {
  showLoading(true);
  try {
    const res = await fetch('/api/players');
    if (!res.ok) throw new Error(res.statusText);
    allPlayers = await res.json();
    populatePositionFilter();
    render();
    updateGlobalStats();
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">Failed to load roster. Please refresh.</td></tr>`;
  }
  showLoading(false);
}

// ── Populate position dropdown ─────────────────────────────────────────────
function populatePositionFilter() {
  const positions = [...new Set(allPlayers.map(p => p.position).filter(Boolean))].sort();
  positions.forEach(pos => {
    const opt = document.createElement('option');
    opt.value = pos;
    opt.textContent = pos;
    posFilter.appendChild(opt);
  });
}

// ── Filter + sort ──────────────────────────────────────────────────────────
function getFiltered() {
  const search = searchInput.value.trim().toLowerCase();
  const pos    = posFilter.value;
  const year   = parseInt(yearInput.value, 10) || null;
  const status = statusFilt.value;

  let list = allPlayers.filter(p => {
    if (search && !p.full_name.toLowerCase().includes(search)) return false;
    if (pos    && p.position !== pos) return false;
    if (year   && !(p.year_start <= year && p.year_end >= year)) return false;
    if (status && p.collection_status !== status) return false;
    return true;
  });

  // Sort
  list.sort((a, b) => {
    let va = a[sortCol] ?? '';
    let vb = b[sortCol] ?? '';
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return sortAsc ? -1 :  1;
    if (va > vb) return sortAsc ?  1 : -1;
    return 0;
  });

  return list;
}

// ── Render table ───────────────────────────────────────────────────────────
function render() {
  const players = getFiltered();
  rosterCount.innerHTML = `Showing <strong>${players.length.toLocaleString()}</strong> of <strong>${allPlayers.length.toLocaleString()}</strong> players`;

  if (players.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">No players match your filters.</td></tr>`;
    return;
  }

  const rows = players.map(p => `
    <tr data-id="${p.id}">
      <td class="col-photo">${avatarHTML(p)}</td>
      <td class="player-name">${esc(p.full_name)}</td>
      <td><span class="pos-badge">${esc(p.position || '—')}</span></td>
      <td>${esc(p.years_active || '—')}</td>
      <td>${statusSelectHTML(p)}</td>
    </tr>
  `).join('');

  tbody.innerHTML = rows;

  // Attach status-change listeners
  tbody.querySelectorAll('.status-select').forEach(sel => {
    sel.addEventListener('change', onStatusChange);
  });
}

// ── Avatar ─────────────────────────────────────────────────────────────────
function avatarHTML(p) {
  const initials = p.full_name
    .split(' ').filter(Boolean).map(w => w[0]).slice(0, 2).join('');

  // Initials div always present as background; image absolutely overlays it.
  // On error the image hides itself, revealing initials cleanly.
  const img = p.photo_url
    ? `<img class="avatar-img" src="${esc(p.photo_url)}" alt="" loading="lazy" onerror="this.style.display='none'">`
    : '';
  return `<div class="avatar-wrap">${img}<div class="avatar-initials">${esc(initials)}</div></div>`;
}

// ── Status select HTML ─────────────────────────────────────────────────────
const STATUS_CLASS = {
  'Have':             'status-have',
  'Have Signed':      'status-signed',
  "Don't Have":       'status-dont',
  'No Auto Available':'status-no-auto',
  'In Person':        'status-in-person',
};

function statusSelectHTML(p) {
  const cls = STATUS_CLASS[p.collection_status] || 'status-dont';
  const opts = ["Don't Have", 'Have', 'Have Signed', 'No Auto Available', 'In Person']
    .map(s => `<option value="${s}"${s === p.collection_status ? ' selected' : ''}>${s}</option>`)
    .join('');
  return `<select class="status-select ${cls}" data-id="${p.id}">${opts}</select>`;
}

// ── Status change via PATCH ────────────────────────────────────────────────
async function onStatusChange(e) {
  const sel      = e.target;
  const id       = sel.dataset.id;
  const status   = sel.value;
  const prevClass = [...sel.classList].find(c => c.startsWith('status-'));

  // Optimistic UI
  sel.classList.remove(prevClass);
  sel.classList.add(STATUS_CLASS[status]);

  // Update local array
  const player = allPlayers.find(p => p.id == id);
  if (player) player.collection_status = status;
  updateGlobalStats();

  try {
    const res = await fetch(`/api/players/${id}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error('Save failed');
    showToast(`${player?.full_name ?? 'Player'} → ${status}`);
  } catch {
    // Revert
    if (player) player.collection_status = prevClass; // crude revert
    showToast('Error saving — please retry', true);
    sel.classList.remove(STATUS_CLASS[status]);
    sel.classList.add(prevClass);
  }
}

// ── Global stats bar ───────────────────────────────────────────────────────
function updateGlobalStats() {
  const have     = allPlayers.filter(p => p.collection_status === 'Have').length;
  const signed   = allPlayers.filter(p => p.collection_status === 'Have Signed').length;
  const dont     = allPlayers.filter(p => p.collection_status === "Don't Have").length;
  const noAuto   = allPlayers.filter(p => p.collection_status === 'No Auto Available').length;
  const inPerson = allPlayers.filter(p => p.collection_status === 'In Person').length;
  statTotal.textContent    = allPlayers.length.toLocaleString();
  statHave.textContent     = have.toLocaleString();
  statSigned.textContent   = signed.toLocaleString();
  statDont.textContent     = dont.toLocaleString();
  statNoAuto.textContent   = noAuto.toLocaleString();
  statInPerson.textContent = inPerson.toLocaleString();
}

// ── Filters & sort event wiring ────────────────────────────────────────────
function setupFilters() {
  let debounceTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(render, 200);
  });
  posFilter.addEventListener('change', render);
  yearInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(render, 300);
  });
  statusFilt.addEventListener('change', render);
  clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    posFilter.value   = '';
    yearInput.value   = '';
    statusFilt.value  = '';
    render();
  });
}

function setupSort() {
  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (sortCol === col) {
        sortAsc = !sortAsc;
      } else {
        sortCol = col;
        sortAsc = true;
      }
      // Update header indicators
      document.querySelectorAll('th.sortable').forEach(t => {
        t.classList.remove('sort-active');
        t.querySelector('.sort-icon').className = 'sort-icon';
      });
      th.classList.add('sort-active');
      const icon = th.querySelector('.sort-icon');
      icon.className = `sort-icon ${sortAsc ? 'asc' : 'desc'}`;
      render();
    });
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────
function showLoading(on) {
  if (on) {
    tbody.innerHTML = `<tr class="loading-row"><td colspan="5"><span class="spinner"></span>Loading roster…</td></tr>`;
  }
}

function showToast(msg, error = false) {
  toast.textContent = msg;
  toast.style.background = error ? '#991b1b' : 'var(--navy)';
  toast.classList.add('show');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 2800);
}

function esc(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

// ── Service Worker registration ────────────────────────────────────────────
function registerSW() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js')
      .catch(err => console.warn('SW registration failed:', err));
  }
}
