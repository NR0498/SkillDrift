const DEMO = window.SKILLDRIFT_DEMO || { trends: [], jobs: [] };
const DEFAULT_DEMO_BASE = "demo";
const LOCAL_API_BASE = "http://localhost:8000";
const STORAGE_KEY = "skilldrift.apiBase";

const els = {
  healthPill: document.getElementById("health-pill"),
  settingsButton: document.getElementById("settings-button"),
  settingsDialog: document.getElementById("settings-dialog"),
  settingsForm: document.getElementById("settings-form"),
  apiBase: document.getElementById("api-base"),
  resetApi: document.getElementById("reset-api"),
  searchForm: document.getElementById("search-form"),
  query: document.getElementById("query"),
  searchButton: document.getElementById("search-button"),
  trendGrid: document.getElementById("trend-grid"),
  trendNote: document.getElementById("trend-note"),
  resultsGrid: document.getElementById("results-grid"),
  searchState: document.getElementById("search-state"),
  resultCount: document.getElementById("result-count"),
  totalRecords: document.getElementById("total-records"),
  distinctJobs: document.getElementById("distinct-jobs"),
  trackedSkills: document.getElementById("tracked-skills"),
  risingSkills: document.getElementById("rising-skills"),
  decliningSkills: document.getElementById("declining-skills"),
  freshnessValue: document.getElementById("freshness-value"),
  freshnessLabel: document.getElementById("freshness-label"),
  plainLanguageCopy: document.getElementById("plain-language-copy"),
};

function getApiBase() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved !== null) return saved;
  if (window.SKILLDRIFT_API_BASE !== undefined) return window.SKILLDRIFT_API_BASE;
  if (["localhost", "127.0.0.1", "::1"].includes(location.hostname)) return LOCAL_API_BASE;
  return "";
}

let apiBase = getApiBase();
let latestTrends = [];
let latestHealth = null;

function setHealth(text, tone = "neutral") {
  els.healthPill.textContent = text;
  els.healthPill.dataset.tone = tone;
}

function esc(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function formatPct(value) {
  return `${Number(value).toFixed(2)}%`;
}

function formatDrift(value) {
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

function statusTone(status) {
  if (status === "rising") return "var(--positive)";
  if (status === "declining") return "var(--negative)";
  return "var(--warning)";
}

function statusText(status) {
  if (status === "rising") return "appearing more often";
  if (status === "declining") return "appearing less often";
  return "roughly unchanged";
}

function shortText(value, limit = 180) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  if (clean.length <= limit) return clean;
  return `${clean.slice(0, limit - 1)}…`;
}

async function request(path) {
  const url = apiBase ? `${apiBase}${path}` : path;
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) message = body.detail;
    } catch {
      // Keep fallback message.
    }
    throw new Error(message);
  }
  return response.json();
}

function renderStats(trends, stats, sourceLabel) {
  const rising = stats?.rising_skills ?? trends.filter((item) => item.status === "rising").length;
  const declining = stats?.declining_skills
    ?? trends.filter((item) => item.status === "declining").length;

  els.totalRecords.textContent = stats?.total_records?.toLocaleString() || "--";
  els.distinctJobs.textContent = stats?.distinct_jobs?.toLocaleString() || "--";
  els.trackedSkills.textContent = stats?.tracked_skills || trends.length || "--";
  els.risingSkills.textContent = rising || "--";
  els.decliningSkills.textContent = declining || "--";
  els.freshnessValue.textContent = stats?.snapshot_count
    ? `${stats.snapshot_count} days`
    : sourceLabel;
  els.freshnessLabel.textContent = latestHealth
    ? `${stats?.real_records || 0} real and ${stats?.simulated_records || 0} simulated rows. Latest: ${stats?.latest_snapshot || "unknown"}.`
    : sourceLabel === "Demo"
      ? "Demo data is visible because the API was not reachable."
      : "Waiting for the latest run.";
}

function renderTrends(trends, sourceLabel) {
  if (!trends.length) {
    els.trendGrid.innerHTML = `
      <div class="empty-state panel-soft">
        No trend data is available yet. Run the pipeline, or use the demo mode to see the layout.
      </div>
    `;
    els.trendNote.textContent = "No results yet";
    return;
  }

  els.trendGrid.innerHTML = trends
    .map((item) => {
      const tone = statusTone(item.status);
      return `
        <article class="trend-card" style="--tone:${tone}">
          <div class="trend-top">
            <div>
              <p class="skill-name">${esc(item.skill)}</p>
              <p class="result-meta">${esc(statusText(item.status))}</p>
            </div>
            <span class="status-chip">${esc(item.status)}</span>
          </div>
          <div class="trend-metrics">
            <div class="trend-metric">
              <div class="metric-label">Current share</div>
              <div class="metric-value">${formatPct(item.current_pct)}</div>
            </div>
            <div class="trend-metric">
              <div class="metric-label">Change</div>
              <div class="metric-value">${formatDrift(item.drift)}</div>
            </div>
            <div class="trend-metric">
              <div class="metric-label">Snapshots</div>
              <div class="metric-value">${esc(item.snapshots)}</div>
            </div>
          </div>
          <div class="metric-help">
            ${esc(item.skill)} is ${statusText(item.status)} across ${esc(item.snapshots)} snapshots.
          </div>
          <div class="trend-actions">
            <button type="button" class="link-button" data-skill="${esc(item.skill)}">View details</button>
            <span class="result-meta">Source: ${esc(sourceLabel)}</span>
          </div>
        </article>
      `;
    })
    .join("");

  els.trendNote.textContent = `${trends.length} skills from ${sourceLabel.toLowerCase()} data`;
}

