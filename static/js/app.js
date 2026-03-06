/* ── Phillies Roster App ─────────────────────────────────────────────────── */
'use strict';

// ── Shared helpers ──────────────────────────────────────────────────────────
const STATUS_CLASS = {
  'Have':             'status-have',
  'Have Signed':      'status-signed',
  "Don't Have":       'status-dont',
  'No Auto Available':'status-no-auto',
  'In Person':        'status-in-person',
};

function esc(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showToast(msg, error = false) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.style.background = error ? '#991b1b' : 'var(--navy)';
  toast.classList.add('show');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 2800);
}

function avatarHTML(p) {
  const initials = p.full_name.split(' ').filter(Boolean).map(w => w[0]).slice(0, 2).join('');
  const img = p.photo_url
    ? `<img class="avatar-img" src="${esc(p.photo_url)}" alt="" loading="lazy" onerror="this.style.display='none'">`
    : '';
  return `<div class="avatar-wrap">${img}<div class="avatar-initials">${esc(initials)}</div></div>`;
}

function statusSelectHTML(p, apiPrefix) {
  const cls  = STATUS_CLASS[p.collection_status] || 'status-dont';
  const opts = ["Don't Have", 'Have', 'Have Signed', 'No Auto Available', 'In Person']
    .map(s => `<option value="${s}"${s === p.collection_status ? ' selected' : ''}>${s}</option>`)
    .join('');
  return `<select class="status-select ${cls}" data-id="${p.id}" data-api="${apiPrefix}">${opts}</select>`;
}

function makeDropdownLabel(menu, btn) {
  const checked = [...menu.querySelectorAll('input[type="checkbox"]:checked')];
  if (checked.length === 0) {
    btn.querySelector('.dd-label').textContent = 'All Statuses';
    btn.classList.remove('active');
  } else if (checked.length === 1) {
    btn.querySelector('.dd-label').textContent = checked[0].value;
    btn.classList.add('active');
  } else {
    btn.querySelector('.dd-label').textContent = `Status (${checked.length})`;
    btn.classList.add('active');
  }
}

function clearDropdown(menu, btn) {
  menu.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
  makeDropdownLabel(menu, btn);
}

function wireDropdown(btn, menu, onChange) {
  btn.innerHTML = '<span class="dd-label">All Statuses</span> <span class="dd-arrow">▾</span>';
  btn.addEventListener('click', e => { e.stopPropagation(); menu.classList.toggle('open'); });
  menu.addEventListener('change', () => { makeDropdownLabel(menu, btn); onChange(); });
  document.addEventListener('click', e => {
    if (!btn.contains(e.target) && !menu.contains(e.target))
      menu.classList.remove('open');
  });
}

