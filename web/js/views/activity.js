import { h } from "../dom.js";
import { clock } from "../format.js";

export function renderActivity(state) {
  const events = state.events || [];
  return h("section", { attrs: { className: "panel" } }, [
    h("h2", { attrs: { className: "panel-title" }, text: "索引變化" }),
    h("p", {
      attrs: { className: "meta" },
      text: "這裡只記錄這次開啟監控頁之後的數字變化。重新整理瀏覽器會清空。",
    }),
    events.length
      ? h(
          "ol",
          { attrs: { className: "log" } },
          events.map((event) =>
            h("li", { attrs: { className: "log-item" } }, [
              h("time", { attrs: { className: "time" }, text: clock(event.at) }),
              h("p", { text: event.text }),
            ]),
          ),
        )
      : h("p", { attrs: { className: "empty" }, text: "數字還沒有變化。清點或描述之後，差異會出現在這裡。" }),
  ]);
}
