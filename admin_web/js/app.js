// SM WoT Assistant Admin — Web UI JS
const API = '';
let currentLang = 'uk';

// --- I18N ---
const I18N = {
  uk: {
    app_name: 'SM WoT Assistant',
    status: 'Статус',
    running: 'Працює',
    stopped: 'Зупинено',
    overview: 'Огляд',
    builds: 'Збірки',
    prompts: 'Промпти',
    errors: 'Помилки',
    build_status: 'Статус збірок',
    community: 'Спільнота',
    log: 'Лог (останні 100 рядків)',
    tanks_db: 'Танки (БД)',
    prompts_count: 'Промпти',
    builds_count: 'Збірки',
    queue: 'Черга',
    errors_count: 'Помилки',
    scan: 'Сканувати',
    generate_queue: 'Згенерувати чергу',
    generate_popular: 'Згенерувати популярні',
    regen_all: 'Перегенерувати все',
    refresh: 'Оновити',
    youtube_views: 'Перегляди YouTube',
    reddit_karma: 'Karma Reddit',
    gh_downloads: 'Завантаження GH',
    kofi: 'Ko-fi',
    patreon: 'Patreon',
    settings: 'Налаштування',
    wot_path: 'Шлях до WoT:',
    start_with_windows: 'Запуск з Windows',
    language: 'Мова:',
    save: 'Зберегти',
    cancel: 'Скасувати',
    close: 'Закрити',
    clear: 'Очистити',
    search: 'Пошук...',
    settings_saved: 'Налаштування збережено',
    loading: 'Завантаження...',
    no_data: 'Немає даних',
    no_errors: 'Немає помилок',
    tag: 'Тег',
    status_col: 'Статус',
    updated: 'Оновлено',
    preview: 'Попередній перегляд',
    type: 'Тип',
    stage: 'Етап',
    text: 'Текст',
    time: 'Час',
    all: 'Усі',
    missing: 'Відсутні',
    complete: 'Завершені',
    complete_st: 'Завершено',
    no_prompt_st: 'Немає промпту',
    ukrainian: 'Українська'
  },
  en: {
    app_name: 'SM WoT Assistant',
    status: 'Status',
    running: 'Running',
    stopped: 'Stopped',
    overview: 'Overview',
    builds: 'Builds',
    prompts: 'Prompts',
    errors: 'Errors',
    build_status: 'Build status',
    community: 'Community',
    log: 'Log (last 100 lines)',
    tanks_db: 'Tanks (DB)',
    prompts_count: 'Prompts',
    builds_count: 'Builds',
    queue: 'Queue',
    errors_count: 'Errors',
    scan: 'Scan',
    generate_queue: 'Generate queue',
    generate_popular: 'Generate popular',
    regen_all: 'Regenerate all',
    refresh: 'Refresh',
    youtube_views: 'YouTube views',
    reddit_karma: 'Reddit karma',
    gh_downloads: 'GH downloads',
    kofi: 'Ko-fi',
    patreon: 'Patreon',
    settings: 'Settings',
    wot_path: 'WoT path:',
    start_with_windows: 'Start with Windows',
    language: 'Language:',
    save: 'Save',
    cancel: 'Cancel',
    close: 'Close',
    clear: 'Clear',
    search: 'Search...',
    settings_saved: 'Settings saved',
    loading: 'Loading...',
    no_data: 'No data',
    no_errors: 'No errors',
    tag: 'Tag',
    status_col: 'Status',
    updated: 'Updated',
    preview: 'Preview',
    type: 'Type',
    stage: 'Stage',
    text: 'Text',
    time: 'Time',
    all: 'All',
    missing: 'Missing',
    complete: 'Complete',
    complete_st: 'Complete',
    no_prompt_st: 'No prompt',
    ukrainian: 'Ukrainian'
  }
};

// --- Language switching ---
function applyLanguage() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const dict = I18N[currentLang] || I18N.uk;
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    const dict = I18N[currentLang] || I18N.uk;
    if (dict[key]) {
      el.placeholder = dict[key];
    }
  });
  document.documentElement.lang = currentLang;
}

// --- API helpers ---
async function apiGet(path) {
  try {
    const r = await fetch(API + path);
    if (!r.ok) return null;
    return await r.json();
  } catch (e) { return null; }
}

