import { loadSnapshot, asset } from "./api.js";
import { STATS, clock } from "./format.js";
import { renderOverview } from "./views/overview.js";
import { renderLibrary, renderLibraryResults } from "./views/library.js";
import { renderModels, renderModelsResults } from "./views/models.js";
import { renderActivity } from "./views/activity.js";

const TITLES = {
  overview: "總覽",
  library: "素材",
  models: "模型",
  activity: "活動",
};

const initialView = location.hash.replace(/^#/, "");
const state = {
  view: TITLES[initialView] ? initialView : "overview",
  live: true,
  filters: { libraryQuery: "", role: "", commercial: "", modelQuery: "" },
  summary: null,
  assets: [],
  assetTotal: 0,
  models: [],
  modelCount: 0,
  modelTotal: 0,
  roles: [],
  trips: [],
  status: null,
  events: [],
  selectedId: null,
  detail: null,
  error: "",
  updatedAt: null,
  debounce: 0,
};

const actions = {
  setFilter(name, value) {
    state.filters[name] = value;
    const active = document.activeElement;
    const typing = active && active.matches("input, select, textarea");
    if (!typing) renderStage();
    scheduleTick();
  },
  selectAsset(id) {
    state.selectedId = id;
    state.detail = null;
    renderStage();
    if (!id) return;
    asset(id)
      .then((detail) => {
        if (state.selectedId !== id) return;
        state.detail = detail;
        refreshResults();
      })
      .catch((error) => {
        state.error = error.message || "無法讀取素材。";
        renderChrome();
      });
  },
};

function markNav() {
  document.querySelectorAll("[data-view]").forEach((item) => {
    const current = item.dataset.view === state.view;
    item.classList.toggle("is-current", current);
    if (current) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    state.selectedId = null;
    state.detail = null;
    history.replaceState(null, "", `#${state.view}`);
    markNav();
    renderChrome();
    renderStage();
  });
});
markNav();

document.querySelector("#refresh").addEventListener("click", () => tick(true));
document.querySelector("#live-toggle").addEventListener("click", () => {
  state.live = !state.live;
  renderChrome();
  if (state.live) tick(true);
});

function scheduleTick() {
  window.clearTimeout(state.debounce);
  state.debounce = window.setTimeout(() => tick(true), 250);
}

async function tick(manual) {
  if (!state.live && !manual) return;
  const previous = state.summary;
  try {
    const next = await loadSnapshot(state.filters);
    const events = diffSummary(previous, next.summary);
    if (events.length) state.events = events.concat(state.events).slice(0, 80);
    state.summary = next.summary;
    state.assets = next.assets;
    state.assetTotal = next.assetTotal;
    state.models = next.models;
    state.modelCount = next.modelCount;
    state.modelTotal = next.modelTotal;
    state.roles = next.roles;
    state.trips = next.trips;
    state.status = next.status;
    state.error = "";
    state.updatedAt = new Date();
    if (state.selectedId) {
      const detail = await asset(state.selectedId);
      if (!detail) state.selectedId = null;
      state.detail = detail;
    }
  } catch (error) {
    state.error = error.message || "無法讀取監控資料。";
  }
  paint();
}

function diffSummary(previous, next) {
  if (!previous || !next) return [];
  const events = [];
  for (const [key, label] of STATS) {
    if (previous[key] !== next[key]) {
      events.push({
        at: new Date(),
        text: `${label}由 ${previous[key]} 變為 ${next[key]}`,
      });
    }
  }
  return events;
}

function paint() {
  renderChrome();
  const stage = document.querySelector("[data-stage]");
  const active = document.activeElement;
  const typing = stage && stage.contains(active) && active.matches("input, select, textarea");
  if (!typing || !stage.childElementCount) renderStage();
  else refreshResults();
}

function renderChrome() {
  document.querySelector("#view-title").textContent = TITLES[state.view] || "監控";
  const status = document.querySelector("#status-line");
  if (state.error) {
    status.textContent = state.error;
  } else if (state.updatedAt) {
    const provider = !state.status
      ? ""
      : state.status.provider === "openai"
        ? `視覺模型 · ${state.status.openai_model}`
        : "技術預檢";
    status.textContent = `更新於 ${clock(state.updatedAt)} · ${provider}`;
  }
  const path = document.querySelector("#library-path");
  const libraryPath = state.status ? state.status.library_path : "";
  path.textContent = libraryPath;
  path.setAttribute("title", libraryPath);
  document.querySelector("#live-dot").classList.toggle("is-paused", !state.live);
  document.querySelector("#live-toggle").textContent = state.live ? "暫停更新" : "繼續更新";
}

function renderStage() {
  const stage = document.querySelector("[data-stage]");
  const view = {
    overview: () => renderOverview(state),
    library: () => renderLibrary(state, actions),
    models: () => renderModels(state, actions),
    activity: () => renderActivity(state),
  }[state.view];
  stage.replaceChildren(view());
}

function refreshResults() {
  const slot = document.querySelector("[data-results]");
  if (!slot) return;
  const replacement =
    state.view === "library"
      ? renderLibraryResults(state, actions)
      : state.view === "models"
        ? renderModelsResults(state)
        : null;
  if (replacement) slot.replaceChildren(replacement);
}

tick(true);
window.setInterval(() => tick(false), 3000);
