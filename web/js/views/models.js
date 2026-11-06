import { h } from "../dom.js";
import { commercialLabel, commercialTone, roleLabel, statusLabel } from "../format.js";

const CHOICES = [
  ["", "全部"],
  ["allowed", "可商用"],
  ["disallowed", "不可商用"],
  ["conditional", "附條件"],
  ["unknown", "未確認"],
];

export function renderModels(state, actions) {
  const roles = [""].concat(state.roles || []);
  return h("div", { attrs: { className: "stack" } }, [
    h("p", {
      attrs: { className: "banner" },
      text: "限制使用的權重只供本機實驗。不要用來產生要販售的圖片、影片、配樂或文案。授權欄位是閱讀筆記，不是法律意見。",
    }),
    h("div", { attrs: { className: "toolbar" } }, [
      h(
        "select",
        {
          attrs: { className: "select", "aria-label": "依用途篩選" },
          on: { change: (event) => actions.setFilter("role", event.target.value) },
        },
        roles.map((role) =>
          h("option", {
            attrs: { value: role, selected: state.filters.role === role },
            text: role ? roleLabel(role) : "全部用途",
          }),
        ),
      ),
      ...CHOICES.map(([value, label]) =>
        h("button", {
          attrs: {
            className: state.filters.commercial === value ? "choice is-current" : "choice",
            type: "button",
          },
          text: label,
          on: { click: () => actions.setFilter("commercial", value) },
        }),
      ),
      h("input", {
        attrs: {
          className: "field",
          type: "search",
          placeholder: "搜尋模型名稱或說明",
          value: state.filters.modelQuery,
          "aria-label": "搜尋模型",
        },
        on: { input: (event) => actions.setFilter("modelQuery", event.target.value) },
      }),
    ]),
    h("div", { attrs: { "data-results": "models" } }, [renderModelsResults(state)]),
  ]);
}

export function renderModelsResults(state) {
  const models = state.models || [];
  return h("div", { attrs: { className: "stack" } }, [
    h("p", {
      attrs: { className: "meta" },
      text: `顯示 ${state.modelCount} 項，清單共 ${state.modelTotal} 項。`,
    }),
    models.length
      ? h("div", { attrs: { className: "table-wrap" } }, [
          h("table", {}, [
            h("thead", {}, [
              h("tr", {}, ["狀態", "授權", "模型", "用途", "顯存"].map((label) => h("th", { text: label }))),
            ]),
            h(
              "tbody",
              {},
              models.map((model) =>
                h("tr", {}, [
                  h("td", { text: statusLabel(model.status) }),
                  h("td", {}, [
                    h("span", {
                      attrs: { className: `tag ${commercialTone(model.commercial_use)}` },
                      text: commercialLabel(model.commercial_use),
                    }),
                  ]),
                  h("td", {}, [
                    h("div", { text: model.name || model.id }),
                    h("div", { attrs: { className: "path" }, text: model.huggingface || model.github || model.id }),
                  ]),
                  h("td", { text: (model.roles || []).map(roleLabel).join("、") }),
                  h("td", { text: model.min_vram_gb_estimate == null ? "—" : `${model.min_vram_gb_estimate} GB` }),
                ]),
              ),
            ),
          ]),
        ])
      : h("p", { attrs: { className: "empty" }, text: "沒有符合條件的模型。" }),
  ]);
}
