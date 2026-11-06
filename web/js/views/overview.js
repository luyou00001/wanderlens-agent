import { h } from "../dom.js";
import { STATS, bytes, count, mediaLabel, providerLabel, when } from "../format.js";

export function renderOverview(state) {
  const summary = state.summary || {};
  const assets = Number(summary.assets) || 0;
  const described = Number(summary.described) || 0;
  const ratio = assets ? Math.round((described / assets) * 100) : 0;
  const fill = h("span", { attrs: { className: "meter-fill" } });
  fill.style.width = `${ratio}%`;

  return h("div", { attrs: { className: "stack" } }, [
    state.summary && state.summary.library_error ? banner(state.summary.library_error) : null,
    h("section", { attrs: { className: "stat-grid" } }, STATS.map(([key, label]) => stat(label, summary[key], key))),
    h("div", { attrs: { className: "split" } }, [
      h("section", { attrs: { className: "panel" } }, [
        h("h2", { attrs: { className: "panel-title" }, text: "描述進度" }),
        h("div", { attrs: { className: "meter" } }, [fill]),
        h("p", {
          attrs: { className: "meta" },
          text: assets
            ? `已有畫面描述 ${described} / ${assets}（${ratio}%）。技術預檢不算看過畫面。`
            : "索引裡還沒有素材。",
        }),
        h("p", {
          attrs: { className: "meta" },
          text: "含定位的檔案只標成「有」。這個頁面不顯示經緯度，也不把照片放上地圖。",
        }),
      ]),
      h("section", { attrs: { className: "panel" } }, [
        h("h2", { attrs: { className: "panel-title" }, text: "行程" }),
        renderTrips(state.trips || []),
      ]),
    ]),
    h("section", { attrs: { className: "panel" } }, [
      h("h2", { attrs: { className: "panel-title" }, text: "最近的素材" }),
      renderRecent(state.assets || []),
    ]),
  ]);
}

function stat(label, value, key) {
  return h("article", { attrs: { className: "stat" } }, [
    h("p", { attrs: { className: "stat-label" }, text: label }),
    h("p", { attrs: { className: "stat-value" }, text: count(value) }),
    key === "with_gps" ? h("p", { attrs: { className: "stat-hint" }, text: "不顯示座標" }) : null,
  ]);
}

function renderTrips(trips) {
  if (!trips.length) {
    return h("p", { attrs: { className: "empty" }, text: "尚未分出行程。" });
  }
  return h(
    "div",
    { attrs: { className: "stack" } },
    trips.slice(0, 6).map((trip) =>
      h("p", {
        attrs: { className: "meta" },
        text: `${trip.place || trip.id || "尚未分行程"} · ${trip.assets} 筆 · ${when(trip.captured_from)}`,
      }),
    ),
  );
}

function renderRecent(assets) {
  if (!assets.length) {
    return h("p", { attrs: { className: "empty" }, text: "放入照片後執行 wanderlens ingest，這裡會開始更新。" });
  }
  return h("div", { attrs: { className: "table-wrap" } }, [
    h("table", {}, [
      h("thead", {}, [
        h("tr", {}, [
          h("th", { text: "檔案" }),
          h("th", { text: "類型" }),
          h("th", { text: "描述" }),
          h("th", { text: "大小" }),
        ]),
      ]),
      h(
        "tbody",
        {},
        assets.slice(0, 8).map((asset) =>
          h("tr", {}, [
            h("td", { attrs: { className: "path" }, text: asset.relative_path || asset.id }),
            h("td", { text: mediaLabel(asset.media_type) }),
            h("td", { text: providerLabel(asset.provider) }),
            h("td", { text: bytes(asset.byte_size) }),
          ]),
        ),
      ),
    ]),
  ]);
}

function banner(text) {
  return h("p", { attrs: { className: "banner", role: "status" }, text });
}
