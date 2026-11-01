// The scoreboard: computed from the simulation and the assumptions, never typed in —
// except the handling time, which the presenter adjusts to see the whole day move.
import { api } from "../core/api.js";
import { clock, el, hm, put } from "../core/format.js";

export function renderScoreboard(root, store) {
  // One persistent input for the handling time, so typing in it doesn't flicker it.
  const handleInput = el("input", {
    type: "number", min: 0.5, step: 0.5, style: "width: 3.5rem", "aria-label": "Handling minutes per message",
  });
  let acc = null; // mode 1: the AI's scoreboard, fetched when the mode is entered

  store.subscribe((s) => {
    if (s.mode >= 1 && !acc) api.accuracy().then((a) => { acc = a; store.set({ _acc: a }); }).catch(() => {});
    if (s.mode === 2 && !s._sb2) api.scoreboard2().then((sb) => store.set({ _sb2: sb })).catch(() => {});
    if (s.mode === 0) acc = null;
  }, ["mode", "_sb2"]);
  handleInput.addEventListener("input", () => {
    const v = Math.max(0, Number(handleInput.value) || 0);
    const a = store.get().assumptions;
    if (a && a.handleMin !== v) {
      // The input node survives the rebuild (it's created once, above), so focus and
      // the value this keystroke just typed are kept; the board just re-extrapolates.
      store.set({ assumptions: { ...a, handleMin: v } });
      api.saveAssumptions({ ...a, handleMin: v }).then(() => store.emit("assumptions-saved")).catch(() => {});
    }
  });

  store.subscribe((s) => {
    const sim = s.sim;
    const base = s.mode ? s._base : null;  // Mode 0's day, to show what each later mode changes
    const stat = (label, value, note, gain) => el("div", { class: "stat" }, el("span", { class: "label" }, label),
      el("b", {}, value), note ? el("span", { class: "note" }, note) : null, gain ? el("span", { class: "note gain" }, gain) : null);
    if (!s.queue.length) { put(root, el("span", { class: "muted" }, "scoreboard")); return; }
    if (s.assumptions && handleInput.value !== String(s.assumptions.handleMin)) handleInput.value = String(s.assumptions.handleMin);
    const stats = [];
    if (!sim) stats.push(stat("The day", "?", "run “Work the queue” to see it"));
    if (sim) {
      const met = (x) => `${x.obligationsCaught} of ${x.obligationsCaught + x.obligationsMissed} met`;
      const reached = (x) => `${x.touches.length - x.unreached} of ${x.touches.length}`;
      stats.push(
        stat("Urgent caller reached", sim.urgentFirstTouch ? clock(sim.urgentFirstTouch) : "not today",
          sim.urgentWaitMin != null ? `${hm(sim.urgentWaitMin)} after they called` : null,
          base && base.urgentFirstTouch && sim.urgentWaitMin != null && sim.urgentWaitMin < base.urgentWaitMin
            ? `${hm(base.urgentWaitMin - sim.urgentWaitMin)} sooner (was ${clock(base.urgentFirstTouch)})` : null),
        stat("Deadline-bound requests", met(sim), null,
          base && sim.obligationsCaught > base.obligationsCaught ? `was ${met(base)}` : null),
        stat("Callers reached today", reached(sim),
          sim.unreached ? `${sim.unreached} wait for tomorrow` : sim.reachedBy ? `everyone, by ${clock(sim.reachedBy)}` : null,
          base && sim.unreached < base.unreached ? `was ${reached(base)}` : null),
        stat("Agent time", `${sim.agentHours.toFixed(1)} h`, s.mode ? null : "for one day's voicemail",
          base && sim.agentHours < base.agentHours - 0.05 ? `${(base.agentHours - sim.agentHours).toFixed(1)} h back for other work` : null),
      );
    }
    if (s.mode === 0 && s.assumptions) {
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
    if (s.mode >= 1 && s._acc) {
      const a = s._acc;
      const pct = (x) => `${Math.round(x * 100)}%`;
      stats.push(
        el("div", { class: "stat acc", title: "Where the AI disagrees with the day's ground truth, after your corrections" },
          el("span", { class: "label" }, "AI accuracy"),
          el("b", {}, `${pct(a.intent_urgency)} intent · ${pct(a.routing)} routing · ${pct(a.extraction)} facts`),
          el("span", { class: "note" }, `over ${a.messages} messages, ${a.corrections} correction${a.corrections === 1 ? "" : "s"} by humans`)),
      );
    }
    if (s.mode === 2 && s._sb2) {
      const sb = s._sb2;
      const before = stats.length;
      stats.push(
        stat("No callback needed", `${s.queue.filter((m) => m.resolvable).length} messages`,
          `the AI found the answer in the case record (${sb.callbacksAvoided.resolvable} could be); `
            + `${sb.callbacksAvoided.approved} approved by a person so far`),
        sb.incident
          ? stat("Outage spotted", `${hm(sb.incident.leadMin)} after the first call`,
            `“${sb.incident.title}”: one holding reply covers every caller`)
          : stat("Outage spotted", "—", "no spike today"),
      );
      stats.slice(before).forEach((n) => n.classList.add("m2"));  // what Mode 2 adds, highlighted as such
    }
    put(root, ...stats);
  }, ["sim", "pace", "queue", "assumptions", "mode", "_acc", "_sb2"]);
}