// The inbox. Mode 0: arrival order — time, caller ID, length, nothing else until a message is played.
// Mode 1: the AI's urgency order, with the urgency score and the routed team on every row;
// changing mode re-sorts the rows with a short slide, the urgent one jumping to the top.
// Mode 2: same order, plus the day's cross-message reasoning: the cluster size, the incident
// flag, the resolvable/obligation/window badges — and repeat callers collapsed to their first message.
import { clock, dayOf, el, mmss, phone, put } from "../core/format.js";

function incidentBanner(incidents) {
  const inc = incidents?.[0];
  if (!inc) return null;
  const card = inc.card || {};
  return el("div", { class: "incident-banner", role: "alert" },
    el("div", {}, el("b", {}, `Incident · ${inc.count} similar callers since ${clock(inc.firstAt)}`),
      el("span", { class: "muted" }, ` · alerted ${clock(inc.alertAt)}`)),
    el("p", { class: "banner-line" }, card.banner || ""),
    el("p", { class: "banner-cause" }, el("span", { class: "muted" }, "Probable cause: "), card.probableCause || ""),
    card.actions?.length ? el("ol", { class: "banner-actions" }, card.actions.map((a) => el("li", {}, a))) : null,
  );
}

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
      const badges = mode >= 1 ? [
        el("span", { class: `urg u${m.urgency}`, title: `AI urgency ${m.urgency} of 5` }, m.urgency),
        el("span", { class: "team", title: `The AI routes this to ${m.team}` }, m.team),
        mode === 2 && m.clusterSize > 1 ? el("span", { class: "badge cluster", title: `${m.clusterSize} similar messages today (a spike)` }, m.clusterSize + "×") : null,
        mode === 2 && m.incident ? el("span", { class: "badge incident", title: `In the spike: ${m.incident}` }, "incident") : null,
        mode === 2 && m.resolvable ? el("span", { class: "badge resolvable", title: "The AI thinks the case record alone answers it — no callback needed" }, "resolvable") : null,
        mode === 2 && m.obligation ? el("span", { class: "badge obligation", title: `Deadline-bound: a ${m.obligation} is promised in the message` }, m.obligation) : null,
        mode === 2 && m.window ? el("span", { class: "badge window", title: `The caller asked to be reached ${m.window}` }, m.window) : null,
      ].filter(Boolean) : [];
      list.append(el("li", {
        class: ["queue-row", m.id === s.selected && "selected", m.worked && "worked", touch && "touched",
                 touch?.late && "late", mode === 2 && m.repeat && "repeat-leader"].filter(Boolean).join(" "),
        "data-id": m.id, tabindex: 0,
        onclick: () => store.set({ selected: m.id }),
        onkeydown: (e) => e.key === "Enter" && store.set({ selected: m.id }),
      },
        el("span", { class: "q-time" }, clock(m.receivedAt)),
        el("span", { class: "q-caller" }, phone(m.callerId),
          mode === 2 && m.repeat ? el("span", { class: "repeat-note", title: `Members: ${m.repeat.members.join(", ")}` },
            ` · ${m.repeat.members.length}× · ${m.repeat.note}`) : null),
        el("span", { class: "q-dur" }, mmss(m.durationSec)),
        ...badges,
        el("span", { class: "q-touch", title: "When the simulated agent first reached it" },
          touch ? (touch.at ? clock(touch.at) : "not reached") : (m.worked ? "✓" : "")),
      ));
    }
    put(root,
      el("div", { class: "pane-head" },
        el("h2", {}, mode === 2 ? `Queue · mode 2 · ${s.queue.length}` : mode === 1 ? `Queue · AI urgency · ${s.queue.length}` : `Queue · ${s.queue.length}`),
        el("button", { class: "small", onclick: () => store.emit("simulate") }, "Work the queue ▸")),
      mode === 2 ? el("div", { class: "queue-legend muted" },
        "cluster  = similar messages today · resolvable = the case record may answer it · the rest of the day's links are on each message") : null,
      mode === 2 ? incidentBanner(s.incidents) : null,
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
  store.subscribe(draw, ["queue", "selected", "touches", "simClock", "mode", "incidents"]);
}