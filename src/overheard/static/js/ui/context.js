// The lookup panel: the case system, searched by hand (by name, phone or case number).
import { api } from "../core/api.js";
import { el, phone, put } from "../core/format.js";

export function renderContext(root) {
  const results = el("div", { class: "results" });
  const box = el("input", { type: "search", placeholder: "Name, phone or case number", "aria-label": "Look up a case" });
  let pending;
  box.addEventListener("input", () => {
    clearTimeout(pending);
    pending = setTimeout(async () => {
      const q = box.value.trim();
      if (q.length < 3) { put(results); return; }
      const cases = await api.lookup(q);
      put(results, ...(cases.length ? cases.map(card) : [el("p", { class: "muted" }, "No matching case.")]));
    }, 250);
  });
  put(root, el("div", { class: "pane-head" }, el("h2", {}, "Case lookup")), box, results);
}

function card(c) {
  return el("article", { class: "case" },
    el("header", {}, el("b", {}, c.name), " ", el("span", { class: "muted" }, `${c.id} · ${phone(c.phone)}`)),
    el("p", {}, el("span", { class: "muted" }, "Status: "), c.status),
    c.payments.length ? el("table", {}, el("tbody", {}, c.payments.map((p) =>
      el("tr", {}, el("td", {}, p.date), el("td", {}, `$${p.amount.toFixed(2)}`), el("td", {}, p.status))))) : null,
    c.docs.length ? el("ul", {}, c.docs.map((d) => el("li", {}, `${d.name}: ${d.received ? `received ${d.received}` : "not received"}`))) : null,
    el("p", { class: "muted" }, `Last action: ${c.lastAction} · team: ${c.team}`),
  );
}
