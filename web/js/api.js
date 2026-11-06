let previewSnapshot = null;

export async function getJSON(path) {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const message = payload && payload.error ? payload.error : `讀取失敗（${response.status}）`;
    throw new Error(message);
  }
  return payload;
}

export async function asset(id) {
  if (previewSnapshot) {
    return previewSnapshot.assets.find((item) => item.id === id) || null;
  }
  const response = await fetch(`/api/assets/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (response.status === 404) return null;
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "無法讀取素材。");
  }
  return payload;
}

export async function loadSnapshot(filters, options = {}) {
  if (options.refresh) previewSnapshot = null;
  if (!previewSnapshot) {
    try {
      const live = await loadLive(filters);
      return { preview: false, notice: "", ...live };
    } catch (error) {
      previewSnapshot = await loadPreview();
      previewSnapshot.previewError = error.message;
    }
  }
  return applyFilters(previewSnapshot, filters);
}

async function loadLive(filters) {
  const assetsQuery = new URLSearchParams({ limit: "200" });
  if (filters.libraryQuery) assetsQuery.set("q", filters.libraryQuery);
  const modelsQuery = new URLSearchParams();
  if (filters.role) modelsQuery.set("role", filters.role);
  if (filters.commercial) modelsQuery.set("commercial", filters.commercial);
  if (filters.modelQuery) modelsQuery.set("query", filters.modelQuery);
  const [status, summary, assets, models, trips] = await Promise.all([
    getJSON("/api/status"),
    getJSON("/api/summary"),
    getJSON(`/api/assets?${assetsQuery}`),
    getJSON(`/api/models?${modelsQuery}`),
    getJSON("/api/trips"),
  ]);
  return {
    status,
    summary,
    assets: assets.assets || [],
    assetTotal: assets.total || 0,
    models: models.models || [],
    modelCount: models.count || 0,
    modelTotal: models.total || 0,
    roles: models.roles || [],
    trips: trips.trips || [],
  };
}

async function loadPreview() {
  const url = new URL("preview/snapshot.json", document.baseURI);
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("無法讀取預覽資料。");
  const payload = await response.json();
  if (!payload || payload.preview !== true || !Array.isArray(payload.assets)) {
    throw new Error("預覽資料格式不正確。");
  }
  return payload;
}

function applyFilters(snapshot, filters) {
  const needle = (filters.libraryQuery || "").trim().toLowerCase();
  const assets = snapshot.assets.filter((item) => {
    if (!needle) return true;
    const haystack = [item.id, item.relative_path, item.user_place, item.trip_id, item.summary_zh_hant]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(needle);
  });
  const query = (filters.modelQuery || "").trim().toLowerCase();
  const models = snapshot.models.filter((model) => {
    if (filters.role && !(model.roles || []).includes(filters.role)) return false;
    if (filters.commercial && model.commercial_use !== filters.commercial) return false;
    if (!query) return true;
    const haystack = [model.id, model.name, model.huggingface, model.github, model.notes, ...(model.roles || [])]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
  return {
    preview: true,
    notice: snapshot.notice || "",
    status: snapshot.status,
    summary: snapshot.summary,
    assets,
    assetTotal: assets.length,
    models,
    modelCount: models.length,
    modelTotal: snapshot.models.length,
    roles: snapshot.roles || [],
    trips: snapshot.trips || [],
  };
}