async function apiPost(path, body) {
  try {
    const opts = { method: 'POST' };
    if (body !== undefined) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(API + path, opts);
    if (!r.ok) return null;
    return await r.json();
  } catch (e) { return null; }
}

// --- Data loading ---
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = (val !== null && val !== undefined) ? val : '\u2014';
}

async function refreshStatus() {
  const status = await apiGet('/api/status');
  if (status) {
    const el = document.getElementById('status-value');
    if (el) {
      const dict = I18N[currentLang] || I18N.uk;
      el.textContent = status.running ? dict.running : dict.stopped;
      el.className = status.running ? 'success' : 'error';
    }
    setText('version-value', status.version || '\u2014');
  }
}

async function refreshBuildsCard() {
  const [tanks, builds, prompts, errs] = await Promise.all([
    apiGet('/api/tanks'),
    apiGet('/api/builds'),
    apiGet('/api/prompts'),
    apiGet('/api/errors')
  ]);
  setText('stat-tanks-db', tanks && tanks.count !== undefined ? tanks.count : '\u2014');
  setText('stat-builds', builds && builds.count !== undefined ? builds.count : '\u2014');
  setText('stat-prompts', prompts ? Object.keys(prompts).length : '\u2014');
  setText('stat-queue', (builds && builds.queue !== undefined) ? builds.queue : '0');
  setText('stat-errors', errs ? (Array.isArray(errs) ? errs.length : errs.count || 0) : '0');
}

async function refreshCommunity() {
  const tiles = await apiGet('/api/community');
  if (tiles) {
    setText('stat-yt', tiles.youtube && tiles.youtube.views);
    setText('stat-rd', tiles.reddit && tiles.reddit.karma);
    setText('stat-gh', tiles.github && tiles.github.downloads);
    setText('stat-kofi', tiles.kofi && tiles.kofi.donations);
    setText('stat-patreon', tiles.patreon && tiles.patreon.patrons);
  } else {
    ['stat-yt', 'stat-rd', 'stat-gh', 'stat-kofi', 'stat-patreon'].forEach(id => setText(id, '\u2014'));
  }
}

async function refreshLog() {
  const log = await apiGet('/api/log');
  const el = document.getElementById('log-view');
  if (el) {
    el.textContent = (log && log.lines && log.lines.length) ? log.lines.join('\n') : '\u2014';
  }
}

async function refreshOverview() {
  await Promise.all([
    refreshStatus(),
    refreshBuildsCard(),
    refreshCommunity(),
    refreshLog()
  ]);
}

async function refreshBuilds() {
  const tbody = document.querySelector('#builds-table tbody');
  if (!tbody) return;
  const dict = I18N[currentLang] || I18N.uk;
  tbody.innerHTML = '<tr><td colspan="3" class="muted">' + dict.loading + '</td></tr>';
  const builds = await apiGet('/api/builds') || {};
  const prompts = await apiGet('/api/prompts') || {};
  const buildKeys = builds.data ? Object.keys(builds.data) : Object.keys(builds);
  const rows = buildKeys.map(tag => {
    const isComplete = prompts[tag] || (prompts.data && prompts.data[tag]);
    const statusKey = isComplete ? 'complete_st' : 'no_prompt_st';
    const statusCls = isComplete ? 'success' : 'warn';
    return '<tr><td>' + escapeHtml(tag) + '</td><td><span class="' + statusCls + '">' + escapeHtml(dict[statusKey]) + '</span></td><td>\u2014</td></tr>';
  });
  tbody.innerHTML = rows.length ? rows.join('') : '<tr><td colspan="3" class="muted">' + dict.no_data + '</td></tr>';
  setupSearch('builds-search', '#builds-table tbody tr');
}

async function refreshPrompts() {
  const tbody = document.querySelector('#prompts-table tbody');
  if (!tbody) return;
  const dict = I18N[currentLang] || I18N.uk;
  tbody.innerHTML = '<tr><td colspan="2" class="muted">' + dict.loading + '</td></tr>';
  const prompts = await apiGet('/api/prompts') || {};
  const data = prompts.data || prompts;
  const rows = Object.entries(data).map(([tag, txt]) => {
    const preview = String(txt || '').substring(0, 80);
    return '<tr><td>' + escapeHtml(tag) + '</td><td>' + escapeHtml(preview) + '\u2026</td></tr>';
  });
  tbody.innerHTML = rows.length ? rows.join('') : '<tr><td colspan="2" class="muted">' + dict.no_data + '</td></tr>';
  setupSearch('prompts-search', '#prompts-table tbody tr');
}

