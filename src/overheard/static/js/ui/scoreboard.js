// The scoreboard: computed from the simulation and the assumptions, never typed in.
import { clock, el, hm, put } from "../core/format.js";

export function renderScoreboard(root, store) {
  store.subscribe((s) => {
    const sim = s.sim;
    const stat = (label, value, note) => el("div", { class: "stat" }, el("span", { class: "label" }, label),
      el("b", {}, value), note ? el("span", { class: "note" }, note) : null);
    if (!sim) { put(root, el("span", { class: "muted" }, "Work the queue to see what it costs.")); return; }
    put(root, 
      stat("Agent hours", sim.agentHours.toFixed(1), `$${Math.round(sim.dollarsPerDay)} a day`),
      stat("Urgent reached", sim.urgentFirstTouch ? clock(sim.urgentFirstTouch) : "not today",
        sim.urgentWaitMin != null ? `${hm(sim.urgentWaitMin)} after the call` : null),
      stat("Deadline-bound", `${sim.obligationsCaught} caught · ${sim.obligationsMissed} missed`),
      stat("Not reached", String(sim.unreached), "by end of shift"),
      s.pace ? stat("Your pace", `${hm(s.pace / 60)}`, "per message") : null,
    );
  }, ["sim", "pace"]);
}
