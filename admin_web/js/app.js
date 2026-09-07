// SM WoT Assistant Admin — Web UI JS
const API = "";  // Same origin (Flask serves both static and API)

// --- Tabs ---
document.querySelectorAll(".tabs .tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tabs .tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    const tabId = "tab-" + btn.dataset.tab;
    const tabEl = document.getElementById(tabId);
    if (tabEl) tabEl.classList.add("active");
    onTabActivated(btn.dataset.tab);
  });
});

function onTabActivated(tab) {
  if (tab === "builds") refreshBuilds();
  if (tab === "prompts") refreshPrompts();
  if (tab === "community") refreshCommunity();
  if (tab === "errors") refreshErrors();
  if (tab === "settings") refreshSettings();
}

// --- API helpers ---
async function apiGet(path) {
  try {
    const r = await fetch(API + path);
    if (!r.ok) return null;
    return await r.json();
  } catch (e) { return null; }
}
async function apiPost(path) {
  try {
    const r = await fetch(API + path, { method: "POST" });
    if (!r.ok) return null;
    return await r.json();
  } catch (e) { return null; }
}

// --- Overview ---
async function refreshOverview() {
  const status = await apiGet("/api/status");
  if (status) {
    document.getElementById("status-value").textContent = status.running ? "running" : "stopped";
    document.getElementById("status-value").className = status.running ? "success" : "error";
  }
  document.getElementById("version-value").textContent = "1.0.45";
  const prompts = await apiGet("/api/prompts");
  if (prompts) {
    document.getElementById("stat-tanks-db").textContent = "—";
    document.getElementById("stat-prompts").textContent = Object.keys(prompts).length;
  }
  document.getElementById("stat-builds").textContent = "—";
  document.getElementById("stat-queue").textContent = "0";
  document.getElementById("stat-errors").textContent = "0";

  const log = await apiGet("/api/log");
  if (log && log.lines) {
    document.getElementById("log-view").textContent = log.lines.join("\n") || "—";
  }
}

document.getElementById("btn-scan").addEventListener("click", async () => {
  await apiPost("/api/scan");
  await refreshOverview();
});
document.getElementById("btn-generate").addEventListener("click", async () => {
  await apiPost("/api/generate");
  await refreshOverview();
});
document.getElementById("btn-generate-popular").addEventListener("click", () => {
  console.log("popular generate: stub");
});
document.getElementById("btn-regen-all").addEventListener("click", () => {
  if (confirm("Regenerate ALL builds? This will take a long time.")) {
    console.log("regen all: stub");
  }
});
document.getElementById("btn-refresh").addEventListener("click", refreshOverview);
document.getElementById("btn-clear-log").addEventListener("click", () => {
  document.getElementById("log-view").textContent = "—";
});

// --- Builds ---
async function refreshBuilds() {
  const tbody = document.querySelector("#builds-table tbody");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="3" class="muted">Loading...</td></tr>';
  const builds = await apiGet("/api/builds") || {};
  const prompts = await apiGet("/api/prompts") || {};
  const rows = Object.keys(builds).map(tag => {
    const status = prompts[tag] ? "complete" : "no-prompt";
    return `<tr><td>${escapeHtml(tag)}</td><td><span class="${status === 'complete' ? 'success' : 'warn'}">${status}</span></td><td>—</td></tr>`;
  });
  tbody.innerHTML = rows.length ? rows.join("") : '<tr><td colspan="3" class="muted">No builds yet</td></tr>';
  setupBuildsFilter();
}

function setupBuildsFilter() {
  const search = document.getElementById("builds-search");
  if (!search) return;
  search.oninput = () => {
    const q = search.value.toLowerCase();
    document.querySelectorAll("#builds-table tbody tr").forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  };
}

