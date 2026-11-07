// The right-hand pane.
// Mode 0: the case system, searched by hand (by name, phone or case number).
// Mode 2: the work the AI has already done for the open message — its lookups,
// its draft reply (a human approves before anything goes out), the obligation
// clocks, the callback window, the rules that apply, and the brief for the calls that still happen.
// The manual case search stays below in every mode.
import { api } from "../core/api.js";
import { clock, day, el, hm, phone, put } from "../core/format.js";
import { DEADLINES, plain } from "../core/words.js";

export function renderContext(root, store) {
  const resolution = el("div", { class: "mode2-panels" });

  const lookup = el("div", { class: "lookup" });
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

  store.subscribe(async (s) => {
    if (s.mode !== 2 || !s.selected) { put(resolution); return; }
    put(resolution, el("span", { class: "muted" }, `thinking over ${s.selected}…`));
    let r;
    try { r = await api.resolution(s.selected); } catch { put(resolution); return; }
    drawResolution(resolution, r, s);
  }, ["selected", "mode", "resolutionBump"]);

  put(root,
    el("div", { class: "pane-head" }, el("h2", {}, "Context")),
    resolution,
    el("h3", {}, "Case lookup"),
    box,
    results,
  );
}

const PROV = {
  mock: ["AI · demo", "Demo mode: made offline from the day's script, with a realistic share of mistakes"],
  llm: ["AI", "Written by the AI model, live"],
  fallback: ["fallback", "The AI's answer didn't check out, so this is a safe stand-in"],
  human: ["edited", "A person changed what the AI said"],
};
function badge(prov) {
  const [text, tip] = PROV[prov] ?? [prov, ""];
  return el("span", { class: `prov prov-${prov}`, "data-tip": tip }, text);
}

function drawResolution(root, r, s) {
  const o = r.resolution;
  const kids = [];

  if (o.resolvable) {
    const draft = el("textarea", { class: "draft-reply", rows: 4 }, o.reply);
    const actions = el("div", { class: "form-actions" },
      el("button", { type: "submit", "data-tip": "Send this reply and close the message: no callback needed" }, "Approve & send"),
      el("button", { class: "small", "data-tip": "Don't send it; the message goes back to the queue for a callback" }, "Reject"));
    const form = el("form", { class: "approve-form", onsubmit: async (e) => {
      e.preventDefault();
      const btn = form.querySelector("button[type=submit]");
      btn.disabled = true; btn.textContent = "Approving…";
      await api.setResolution(r.voicemail, "approved", draft.value);
      store_bump();
    } });
    form.append(draft, actions);
    if (r.state === "approved") form.hidden = true;
    kids.push(el("section", { class: "ai-panel" },
      el("header", { class: "ai-panel-head" }, el("b", { "data-tip": "The AI looked the caller up and the case record already answers the question" }, "Answer found in the record"), badge(o.provenance)),
      el("p", { class: "ai-line" }, `The lookups${o.caseId ? ` (case ${o.caseId}, status: ${o.caseStatus})` : ""} answer it: ${o.answer}`),
      o.beliefMismatch ? el("p", { class: "ai-line mismatch" }, `The caller thinks “${o.beliefMismatch}” — the record disagrees.`) : null,
      r.state === "approved"
        ? el("p", { class: "state approved" }, `Approved ${r.at ? `· ${r.at}` : ""} — the reply goes out, no callback needed.`)
        : el("p", { class: "muted" }, "Suggested reply: nothing is sent until a person approves it."),
      form));
  } else {
    kids.push(el("section", { class: "ai-panel" },
      el("header", { class: "ai-panel-head" }, el("b", { "data-tip": "The record doesn't answer it, so a person calls back; the AI has prepared the call" }, "Still needs a call"), badge(o.provenance)),
      el("p", { class: "ai-line muted" }, `Checked: ${o.lookups.length ? o.lookups.map((l) => l.tool.replace(/_/g, " ")).join(", ") : "nothing"} · ${o.answer}`),
      el("p", { class: "ai-line bold-b" }, el("b", { "data-tip": "What to know before dialling, so the call is short" }, "Before you call: "), o.brief)));
  }

  if (o.callbackWindow?.when) {
    kids.push(el("section", { class: "ai-panel window-panel" },
      el("header", { class: "ai-panel-head" }, el("b", { "data-tip": "When the caller said they can be reached" }, "Best time to call")),
      el("p", { class: "ai-line" }, `They asked for ${o.callbackWindow.when}: that's ${o.callbackWindow.at}.`)));
  }

  if (r.obligations?.length) {
    kids.push(el("section", { class: "ai-panel" },
      el("header", { class: "ai-panel-head" }, el("b", { "data-tip": "Requests the agency must answer by a set date" }, "Has a deadline")),
      r.obligations.map((ob) =>
        el("p", { class: "ai-line clock",
          "data-tip": `${DEADLINES[ob.kind]?.[1] ?? ""}${ob.evidence ? `. Heard: “${ob.evidence}”` : ""}` },
          `${DEADLINES[ob.kind]?.[0] ?? plain(ob.kind)}: due ${ob.due.includes("T") ? clock(ob.due) : day(ob.due)}`))));
  }

  const ap = (r.applies?.verdicts || []).filter((a) => a.verdict !== "does_not_apply");
  if (ap.length) {
    const WORD = { applies: "applies", unsure: "unsure: a person decides" };
    kids.push(el("section", { class: "ai-panel" },
      el("header", { class: "ai-panel-head" }, el("b", { "data-tip": "Policies, programs, notices and outages in force when they called that fit this message; the AI quotes the caller's words" }, "Applies here"), badge(r.applies.provenance)),
      el("div", { class: "applies" }, ap.map((a) =>
        el("span", { class: `chip-applies a-${a.verdict}`,
          "data-tip": `${a.reason}${a.quote ? `\nHeard: “${a.quote}”` : ""}` },
          `${a.name} · ${WORD[a.verdict]}`)))));
  }

  if (r.missingInfo) {
    kids.push(el("section", { class: "ai-panel" },
      el("header", { class: "ai-panel-head" }, el("b", { "data-tip": "Something the caller didn't say that the agent will need" }, "Missing info")),
      el("p", { class: "ai-line" }, `The caller never gave a ${r.missingInfo.needed}.`),
      r.missingInfo.recovered
        ? el("p", { class: "ai-line" }, `Recovered from the phone: case ${r.missingInfo.recovered} — no one has to ask.`)
        : el("p", { class: "ai-line muted" }, `${r.missingInfo.how} — the message needs an automatic request for it.`)));
  }

  put(root, ...kids);
}

// a little bridge so the approve form (built outside the store closure) can re-render
let store_bump = () => {};
export function bindResolutionBump(store) {
  store_bump = () => store.set({ resolutionBump: (store.get().resolutionBump || 0) + 1 });
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