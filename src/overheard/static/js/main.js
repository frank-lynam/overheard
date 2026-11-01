import { api } from "./core/api.js";
import { createStore } from "./core/store.js";
import { renderContext, bindResolutionBump } from "./ui/context.js";
import { renderMessage } from "./ui/message.js";
import { renderQueue } from "./ui/queue.js";
import { renderScoreboard } from "./ui/scoreboard.js";
import { renderRootCauses, renderEventImpact, renderJourneys, renderPromises, renderEquity, renderLetterLab, renderAsk, renderKnowledgeGaps, renderWeakSignals, renderStaffingForecast } from "./ui/mode3.js";

const store = createStore({ mode: 0, queue: [], selected: null, sim: null, touches: null, simClock: null, pace: null, today: null, assumptions: null, incidents: null });
const buttons = [...document.querySelectorAll(".stepper button")];
buttons.forEach((b) => b.addEventListener("click", () => store.set({ mode: Number(b.dataset.mode) })));
document.addEventListener("keydown", (e) => {
  if (["1", "2", "3", "4"].includes(e.key) && !e.target.closest("input, textarea, select")) store.set({ mode: Number(e.key) - 1 });
});
// Mode 3: the archive is a tabbed dashboard. Each pane loads only when its tab
// is opened, and stays rendered (cached) for the rest of the session.
const M3_PANES = {
  "root-causes": { api: api.rootCauses, render: renderRootCauses },
  "event-impact": { api: api.eventImpact, render: renderEventImpact },
  journeys: { api: api.journeys, render: renderJourneys },
  promises: { api: api.promises, render: renderPromises },
  equity: { api: api.equity, render: renderEquity },
  "letter-lab": { render: renderLetterLab },
  ask: { render: renderAsk },
  "knowledge-gaps": { api: api.knowledgeGaps, render: renderKnowledgeGaps },
  "weak-signals": { api: api.weakSignals, render: renderWeakSignals },
  "staffing-forecast": { api: api.staffingForecast, render: renderStaffingForecast },
};
let m3Active = "root-causes";
function loadM3Pane(pane) {
  if (pane.dataset.loaded === "1") return;
  const spec = M3_PANES[pane.dataset.pane];
  if (!spec) return;
  const done = (data) => {
    if (pane.dataset.loaded !== "1") {
      pane.dataset.loaded = "1";
      spec.render(pane, data);
    }
  };
  if (spec.api) spec.api().then(done).catch(() => {});
  else done();
}
function selectM3Pane(m3, name) {
  if (!M3_PANES[name]) name = "root-causes";
  m3Active = name;
  m3.querySelectorAll(".m3-tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.pane === name)));
  m3.querySelectorAll(".m3-pane").forEach((p) => {
    p.hidden = p.dataset.pane !== name;
  });
  loadM3Pane(m3.querySelector(`.m3-pane[data-pane="${name}"]`));
  m3.querySelector(`.m3-tab[data-pane="${name}"]`)?.focus();
}
store.subscribe(({ mode }) => {
  buttons.forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.mode) === mode)));
  document.body.dataset.mode = mode;
  const m3 = document.querySelector(".mode3");
  m3.hidden = mode !== 3;
  document.querySelector(".workbench").hidden = mode === 3;
  if (mode === 3) selectM3Pane(m3, m3Active);
}, ["mode"]);
{
  const m3 = document.querySelector(".mode3");
  const tabs = [...m3.querySelectorAll(".m3-tab")];
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => selectM3Pane(m3, t.dataset.pane));
    t.addEventListener("keydown", (e) => {
      const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      tabs[(i + d + tabs.length) % tabs.length].click();
    });
  });
}

renderQueue(document.querySelector(".pane.queue"), store);
renderMessage(document.querySelector(".pane.message"), store);
renderContext(document.querySelector(".pane.context"), store);
bindResolutionBump(store);
renderScoreboard(document.querySelector(".scoreboard"), store);

const refresh = async () => store.set({ queue: await api.queue(store.get().mode) });
// mode 0: back to arrival order; mode 1: the same day, re-ordered by the AI's urgency (so the re-sort animation can slide)
store.subscribe((s) => {
  if (s.mode > 1) return;
  api.queue(s.mode).then((q) => { if (store.get().mode === s.mode) store.set({ queue: q }); }).catch(() => {});
}, ["mode"]);
// mode 2: the day's cross-message reasoning (clusters, repeats, the incident) comes with the queue
store.subscribe((s) => {
  if (s.mode !== 2) return;
  api.queue(2).then((q) => { if (store.get().mode === 2) store.set({ queue: q }); }).catch(() => {});
  api.incidents().then((inc) => store.set({ incidents: inc })).catch(() => {});
}, ["mode"]);
store.on("saved", async ({ seconds }) => {
  const times = (store.get()._times || []).concat(seconds);
  store.set({ _times: times, pace: times.reduce((a, b) => a + b, 0) / times.length });
  await refresh();
});

// "Work the queue": fast-forward one simulated agent through the day, stamping each message as it's reached.
store.on("simulate", async () => {
  const sim = await api.simulation(store.get().mode);
  const touches = {};
  store.set({ touches, sim: null });
  const reached = sim.touches.filter((t) => t.firstTouch);
  for (const t of reached) {
    touches[t.id] = { at: t.firstTouch, late: t.id === sim.urgentId };
    store.set({ touches: { ...touches }, simClock: t.firstTouch });
    document.querySelector(`[data-id="${t.id}"]`)?.scrollIntoView({ block: "nearest" });
    await new Promise((r) => setTimeout(r, 120));
  }
  for (const t of sim.touches.filter((x) => !x.firstTouch)) touches[t.id] = { at: null, late: true };
  store.set({ touches: { ...touches }, sim, simClock: null });
});

(async () => {
  const [day, assumptions] = await Promise.all([api.day(), api.assumptions()]);
  store.set({ today: day.date, assumptions });
  await refresh();
  store.set({ sim: await api.simulation(store.get().mode) });
})();
