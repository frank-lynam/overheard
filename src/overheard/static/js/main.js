import { api } from "./core/api.js";
import { createStore } from "./core/store.js";
import { renderContext, bindResolutionBump } from "./ui/context.js";
import { renderMessage } from "./ui/message.js";
import { renderQueue } from "./ui/queue.js";
import { renderScoreboard } from "./ui/scoreboard.js";
import { renderRootCauses, renderEventImpact, renderJourneys, renderPromises, renderEquity, renderLetterLab, renderAsk, renderKnowledgeGaps } from "./ui/mode3.js";

const store = createStore({ mode: 0, queue: [], selected: null, sim: null, touches: null, simClock: null, pace: null, today: null, assumptions: null, incidents: null });
const buttons = [...document.querySelectorAll(".stepper button")];
buttons.forEach((b) => b.addEventListener("click", () => store.set({ mode: Number(b.dataset.mode) })));
document.addEventListener("keydown", (e) => {
  if (["1", "2", "3", "4"].includes(e.key) && !e.target.closest("input, textarea, select")) store.set({ mode: Number(e.key) - 1 });
});
store.subscribe(({ mode }) => {
  buttons.forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.mode) === mode)));
  document.body.dataset.mode = mode;
  document.querySelector(".later").hidden = mode >= 1;
  const m3 = document.querySelector(".mode3");
  const wb = document.querySelector(".workbench");
  if (m3) m3.hidden = mode !== 3;
  wb.hidden = mode === 3 && !!m3;
  if (mode === 3 && m3) {
    const pane = m3.querySelector(".m3-pane.root-causes");
    if (pane.dataset.loaded !== "1") {
      api.rootCauses().then((data) => {
        pane.dataset.loaded = "1";
        renderRootCauses(pane, data);
      }).catch(() => {});
    }
    const epane = m3.querySelector(".m3-pane.event-impact");
    if (epane.dataset.loaded !== "1") {
      api.eventImpact().then((data) => {
        epane.dataset.loaded = "1";
        renderEventImpact(epane, data);
      }).catch(() => {});
    }
    const jpane = m3.querySelector(".m3-pane.journeys");
    if (jpane.dataset.loaded !== "1") {
      api.journeys().then((data) => {
        jpane.dataset.loaded = "1";
        renderJourneys(jpane, data);
      }).catch(() => {});
    }
    const ppane = m3.querySelector(".m3-pane.promises");
    if (ppane.dataset.loaded !== "1") {
      api.promises().then((data) => {
        ppane.dataset.loaded = "1";
        renderPromises(ppane, data);
      }).catch(() => {});
    }
    const qpane = m3.querySelector(".m3-pane.equity");
    if (qpane.dataset.loaded !== "1") {
      api.equity().then((data) => {
        qpane.dataset.loaded = "1";
        renderEquity(qpane, data);
      }).catch(() => {});
    }
    const lpane = m3.querySelector(".m3-pane.letter-lab");
    if (lpane.dataset.loaded !== "1") {
      lpane.dataset.loaded = "1";
      renderLetterLab(lpane);
    }
    const ap = m3.querySelector(".m3-pane.ask");
    if (ap.dataset.loaded !== "1") {
      ap.dataset.loaded = "1";
      renderAsk(ap);
    }
    const gpane = m3.querySelector(".m3-pane.knowledge-gaps");
    if (gpane.dataset.loaded !== "1") {
      api.knowledgeGaps().then((data) => {
        gpane.dataset.loaded = "1";
        renderKnowledgeGaps(gpane, data);
      }).catch(() => {});
    }
  }
}, ["mode"]);

renderQueue(document.querySelector(".pane.queue"), store);
renderMessage(document.querySelector(".pane.message"), store);
renderContext(document.querySelector(".pane.context"), store);
bindResolutionBump(store);
renderScoreboard(document.querySelector(".scoreboard"), store);

const refresh = async () => store.set({ queue: await api.queue(store.get().mode) });
// mode 1: the same day, re-ordered by the AI's urgency (so the re-sort animation can slide)
store.subscribe(() => { api.queue(1).then((q) => { if (store.get().mode === 1) store.set({ queue: q }); }).catch(() => {}); }, ["mode"]);
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
