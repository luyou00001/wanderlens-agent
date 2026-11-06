import { h } from "../dom.js";
import { bytes, mediaLabel, peopleLabel, providerLabel, when } from "../format.js";

export function renderLibrary(state, actions) {
  return h("div", { attrs: { className: "stack" } }, [
    h("div", { attrs: { className: "toolbar" } }, [
      h("input", {
        attrs: {
          className: "field",
          type: "search",
          placeholder: "搜尋路徑、行程或地點標記",
          value: state.filters.libraryQuery,
          "aria-label": "搜尋素材",
        },
        on: {
          input: (event) => actions.setFilter("libraryQuery", event.target.value),
        },
      }),
      h("p", { attrs: { className: "meta" }, text: `顯示 ${state.assets.length} / ${state.assetTotal}` }),
    ]),
    h("div", { attrs: { "data-results": "library" } }, [renderLibraryResults(state, actions)]),
  ]);
}

export function renderLibraryResults(state, actions) {
  const layoutClass = state.selectedId ? "library-layout has-detail" : "library-layout";
  return h("div", { attrs: { className: layoutClass } }, [
    h("div", { attrs: { className: "table-wrap" } }, [renderTable(state, actions)]),
    state.selectedId ? renderDetail(state, actions) : null,
  ]);
}

function renderTable(state, actions) {
  if (!state.assets.length) {
    return h("p", { attrs: { className: "empty" }, text: "沒有符合條件的素材。" });
  }
  return h("table", {}, [
    h("thead", {}, [
      h("tr", {}, ["檔案", "類型", "拍攝", "描述", "人物", "販售"].map((label) => h("th", { text: label }))),
    ]),
    h(
      "tbody",
      {},
      state.assets.map((asset) => {
        const selected = state.selectedId === asset.id;
        return h(
          "tr",
          {
            attrs: { className: selected ? "is-selected" : "", tabindex: "0" },
            on: {
              click: () => actions.selectAsset(selected ? null : asset.id),
              keydown: (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  actions.selectAsset(selected ? null : asset.id);
                }
              },
            },
          },
          [
            h("td", { attrs: { className: "path" }, text: asset.relative_path || asset.id }),
            h("td", { text: mediaLabel(asset.media_type) }),
            h("td", { text: when(asset.captured_at) }),
            h("td", { text: providerLabel(asset.provider) }),
            h("td", { text: peopleLabel(asset.people) }),
            h("td", { text: asset.cleared_for_sale ? "可進入草稿包" : "未標記" }),
          ],
        );
      }),
    ),
  ]);
}

function renderDetail(state, actions) {
  const asset = state.detail;
  if (!asset) {
    return h("aside", { attrs: { className: "panel" } }, [
      h("h2", { attrs: { className: "panel-title" }, text: "素材" }),
      h("p", { attrs: { className: "meta" }, text: "正在讀取。" }),
    ]);
  }
  const rows = [
    ["路徑", asset.relative_path],
    ["行程", asset.trip_id || "尚未分行程"],
    ["地點標記", asset.user_place || "尚未填寫"],
    ["相機", asset.camera_model || "沒有"],
    ["定位", asset.has_gps ? "有，座標留在本機索引" : "沒有"],
    ["描述", providerLabel(asset.provider)],
    ["模型", asset.model || "—"],
    ["人物", peopleLabel(asset.people)],
    ["敏感內容", asset.sensitive === true ? "是" : asset.sensitive === false ? "否" : "尚未判斷"],
    ["發佈", asset.approved_for_publish ? "已核准" : "未核准"],
  ];
  return h("aside", { attrs: { className: "panel" } }, [
    h("div", { attrs: { className: "toolbar" } }, [
      h("h2", { attrs: { className: "panel-title" }, text: asset.id }),
      h("button", {
        attrs: { className: "button", type: "button" },
        text: "關閉",
        on: { click: () => actions.selectAsset(null) },
      }),
    ]),
    h(
      "dl",
      { attrs: { className: "definition" } },
      rows.flatMap(([label, value]) => [h("dt", { text: label }), h("dd", { text: value || "—" })]),
    ),
    asset.summary_zh_hant
      ? h("p", { attrs: { className: "meta" }, text: asset.summary_zh_hant })
      : null,
    asset.byte_size != null ? h("p", { attrs: { className: "meta" }, text: bytes(asset.byte_size) }) : null,
    ...(asset.drafts || []).slice(0, 4).map((draft) =>
      h("article", { attrs: { className: "draft" } }, [
        h("p", { attrs: { className: "meta" }, text: `${draft.platform || ""} · ${draft.language || ""}` }),
        h("p", { text: draft.title || "沒有標題" }),
      ]),
    ),
  ]);
}
