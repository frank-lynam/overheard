// The inbox. Mode 0: arrival order — time, caller ID, length, nothing else until a message is played.
// Mode 1: the AI's urgency order, with the urgency score and the routed team on every row;
// changing mode re-sorts the rows with a short slide, the urgent one jumping to the top.
import { clock, dayOf, el, mmss, phone, put } from "../core/format.js";

export function renderQueue(root, store) {
  const draw = (s) => {
    const mode = s.mode;
    // remember where the rows are now, so after the re-sort we can slide them (FLIP)
    const oldTop = {};
    for (const li of root.querySelectorAll(".queue-row")) oldTop[li.dataset.id] = li.getBoundingClientRect().top;
    const list = el("ol", { class: "queue-list" });
    let lastDay = null;
    for (const m of s.queue) {
      if (mode === 0 && dayOf(m.receivedAt) !== lastDay) {
        lastDay = dayOf(m.receivedAt);
        list.append(el("li", { class: "day-break" }, lastDay === s.today ? "Today" : "Yesterday, after hours"));
      }
      const touch = s.touches?.[m.id];
      list.append(el("li", {
        class: ["queue-row", m.id === s.selected && "selected", m.worked && "worked", touch && "touched",
                 touch?.late && "late"].filter(Boolean).join(" "),
        "data-id": m.id, tabindex: 0,
        onclick: () => store.set({ selected: m.id }),
        onkeydown: (e) => e.key === "Enter" && store.set({ selected: m.id }),
      },
        el("span", { class: "q-time" }, clock(m.receivedAt)),
        el("span", { class: "q-caller" }, phone(m.callerId)),
        el("span", { class: "q-dur" }, mmss(m.durationSec)),
        mode === 1 ? el("span", { class: `urg u${m.urgency}`, title: `AI urgency ${m.urgency} of 5` }, m.urgency) : null,
        mode === 1 ? el("span", { class: "team", title: `The AI routes this to ${m.team}` }, m.team) : null,
        el("span", { class: "q-touch", title: "When the simulated agent first reached it" },
          touch ? (touch.at ? clock(touch.at) : "not reached") : (m.worked ? "✓" : "")),
      ));
    }
    put(root,
      el("div", { class: "pane-head" },
        el("h2", {}, mode === 1 ? `Queue · AI urgency · ${s.queue.length}` : `Queue · ${s.queue.length}`),
        el("button", { class: "small", onclick: () => store.emit("simulate") }, "Work the queue ▸")),
      s.simClock ? el("div", { class: "sim-clock" }, `Simulated agent: ${clock(s.simClock)}`) : null,
      list,
    );
    // slide the rows that moved, fade in the ones that are new to this order
    for (const li of list.querySelectorAll(".queue-row")) {
      const old = oldTop[li.dataset.id];
      if (old == null) { li.classList.add("queue-new"); continue; }
      const d = old - li.getBoundingClientRect().top;
      if (Math.abs(d) < 2) continue;
      li.style.transform = `translateY(${d}px)`;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        li.style.transition = "transform 500ms cubic-bezier(0.2, 0.8, 0.2, 1)";
        li.style.transform = "";
      }));
    }
  };
  store.subscribe(draw, ["queue", "selected", "touches", "simClock", "mode"]);
}