function renderSearchResults(items, query, sourceLabel) {
  if (!items.length) {
    els.resultsGrid.hidden = true;
    els.searchState.hidden = false;
    els.searchState.textContent = `No jobs matched “${query}”. Try a broader term like “python”, “data”, or “cloud”.`;
    els.resultCount.textContent = `No matches for “${query}”.`;
    return;
  }

  els.searchState.hidden = true;
  els.resultsGrid.hidden = false;
  els.resultsGrid.innerHTML = items
    .map((job) => {
      const tags = Array.isArray(job.tags) ? job.tags.join(", ") : job.tags;
      const sourceLink = job.source_url
        ? `<a class="source-link" href="${esc(job.source_url)}" target="_blank" rel="noopener noreferrer">Open source</a>`
        : "";

      return `
        <article class="result-card">
          <div>
            <h3>${esc(job.title || "Untitled role")}</h3>
            <div class="result-meta">${esc(job.company || "Unknown company")} | ${esc(tags || "No tags")}</div>
            <p class="result-snippet">${esc(shortText(job.description || "No description available."))}</p>
          </div>
          <div class="result-actions">
            ${sourceLink}
            <div class="result-meta">${esc(sourceLabel)}</div>
          </div>
        </article>
      `;
    })
    .join("");

  els.resultCount.textContent = `${items.length} results for “${query}”`;
}

async function loadDashboard() {
  try {
    const [health, trends, stats] = await Promise.all([
      request("/health"),
      request("/skills/trending?direction=all&limit=12"),
      request("/stats"),
    ]);
    latestHealth = health;
    latestTrends = trends;
    const label = "Live data";
    setHealth(
      health.status === "ok"
        ? "Live data connected"
        : "Live data available with warnings",
      health.status === "ok" ? "positive" : "warning",
    );
    renderStats(trends, stats, label);
    renderTrends(trends, label);
  } catch (error) {
    latestHealth = null;
    latestTrends = DEMO.trends;
    setHealth("Demo mode", "warning");
    renderStats(DEMO.trends, null, "Demo");
    renderTrends(DEMO.trends, "Demo");
    els.trendNote.textContent = `Showing demo data because the API was not reachable.`;
    els.plainLanguageCopy.textContent =
      "Demo mode keeps the dashboard usable even when the API is offline. Connect your own API in the settings if you want live data.";
    console.warn(error);
  }
}

async function performSearch(query) {
  const trimmed = query.trim();
  if (trimmed.length < 2) return;

  els.searchButton.disabled = true;
  els.searchButton.textContent = "Searching...";

  try {
    const data = await request(`/search?q=${encodeURIComponent(trimmed)}&limit=20`);
    renderSearchResults(data.items || [], trimmed, "Live data");
  } catch (error) {
    const fallback = DEMO.jobs.filter((job) => {
      const haystack = `${job.title} ${job.company} ${(job.tags || []).join(" ")} ${job.description}`.toLowerCase();
      return haystack.includes(trimmed.toLowerCase());
    });
    if (fallback.length) {
      renderSearchResults(fallback, trimmed, "Demo results");
      els.searchState.hidden = true;
    } else {
      els.resultsGrid.hidden = true;
      els.searchState.hidden = false;
      els.searchState.textContent = `I could not load live results. ${error.message} Use demo search terms or connect the API in settings.`;
      els.resultCount.textContent = "Live search is unavailable";
    }
    setHealth("Offline, showing demo", "warning");
  } finally {
    els.searchButton.disabled = false;
    els.searchButton.textContent = "Search";
  }
}

function openSettings() {
  els.apiBase.value = apiBase;
  if (typeof els.settingsDialog.showModal === "function") {
    els.settingsDialog.showModal();
  } else {
    const next = window.prompt("API base URL", apiBase);
    if (next !== null) saveApiBase(next.trim());
  }
}

function saveApiBase(nextBase) {
  apiBase = nextBase;
  if (apiBase) {
    localStorage.setItem(STORAGE_KEY, apiBase);
    setHealth("Custom data source", "positive");
  } else {
    localStorage.removeItem(STORAGE_KEY);
    apiBase = getApiBase();
    setHealth(apiBase ? "Live data connected" : "Demo mode", apiBase ? "positive" : "warning");
  }
  loadDashboard();
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-query]");
  if (button) {
    els.query.value = button.dataset.query || "";
    els.searchForm.requestSubmit();
    return;
  }

  const skillButton = event.target.closest("[data-skill]");
  if (skillButton) {
    const skill = skillButton.dataset.skill || "";
    if (skill) {
      els.query.value = skill;
      els.searchForm.requestSubmit();
    }
  }
});

els.settingsButton.addEventListener("click", openSettings);
els.settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  saveApiBase(els.apiBase.value.trim());
  els.settingsDialog.close();
});
els.resetApi.addEventListener("click", () => {
  els.apiBase.value = "";
});

els.searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  performSearch(els.query.value);
});

if (els.settingsDialog && typeof els.settingsDialog.addEventListener === "function") {
  els.settingsDialog.addEventListener("click", (event) => {
    if (event.target === els.settingsDialog) {
      els.settingsDialog.close();
    }
  });
}

loadDashboard();