// --- Prompts ---
async function refreshPrompts() {
  const tbody = document.querySelector("#prompts-table tbody");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="2" class="muted">Loading...</td></tr>';
  const prompts = await apiGet("/api/prompts") || {};
  const rows = Object.entries(prompts).map(([tag, txt]) => {
    const preview = String(txt || "").substring(0, 80);
    return `<tr><td>${escapeHtml(tag)}</td><td>${escapeHtml(preview)}…</td></tr>`;
  });
  tbody.innerHTML = rows.length ? rows.join("") : '<tr><td colspan="2" class="muted">No prompts</td></tr>';
  const search = document.getElementById("prompts-search");
  if (search) {
    search.oninput = () => {
      const q = search.value.toLowerCase();
      document.querySelectorAll("#prompts-table tbody tr").forEach(tr => {
        tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    };
  }
}

// --- Community ---
async function refreshCommunity() {
  const tiles = await apiGet("/api/community");
  if (tiles) {
    document.getElementById("stat-yt").textContent = tiles.youtube?.views || "—";
    document.getElementById("stat-rd").textContent = tiles.reddit?.karma || "—";
    document.getElementById("stat-gh").textContent = tiles.github?.downloads || "—";
    document.getElementById("stat-kofi").textContent = tiles.kofi?.donations || "—";
    document.getElementById("stat-patreon").textContent = tiles.patreon?.patrons || "—";
  } else {
    ["yt", "rd", "gh", "kofi", "patreon"].forEach(id => {
      document.getElementById("stat-" + id).textContent = "—";
    });
  }
}
document.getElementById("btn-refresh-community").addEventListener("click", refreshCommunity);

// --- Errors ---
async function refreshErrors() {
  const tbody = document.querySelector("#errors-table tbody");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="4" class="muted">Loading...</td></tr>';
  const errs = await apiGet("/api/errors") || [];
  const rows = errs.map(e => {
    return `<tr><td>${escapeHtml(e.type || "")}</td><td>${escapeHtml(e.stage || "")}</td><td>${escapeHtml((e.error_text || "").substring(0, 80))}</td><td>${escapeHtml(e.timestamp || "")}</td></tr>`;
  });
  tbody.innerHTML = rows.length ? rows.join("") : '<tr><td colspan="4" class="muted">No errors</td></tr>';
}

// --- Settings ---
async function refreshSettings() {
  const s = await apiGet("/api/settings") || {};
  document.getElementById("setting-wot-path").value = s.wot_path || "";
  document.getElementById("setting-launch-on-game-start").checked = !!s.launch_on_game_start;
  document.getElementById("setting-close-with-game").checked = !!s.close_with_game;
  document.getElementById("setting-sync-schemes-with-mode").checked = !!s.sync_schemes_with_mode;
}
document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = {
    wot_path: document.getElementById("setting-wot-path").value,
    launch_on_game_start: document.getElementById("setting-launch-on-game-start").checked,
    close_with_game: document.getElementById("setting-close-with-game").checked,
    sync_schemes_with_mode: document.getElementById("setting-sync-schemes-with-mode").checked,
  };
  await apiPost("/api/settings", data);
  alert("Settings saved");
});

// --- Drilldown (stat click) ---
document.querySelectorAll(".stat[data-detail]").forEach(stat => {
  stat.addEventListener("click", () => {
    const key = stat.dataset.detail;
    openDrilldown(key);
  });
});

function openDrilldown(key) {
  const modal = document.getElementById("drilldown-modal");
  document.getElementById("drilldown-title").textContent = key;
  modal.showModal();
  loadDrilldownData(key);
}

async function loadDrilldownData(key) {
  const tbody = document.querySelector("#drilldown-table tbody");
  const thead = document.querySelector("#drilldown-table thead");
  tbody.innerHTML = '<tr><td class="muted">Loading...</td></tr>';
  let rows = [];
  let headers = ["Tag"];
  if (key === "tanks-db" || key === "builds" || key === "prompts" || key === "queue") {
    const prompts = await apiGet("/api/prompts") || {};
    const builds = await apiGet("/api/builds") || {};
    if (key === "builds") {
      rows = Object.keys(builds).map(tag => ({ tag, status: prompts[tag] ? "complete" : "no-prompt" }));
      headers = ["Tag", "Status"];
    } else if (key === "prompts") {
      rows = Object.entries(prompts).map(([tag, txt]) => ({ tag, preview: String(txt).substring(0, 60) }));
      headers = ["Tag", "Preview"];
    } else if (key === "queue") {
      rows = [];  // Stub
      headers = ["Tag"];
    } else {
      rows = Object.keys(prompts).map(tag => ({ tag }));
      headers = ["Tag"];
    }
  } else if (key === "errors") {
    const errs = await apiGet("/api/errors") || [];
    rows = errs.map(e => ({ type: e.type, stage: e.stage, text: (e.error_text || "").substring(0, 60) }));
    headers = ["Type", "Stage", "Text"];
  } else if (key === "youtube" || key === "reddit" || key === "github" || key === "kofi" || key === "patreon") {
    rows = [{ value: "—", source: key }];
    headers = ["Value", "Source"];
  }
  thead.innerHTML = "<tr>" + headers.map(h => `<th>${h}</th>`).join("") + "</tr>";
  tbody.innerHTML = rows.length ? rows.map(r =>
    "<tr>" + headers.map(h => `<td>${escapeHtml(String(r[h.toLowerCase()] || ""))}</td>`).join("") + "</tr>"
  ).join("") : `<tr><td colspan="${headers.length}" class="muted">No data</td></tr>`;
  document.getElementById("drilldown-status").textContent = `${rows.length} / ${rows.length}`;
}

document.getElementById("drilldown-close").addEventListener("click", () => {
  document.getElementById("drilldown-modal").close();
});
document.getElementById("drilldown-search").addEventListener("input", () => {
  const q = document.getElementById("drilldown-search").value.toLowerCase();
  document.querySelectorAll("#drilldown-table tbody tr").forEach(tr => {
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
  });
});

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// --- Init ---
setInterval(refreshOverview, 10000);
refreshOverview();
