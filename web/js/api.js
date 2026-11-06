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
  const response = await fetch(`/api/assets/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (response.status === 404) return null;
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "無法讀取素材。");
  }
  return payload;
}

export async function loadSnapshot(filters) {
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
