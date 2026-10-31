// The scoreboard: computed from the simulation and the assumptions, never typed in —
// except the handling time, which the presenter adjusts to see the whole day move.
import { api } from "../core/api.js";
import { clock, el, hm, put } from "../core/format.js";

export function renderScoreboard(root, store) {
  // One persistent input for the handling time, so typing in it doesn't flicker it.
  const handleInput = el("input", {
    type: "number", min: 0.5, step: 0.5, style: "width: 3.5rem", "aria-label": "Handling minutes per message",
  });
  handleInput.addEventListener("input", () => {
    const v = Math.max(0, Number(handleInput.value) || 0);
    const a = store.get().assumptions;
    if (a && a.handleMin !== v) {
      // The input node survives the rebuild (it's created once, above), so focus and
      // the value this keystroke just typed are kept; the board just re-extrapolates.
      store.set({ assumptions: { ...a, handleMin: v } });
      api.saveAssumptions({ ...a, handleMin: v }).catch(() => {});
    }
  });

  store.subscribe((s) => {
    const sim = s.sim;
    const stat = (label, value, note) => el("div", { class: "stat" }, el("span", { class: "label" }, label),
      el("b", {}, value), note ? el("span", { class: "note" }, note) : null);
    if (!s.queue.length) { put(root, el("span", { class: "muted" }, "scoreboard")); return; }
    if (s.assumptions && handleInput.value !== String(s.assumptions.handleMin)) handleInput.value = String(s.assumptions.handleMin);
    const stats = [
      sim ? stat("Agent hours", sim.agentHours.toFixed(1), `$${Math.round(sim.dollarsPerDay)} a day`)
        : stat("Agent hours", "?", "run “Work the queue” to time the day"),
    ];
    if (sim) {
      stats.push(
        stat("Urgent reached", sim.urgentFirstTouch ? clock(sim.urgentFirstTouch) : "not today",
          sim.urgentWaitMin != null ? `${hm(sim.urgentWaitMin)} after the call` : null),
        stat("Deadline-bound", `${sim.obligationsCaught} caught · ${sim.obligationsMissed} missed`),
        stat("Not reached", String(sim.unreached), "by end of shift"),
      );
    }
    if (s.assumptions) {
      const a = s.assumptions;
      // The same arithmetic as the simulation, straight from the day's queue: every message
      // costs its listening plus the handling time, and most need a callback.
      const listen = s.queue.reduce((n, m) => n + m.durationSec / 60, 0);
      const minutes = listen + s.queue.length * (a.handleMin + a.callbackMin);
      stats.push(el("div", { class: "stat" }, el("span", { class: "label" }, "Workload clock"),
        el("b", {}, hm(minutes)),
        el("span", { class: "note" }, `${s.queue.length} messages · `), handleInput,
        el("span", { class: "note" }, ` min handling each, ${hm(a.callbackMin)} a callback`)));
    }
    if (s.pace) stats.push(stat("Your pace", `${hm(s.pace / 60)}`, "per message"));
    put(root, ...stats);
  }, ["sim", "pace", "queue", "assumptions"]);
}