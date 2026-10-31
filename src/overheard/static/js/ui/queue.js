// Mode 0's inbox: arrival order; only time, caller ID and length until a message is played.
import { clock, dayOf, el, mmss, phone, put } from "../core/format.js";

export function renderQueue(root, store) {
  const draw = (s) => {
    const list = el("ol", { class: "queue-list" });
    let lastDay = null;
    for (const m of s.queue) {
      if (dayOf(m.receivedAt) !== lastDay) {
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
        el("span", { class: "q-touch", title: "When the simulated agent first reached it" },
          touch ? (touch.at ? clock(touch.at) : "not reached") : (m.worked ? "✓" : "")),
      ));
    }
    put(root, 
      el("div", { class: "pane-head" },
        el("h2", {}, `Queue · ${s.queue.length}`),
        el("button", { class: "small", onclick: () => store.emit("simulate") }, "Work the queue ▸")),
      s.simClock ? el("div", { class: "sim-clock" }, `Simulated agent: ${clock(s.simClock)}`) : null,
      list,
    );
  };
  store.subscribe(draw, ["queue", "selected", "touches", "simClock"]);
}