async function refreshErrors() {
  const tbody = document.querySelector('#errors-table tbody');
  if (!tbody) return;
  const dict = I18N[currentLang] || I18N.uk;
  tbody.innerHTML = '<tr><td colspan="4" class="muted">' + dict.loading + '</td></tr>';
  const errs = await apiGet('/api/errors') || [];
  const list = Array.isArray(errs) ? errs : (errs.data || []);
  const rows = list.map(e => {
    return '<tr><td>' + escapeHtml(e.type || '') + '</td><td>' + escapeHtml(e.stage || '') + '</td><td>' + escapeHtml((e.error_text || '').substring(0, 80)) + '</td><td>' + escapeHtml(e.timestamp || '') + '</td></tr>';
  });
  tbody.innerHTML = rows.length ? rows.join('') : '<tr><td colspan="4" class="muted">' + dict.no_errors + '</td></tr>';
}

// --- Tab switching ---
document.querySelectorAll('.tabs .tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tabs .tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    const tabId = 'tab-' + btn.dataset.tab;
    const tabEl = document.getElementById(tabId);
    if (tabEl) tabEl.classList.add('active');
    onTabActivated(btn.dataset.tab);
  });
});

function onTabActivated(tab) {
  if (tab === 'builds') refreshBuilds();
  if (tab === 'prompts') refreshPrompts();
  if (tab === 'errors') refreshErrors();
}

// --- Buttons ---
document.getElementById('btn-scan').addEventListener('click', async () => {
  await apiPost('/api/scan');
  await refreshOverview();
});

document.getElementById('btn-generate').addEventListener('click', async () => {
  await apiPost('/api/generate');
  await refreshOverview();
});

document.getElementById('btn-generate-popular').addEventListener('click', async () => {
  await apiPost('/api/generate/popular');
  await refreshOverview();
});

document.getElementById('btn-regen-all').addEventListener('click', async () => {
  const dict = I18N[currentLang] || I18N.uk;
  if (confirm(dict.regen_all + '?')) {
    await apiPost('/api/regen-all');
    await refreshOverview();
  }
});

document.getElementById('btn-refresh').addEventListener('click', refreshOverview);

document.getElementById('btn-clear-log').addEventListener('click', () => {
  document.getElementById('log-view').textContent = '\u2014';
});

document.getElementById('btn-refresh-community').addEventListener('click', refreshCommunity);

document.getElementById('builds-refresh').addEventListener('click', refreshBuilds);
document.getElementById('prompts-refresh').addEventListener('click', refreshPrompts);
document.getElementById('errors-refresh').addEventListener('click', refreshErrors);

// --- Drilldown ---
document.querySelectorAll('.stat[data-detail]').forEach(stat => {
  stat.addEventListener('click', () => {
    openDrilldown(stat.dataset.detail);
  });
});

function openDrilldown(key) {
  const dict = I18N[currentLang] || I18N.uk;
  const titleMap = {
    'tanks-db': dict.tanks_db,
    'builds': dict.builds_count,
    'prompts': dict.prompts_count,
    'queue': dict.queue,
    'errors': dict.errors_count,
    'community-youtube': dict.youtube_views,
    'community-reddit': dict.reddit_karma,
    'community-github': dict.gh_downloads,
    'community-kofi': dict.kofi,
    'community-patreon': dict.patreon
  };
  document.getElementById('drilldown-title').textContent = titleMap[key] || key;
  document.getElementById('drilldown-modal').showModal();
  loadDrilldownData(key);
}

