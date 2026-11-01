// The inbox. Mode 0: arrival order — time, caller ID, length, nothing else until a message is played.
// Mode 1: the AI's urgency order, with the urgency score and the routed team on every row;
// changing mode re-sorts the rows with a short slide, the urgent one jumping to the top.
// Mode 2: same order, plus the day's cross-message reasoning: the cluster size, the incident
// flag, the resolvable/obligation/window badges — and repeat callers collapsed to their first message.
import { clock, dayOf, el, mmss, phone, put } from "../core/format.js";
import { DEADLINES, TEAMS, URGENCY, plain, word } from "../core/words.js";

function incidentBanner(incidents) {
  const inc = incidents?.[0];
  if (!inc) return null;
  const card = inc.card || {};
  return el("div", { class: "incident-banner", role: "alert" },
    el("div", { "data-tip": "Several callers describing the same problem at once: the AI flags it as one outage, not separate messages" },
      el("b", {}, `Likely outage · ${inc.count} callers with the same problem since ${clock(inc.firstAt)}`),
      el("span", { class: "muted" }, ` · flagged at ${clock(inc.alertAt)}`)),
    el("p", { class: "banner-line" }, card.banner || ""),
    el("p", { class: "banner-cause" }, el("span", { class: "muted" }, "Likely cause: "), card.probableCause || ""),
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
      const urg = mode >= 1 ? el("span", { class: `urg u${m.urgency}`, "data-tip": `How urgent, in the AI's view: ${URGENCY[m.urgency] ?? m.urgency} (of 5)` }, m.urgency) : null;
      const badges = mode >= 1 ? [
        mode === 2 && m.repeat ? el("span", { class: "repeat-note", "data-tip": `The same caller left ${m.repeat.members.length} messages; they're handled together, once` },
          `${m.repeat.members.length} messages · ${m.repeat.note}`) : null,
        el("span", { class: "team", "data-tip": `The AI would send this to ${word(TEAMS, m.team)}` }, word(TEAMS, m.team)),
        mode === 2 && m.clusterSize > 1 ? el("span", { class: "badge cluster", "data-tip": `${m.clusterSize} messages today are about the same thing` }, `${m.clusterSize} alike`) : null,
        mode === 2 && m.incident ? el("span", { class: "badge incident", "data-tip": `Part of a likely outage: ${m.incident}. One holding reply covers every caller.` }, "outage") : null,
        mode === 2 && m.resolvable ? el("span", { class: "badge resolvable", "data-tip": "The case record answers this: a person approves the AI's reply, no callback needed" }, "answer ready") : null,
        mode === 2 && m.obligation ? el("span", { class: "badge obligation", "data-tip": DEADLINES[m.obligation] ? `Has a deadline: ${DEADLINES[m.obligation][1]}` : `Has a deadline: ${plain(m.obligation)}` }, "deadline") : null,
        mode === 2 && m.window ? el("span", { class: "badge window", "data-tip": `Best time to call them back: ${m.window}` }, m.window) : null,
      ].filter(Boolean) : [];
      list.append(el("li", {
        class: ["queue-row", m.id === s.selected && "selected", m.worked && "worked", touch && "touched",
                 touch?.late && "late", mode === 2 && m.repeat && "repeat-leader"].filter(Boolean).join(" "),
        "data-id": m.id, tabindex: 0,
        onclick: () => store.set({ selected: m.id }),
        onkeydown: (e) => e.key === "Enter" && store.set({ selected: m.id }),
      },
        el("span", { class: "q-time" }, clock(m.receivedAt)),
        el("span", { class: "q-caller" }, phone(m.callerId)),
        el("span", { class: "q-dur" }, mmss(m.durationSec)),
        urg,
        el("span", { class: "q-touch", "data-tip": touch ? "When the agent got to it in the played-out day" : "" },
          touch ? (touch.at ? clock(touch.at) : "not reached") : (m.worked ? "✓" : "")),
        badges.length ? el("span", { class: "q-tags" }, badges) : null,  // a second line: the team, then the tags
      ));
    }
    put(root,
      el("div", { class: "pane-head" },
        el("h2", { "data-tip": mode ? "Most urgent first, as the AI judges it" : "In the order the messages arrived, oldest first" },
          `Voicemail · ${s.queue.length} · ${mode === 2 ? "most urgent first, repeat callers combined" : mode === 1 ? "most urgent first" : "oldest first"}`),
        el("button", { class: "small", onclick: () => store.emit("simulate"),
          "data-tip": "Play out the day: one agent works through these, and the board shows who gets reached when" }, "Work the queue ▸")),
      mode === 2 ? el("div", { class: "queue-legend muted" }, "Hover a tag to see what it means.") : null,
      mode === 2 ? incidentBanner(s.incidents) : null,
      s.simClock ? el("div", { class: "sim-clock" }, `Playing the day: ${clock(s.simClock)}`) : null,
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