// Universal status-change handler (works for both MLB and minor league rows)
async function onStatusChange(e) {
  const sel       = e.target;
  const id        = sel.dataset.id;
  const api       = sel.dataset.api;           // 'players' or 'minors'
  const status    = sel.value;
  const prevClass = [...sel.classList].find(c => c.startsWith('status-'));

  sel.classList.remove(prevClass);
  sel.classList.add(STATUS_CLASS[status]);

  const arr     = api === 'minors' ? allMinors : allPlayers;
  const player  = arr.find(p => p.id == id);
  if (player) player.collection_status = status;

  if (api === 'minors') updateMinorStats(); else updateGlobalStats();

  try {
    const res = await fetch(`/api/${api}/${id}/status`, {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error('Save failed');
    showToast(`${player?.full_name ?? 'Player'} → ${status}`);
  } catch {
    if (player) player.collection_status = prevClass;
    showToast('Error saving — please retry', true);
    sel.classList.remove(STATUS_CLASS[status]);
    sel.classList.add(prevClass);
  }
}

// ════════════════════════════════════════════════════════════════════════════
//  MLB ROSTER
// ════════════════════════════════════════════════════════════════════════════

let allPlayers = [];
let sortCol    = 'full_name';
let sortAsc    = true;

const tbody       = document.getElementById('playerBody');
const searchInput = document.getElementById('searchInput');
const posFilter   = document.getElementById('posFilter');
const yearInput   = document.getElementById('yearInput');
const mlbDDBtn    = document.getElementById('statusDropdownBtn');
const mlbDDMenu   = document.getElementById('statusDropdownMenu');
const clearBtn    = document.getElementById('clearBtn');
const rosterCount = document.getElementById('rosterCount');

const statTotal    = document.getElementById('statTotal');
const statHave     = document.getElementById('statHave');
const statSigned   = document.getElementById('statSigned');
const statDont     = document.getElementById('statDont');
const statNoAuto   = document.getElementById('statNoAuto');
const statInPerson = document.getElementById('statInPerson');

async function loadPlayers() {
  tbody.innerHTML = `<tr class="loading-row"><td colspan="5"><span class="spinner"></span>Loading roster…</td></tr>`;
  try {
    const res = await fetch('/api/players');
    if (!res.ok) throw new Error(res.statusText);
    allPlayers = await res.json();
    populatePositionFilter(posFilter, allPlayers);
    render();
    updateGlobalStats();
  } catch {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">Failed to load roster. Please refresh.</td></tr>`;
  }
}

function populatePositionFilter(select, players) {
  const positions = [...new Set(players.map(p => p.position).filter(Boolean))].sort();
  positions.forEach(pos => {
    const opt = document.createElement('option');
    opt.value = opt.textContent = pos;
    select.appendChild(opt);
  });
}

function getFiltered() {
  const search   = searchInput.value.trim().toLowerCase();
  const pos      = posFilter.value;
  const year     = parseInt(yearInput.value, 10) || null;
  const statuses = new Set(
    [...mlbDDMenu.querySelectorAll('input[type="checkbox"]:checked')].map(cb => cb.value)
  );
  let list = allPlayers.filter(p => {
    if (search && !p.full_name.toLowerCase().includes(search)) return false;
    if (pos    && p.position !== pos) return false;
    if (year   && !(p.year_start <= year && p.year_end >= year)) return false;
    if (statuses.size > 0 && !statuses.has(p.collection_status)) return false;
    return true;
  });
  list.sort((a, b) => {
    let va = a[sortCol] ?? '', vb = b[sortCol] ?? '';
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return sortAsc ? -1 :  1;
    if (va > vb) return sortAsc ?  1 : -1;
    return 0;
  });
  return list;
}

function render() {
  const players = getFiltered();
  rosterCount.innerHTML = `Showing <strong>${players.length.toLocaleString()}</strong> of <strong>${allPlayers.length.toLocaleString()}</strong> players`;
  if (players.length === 0) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="5">No players match your filters.</td></tr>`;
    return;
  }
  tbody.innerHTML = players.map(p => `
    <tr data-id="${p.id}">
      <td class="col-photo">${avatarHTML(p)}</td>
      <td class="player-name">${esc(p.full_name)}</td>
      <td><span class="pos-badge">${esc(p.position || '—')}</span></td>
      <td>${esc(p.years_active || '—')}</td>
      <td>${statusSelectHTML(p, 'players')}</td>
    </tr>
  `).join('');
  tbody.querySelectorAll('.status-select').forEach(sel => sel.addEventListener('change', onStatusChange));
}

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

function applyStatFilter(status) {
  clearDropdown(mlbDDMenu, mlbDDBtn);
  if (status) {
    const cb = [...mlbDDMenu.querySelectorAll('input[type="checkbox"]')].find(c => c.value === status);
    if (cb) { cb.checked = true; makeDropdownLabel(mlbDDMenu, mlbDDBtn); }
  }
  document.querySelectorAll('#panel-mlb .stats-bar span[data-filter]').forEach(s =>
    s.classList.toggle('stat-active', s.dataset.filter === status)
  );
  render();
}

function setupMLBFilters() {
  let t;
  wireDropdown(mlbDDBtn, mlbDDMenu, () => {
    document.querySelectorAll('#panel-mlb .stats-bar span[data-filter]').forEach(s => s.classList.remove('stat-active'));
    render();
  });
  searchInput.addEventListener('input', () => { clearTimeout(t); t = setTimeout(render, 200); });
  posFilter.addEventListener('change', render);
  yearInput.addEventListener('input',  () => { clearTimeout(t); t = setTimeout(render, 300); });
  document.querySelector('#panel-mlb .stats-bar').addEventListener('click', e => {
    const span = e.target.closest('[data-filter]');
    if (span) applyStatFilter(span.dataset.filter);
  });
  clearBtn.addEventListener('click', () => {
    searchInput.value = ''; posFilter.value = ''; yearInput.value = '';
    clearDropdown(mlbDDMenu, mlbDDBtn);
    document.querySelectorAll('#panel-mlb .stats-bar span[data-filter]').forEach(s => s.classList.remove('stat-active'));
    render();
  });
}

function setupMLBSort() {
  document.querySelectorAll('#panel-mlb th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      sortAsc = sortCol === col ? !sortAsc : true;
      sortCol = col;
      document.querySelectorAll('#panel-mlb th.sortable').forEach(t => {
        t.classList.remove('sort-active');
        t.querySelector('.sort-icon').className = 'sort-icon';
      });
      th.classList.add('sort-active');
      th.querySelector('.sort-icon').className = `sort-icon ${sortAsc ? 'asc' : 'desc'}`;
      render();
    });
  });
}

// ════════════════════════════════════════════════════════════════════════════
//  MINOR LEAGUE
// ════════════════════════════════════════════════════════════════════════════

let allMinors      = [];
let minorSortCol   = 'full_name';
let minorSortAsc   = true;
let minorsLoaded   = false;

const minorTbody         = document.getElementById('minorBody');
const minorSearchInput   = document.getElementById('minorSearchInput');
const minorPosFilter     = document.getElementById('minorPosFilter');
const minorLevelFilter   = document.getElementById('minorLevelFilter');
const minorAffFilter     = document.getElementById('minorAffiliateFilter');
const minorYearInput     = document.getElementById('minorYearInput');
const minorDDBtn         = document.getElementById('minorStatusDropdownBtn');
const minorDDMenu        = document.getElementById('minorStatusDropdownMenu');
const minorClearBtn      = document.getElementById('minorClearBtn');
const minorRosterCount   = document.getElementById('minorRosterCount');

const minorStatTotal    = document.getElementById('minorStatTotal');
const minorStatHave     = document.getElementById('minorStatHave');
const minorStatSigned   = document.getElementById('minorStatSigned');
const minorStatDont     = document.getElementById('minorStatDont');
const minorStatNoAuto   = document.getElementById('minorStatNoAuto');
const minorStatInPerson = document.getElementById('minorStatInPerson');

async function loadMinors() {
  minorTbody.innerHTML = `<tr class="loading-row"><td colspan="7"><span class="spinner"></span>Loading minor league roster…</td></tr>`;
  try {
    const [playersRes, affsRes] = await Promise.all([
      fetch('/api/minors'),
      fetch('/api/affiliates'),
    ]);
    if (!playersRes.ok) throw new Error(playersRes.statusText);
    allMinors      = await playersRes.json();
    const affiliates = affsRes.ok ? await affsRes.json() : [];

    populateMinorFilters(affiliates);
    renderMinors();
    updateMinorStats();
    minorsLoaded = true;
  } catch {
    minorTbody.innerHTML = `<tr class="empty-row"><td colspan="7">Failed to load minor league data. Please refresh.</td></tr>`;
  }
}

function populateMinorFilters(affiliates) {
  // Positions from data
  const positions = [...new Set(allMinors.map(p => p.position).filter(Boolean))].sort();
  positions.forEach(pos => {
    const opt = document.createElement('option');
    opt.value = opt.textContent = pos;
    minorPosFilter.appendChild(opt);
  });

  // Affiliates from data (unique names, sorted)
  const affNames = [...new Set(allMinors.map(p => p.affiliate_name).filter(Boolean))].sort();
  affNames.forEach(name => {
    const opt = document.createElement('option');
    opt.value = opt.textContent = name;
    minorAffFilter.appendChild(opt);
  });
}

function getMinorFiltered() {
  const search   = minorSearchInput.value.trim().toLowerCase();
  const pos      = minorPosFilter.value;
  const level    = minorLevelFilter.value;
  const aff      = minorAffFilter.value;
  const year     = parseInt(minorYearInput.value, 10) || null;
  const statuses = new Set(
    [...minorDDMenu.querySelectorAll('input[type="checkbox"]:checked')].map(cb => cb.value)
  );

  let list = allMinors.filter(p => {
    if (search && !p.full_name.toLowerCase().includes(search)) return false;
    if (pos   && p.position !== pos) return false;
    if (level && p.level !== level) return false;
    if (aff   && p.affiliate_name !== aff) return false;
    if (year  && !(p.year_start <= year && p.year_end >= year)) return false;
    if (statuses.size > 0 && !statuses.has(p.collection_status)) return false;
    return true;
  });

  list.sort((a, b) => {
    let va = a[minorSortCol] ?? '', vb = b[minorSortCol] ?? '';
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return minorSortAsc ? -1 :  1;
    if (va > vb) return minorSortAsc ?  1 : -1;
    return 0;
  });

  return list;
}

function renderMinors() {
  const players = getMinorFiltered();
  minorRosterCount.innerHTML = `Showing <strong>${players.length.toLocaleString()}</strong> of <strong>${allMinors.length.toLocaleString()}</strong> players`;

  if (players.length === 0) {
    if (allMinors.length === 0) {
      minorTbody.innerHTML = `<tr class="empty-row"><td colspan="7">No minor league data yet. Run <code>railway run python import_minors.py</code> to import.</td></tr>`;
    } else {
      minorTbody.innerHTML = `<tr class="empty-row"><td colspan="7">No players match your filters.</td></tr>`;
    }
    return;
  }

  minorTbody.innerHTML = players.map(p => `
    <tr data-id="${p.id}">
      <td class="col-photo">${avatarHTML(p)}</td>
      <td class="player-name">${esc(p.full_name)}</td>
      <td><span class="pos-badge">${esc(p.position || '—')}</span></td>
      <td><span class="level-badge level-${esc(p.level.toLowerCase().replace(/[^a-z]/g,'-'))}">${esc(p.level || '—')}</span></td>
      <td class="col-affiliate">${esc(p.affiliate_name || '—')}</td>
      <td>${esc(p.years_active || '—')}</td>
      <td>${statusSelectHTML(p, 'minors')}</td>
    </tr>
  `).join('');
  minorTbody.querySelectorAll('.status-select').forEach(sel => sel.addEventListener('change', onStatusChange));
}

function updateMinorStats() {
  const have     = allMinors.filter(p => p.collection_status === 'Have').length;
  const signed   = allMinors.filter(p => p.collection_status === 'Have Signed').length;
  const dont     = allMinors.filter(p => p.collection_status === "Don't Have").length;
  const noAuto   = allMinors.filter(p => p.collection_status === 'No Auto Available').length;
  const inPerson = allMinors.filter(p => p.collection_status === 'In Person').length;
  minorStatTotal.textContent    = allMinors.length.toLocaleString();
  minorStatHave.textContent     = have.toLocaleString();
  minorStatSigned.textContent   = signed.toLocaleString();
  minorStatDont.textContent     = dont.toLocaleString();
  minorStatNoAuto.textContent   = noAuto.toLocaleString();
  minorStatInPerson.textContent = inPerson.toLocaleString();
}

function applyMinorStatFilter(status) {
  clearDropdown(minorDDMenu, minorDDBtn);
  if (status) {
    const cb = [...minorDDMenu.querySelectorAll('input[type="checkbox"]')].find(c => c.value === status);
    if (cb) { cb.checked = true; makeDropdownLabel(minorDDMenu, minorDDBtn); }
  }
  document.querySelectorAll('#panel-minors .stats-bar span[data-minor-filter]').forEach(s =>
    s.classList.toggle('stat-active', s.dataset.minorFilter === status)
  );
  renderMinors();
}

function setupMinorFilters() {
  let t;
  wireDropdown(minorDDBtn, minorDDMenu, () => {
    document.querySelectorAll('#panel-minors .stats-bar span[data-minor-filter]').forEach(s => s.classList.remove('stat-active'));
    renderMinors();
  });
  minorSearchInput.addEventListener('input',  () => { clearTimeout(t); t = setTimeout(renderMinors, 200); });
  minorPosFilter.addEventListener('change',   renderMinors);
  minorLevelFilter.addEventListener('change', renderMinors);
  minorAffFilter.addEventListener('change',   renderMinors);
  minorYearInput.addEventListener('input',    () => { clearTimeout(t); t = setTimeout(renderMinors, 300); });

  document.querySelector('#panel-minors .stats-bar').addEventListener('click', e => {
    const span = e.target.closest('[data-minor-filter]');
    if (span) applyMinorStatFilter(span.dataset.minorFilter);
  });

  minorClearBtn.addEventListener('click', () => {
    minorSearchInput.value = ''; minorPosFilter.value = ''; minorLevelFilter.value = '';
    minorAffFilter.value = ''; minorYearInput.value = '';
    clearDropdown(minorDDMenu, minorDDBtn);
    document.querySelectorAll('#panel-minors .stats-bar span[data-minor-filter]').forEach(s => s.classList.remove('stat-active'));
    renderMinors();
  });
}

function setupMinorSort() {
  document.querySelectorAll('#panel-minors th.minor-sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      minorSortAsc = minorSortCol === col ? !minorSortAsc : true;
      minorSortCol = col;
      document.querySelectorAll('#panel-minors th.minor-sortable').forEach(t => {
        t.classList.remove('sort-active');
        t.querySelector('.sort-icon').className = 'sort-icon';
      });
      th.classList.add('sort-active');
      th.querySelector('.sort-icon').className = `sort-icon ${minorSortAsc ? 'asc' : 'desc'}`;
      renderMinors();
    });
  });
}

// ════════════════════════════════════════════════════════════════════════════
//  TAB SWITCHING
// ════════════════════════════════════════════════════════════════════════════

function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
      document.querySelectorAll('.tab-panel').forEach(p => { p.hidden = p.id !== `panel-${tab}`; });
      if (tab === 'minors' && !minorsLoaded) {
        loadMinors();
      }
    });
  });
}

// ── Service Worker ──────────────────────────────────────────────────────────
function registerSW() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js')
      .catch(err => console.warn('SW registration failed:', err));
  }
}

// ── Bootstrap ───────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadPlayers();
  setupMLBFilters();
  setupMLBSort();
  setupTabs();
  setupMinorFilters();
  setupMinorSort();
  registerSW();

  // iOS PWA: prevent background pan/drag when touching dead space on the body.
  // Scrollable containers (.table-wrapper etc.) are unaffected because their
  // touch events don't bubble up with target === document.body.
  document.body.addEventListener('touchmove', e => {
    if (e.target === document.body) e.preventDefault();
  }, { passive: false });
});