async function loadDrilldownData(key) {
  const tbody = document.querySelector('#drilldown-table tbody');
  const thead = document.querySelector('#drilldown-table thead');
  const dict = I18N[currentLang] || I18N.uk;
  tbody.innerHTML = '<tr><td class="muted">' + dict.loading + '</td></tr>';
  let rows = [];
  let headers = [dict.tag];

  if (key === 'tanks-db' || key === 'builds' || key === 'prompts' || key === 'queue') {
    const prompts = await apiGet('/api/prompts') || {};
    const builds = await apiGet('/api/builds') || {};
    const promptsData = prompts.data || prompts;
    const buildsData = builds.data || builds;

    if (key === 'builds') {
      rows = Object.keys(buildsData).map(tag => ({
        tag: tag,
        status: promptsData[tag] ? dict.complete_st : dict.no_prompt_st
      }));
      headers = [dict.tag, dict.status_col];
    } else if (key === 'prompts') {
      rows = Object.entries(promptsData).map(([tag, txt]) => ({
        tag: tag,
        preview: String(txt).substring(0, 60)
      }));
      headers = [dict.tag, dict.preview];
    } else if (key === 'queue') {
      rows = [];
      headers = [dict.tag];
    } else {
      rows = Object.keys(promptsData).map(tag => ({ tag: tag }));
      headers = [dict.tag];
    }
  } else if (key === 'errors') {
    const errs = await apiGet('/api/errors') || [];
    const list = Array.isArray(errs) ? errs : (errs.data || []);
    rows = list.map(e => ({
      type: e.type || '',
      stage: e.stage || '',
      text: (e.error_text || '').substring(0, 60)
    }));
    headers = [dict.type, dict.stage, dict.text];
  } else if (key.startsWith('community-')) {
    const platform = key.replace('community-', '');
    const tiles = await apiGet('/api/community') || {};
    const data = tiles[platform] || {};
    rows = Object.entries(data).map(([k, v]) => ({ key: k, value: String(v) }));
    headers = ['Key', 'Value'];
  }

  thead.innerHTML = '<tr>' + headers.map(h => '<th>' + escapeHtml(h) + '</th>').join('') + '</tr>';
  tbody.innerHTML = rows.length ? rows.map(r =>
    '<tr>' + headers.map(h => {
      const field = h.toLowerCase();
      return '<td>' + escapeHtml(String(r[field] || '')) + '</td>';
    }).join('') + '</tr>'
  ).join('') : '<tr><td colspan="' + headers.length + '" class="muted">' + dict.no_data + '</td></tr>';
  setText('drilldown-status', rows.length + ' / ' + rows.length);
}

document.getElementById('drilldown-close').addEventListener('click', () => {
  document.getElementById('drilldown-modal').close();
});

document.getElementById('drilldown-search').addEventListener('input', () => {
  const q = document.getElementById('drilldown-search').value.toLowerCase();
  document.querySelectorAll('#drilldown-table tbody tr').forEach(tr => {
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
});

// --- Settings ---
document.getElementById('settings-btn').addEventListener('click', async () => {
  await loadSettings();
  document.getElementById('settings-modal').showModal();
});

document.getElementById('settings-cancel').addEventListener('click', () => {
  document.getElementById('settings-modal').close();
});

document.getElementById('set-lang').addEventListener('change', (e) => {
  currentLang = e.target.value;
  applyLanguage();
});

document.getElementById('settings-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    wot_path: document.getElementById('set-wot-path').value,
    launch_with_windows: document.getElementById('set-launch-windows').checked,
    sync_schemes_with_mode: document.getElementById('set-sync-schemes') ? document.getElementById('set-sync-schemes').checked : false,
    language: document.getElementById('set-lang').value
  };
  await apiPost('/api/settings', payload);
  currentLang = payload.language || 'uk';
  applyLanguage();
  document.getElementById('settings-modal').close();
});

async function loadSettings() {
  const s = await apiGet('/api/settings') || {};
  document.getElementById('set-wot-path').value = s.wot_path || '';
  document.getElementById('set-launch-windows').checked = !!s.launch_with_windows;
  if (document.getElementById('set-sync-schemes')) {
    document.getElementById('set-sync-schemes').checked = !!s.sync_schemes_with_mode;
  }
  document.getElementById('set-lang').value = s.language || 'uk';
  currentLang = s.language || 'uk';
}

// --- Helpers ---
function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function setupSearch(inputId, rowSelector) {
  const search = document.getElementById(inputId);
  if (!search) return;
  search.oninput = () => {
    const q = search.value.toLowerCase();
    document.querySelectorAll(rowSelector).forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  };
}

// --- Init ---
loadSettings().then(() => {
  applyLanguage();
  refreshOverview();
});
setInterval(refreshOverview, 10000);
