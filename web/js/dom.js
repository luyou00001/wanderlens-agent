export function h(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  const { text, attrs, on } = options;
  if (text !== undefined && text !== null) {
    node.textContent = String(text);
  }
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value === false || value == null) continue;
      if (key === "className") node.className = String(value);
      else node.setAttribute(key, value === true ? "" : String(value));
    }
  }
  if (on) {
    for (const [type, handler] of Object.entries(on)) {
      node.addEventListener(type, handler);
    }
  }
  const list = Array.isArray(children) ? children : [children];
  for (const child of list) {
    if (child == null || child === false) continue;
    node.append(child);
  }
  return node;
}
