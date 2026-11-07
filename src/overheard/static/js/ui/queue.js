// The inbox. Mode 0: arrival order — time, caller ID, length, nothing else until a message is played.
// Mode 1: the AI's urgency order, with the urgency score and the routed team on every row;
// changing mode re-sorts the rows with a short slide, the urgent one jumping to the top.
// Mode 2: same order, plus the day's cross-message reasoning: the cluster size, the incident
// flag, the resolvable/obligation/window badges — and repeat callers collapsed to their first message.
import { api } from "../core/api.js";
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

// Mode 2: the tickets filed in the workflow system, revealed voicemail by voicemail, each with its proposed team
const TEAM_NAMES = (t) => t?.teams || {};
function ticketCard(store, t, teams) {
  const name = (slug) => teams[slug] || (slug === "general" ? "General" : slug);
  const team = t.proposed_team === "unknown" ? "unknown (filed in General)" : name(t.proposed_team);
  const status = { proposed: "waiting for the team", accepted: `accepted by ${name(t.final_team)}`,
    moved: `moved to ${name(t.final_team)}`, declined: "declined" }[t.status] || t.status;
  const why = t.evidence.map((e) => `${e.ref} (${e.when}): “${e.text}” went to ${name(e.team)}`).join("\n");
  const act = async (action, teamSlug) => {
    try {
      await api.decideTicket(t.ticket_id, action, teamSlug);
      store.set({ _tickets: await api.tickets() });
    } catch (e) { alert(e.message); }
  };
  const move = el("select", { "aria-label": "Move to", onchange: (e) => e.target.value && act("move", e.target.value) },
    el("option", { value: "" }, "Move to…"),
    Object.entries(teams).filter(([k]) => k !== t.filed_in).map(([k, v]) => el("option", { value: k }, v)));
  return el("li", { class: `ticket-card t-${t.status}` },
    el("div", { class: "ticket-head" }, el("b", {}, t.summary),
      t.priority === 1 ? el("span", { class: "badge alert", "data-tip": "Code words: priority 1" }, "priority") : null),
    el("div", { class: "ticket-meta" },
      el("span", { class: "chip-team", "data-tip": why || "No similar past problems" },
        `Proposed: ${team} · ${Math.round(t.team_confidence * 100)}%`),
      el("span", { class: "muted" }, ` · ${status}`)),
    t.status === "proposed" && t.sink === "mock"
      ? el("div", { class: "ticket-acts" }, el("button", { class: "small", onclick: () => act("accept") }, "Accept"), move,
          el("button", { class: "small", onclick: () => act("decline") }, "Decline"))
      : t.link ? el("a", { href: t.link, target: "_blank", rel: "noopener" }, "Open on the board ›") : null);
}

export function renderQueue(root, store) {
  let polling = null;
  const drawTickets = (s) => {
    const t = s._tickets, teams = TEAM_NAMES(t);
    const reveal = async (all) => {
      await api.revealTickets(all);
      store.set({ _tickets: await api.tickets() });
    };
    clearInterval(polling);   // decisions made on the board come back by polling
    if (t.sink !== "mock") polling = setInterval(async () => {
      if (!store.get().showTickets) { clearInterval(polling); return; }
      store.set({ _tickets: await api.tickets() });
    }, 5000);
    put(root,
      el("div", { class: "pane-head" }, el("h2", {}, `Tickets · ${t.tickets.length}`),
        el("button", { class: "small", onclick: () => store.set({ showTickets: false }) }, "Back to the queue")),
      el("p", { class: "queue-legend muted" }, t.sink === "mock"
        ? "Each problem becomes a ticket for the team routing memory proposes. Accept, move or decline it: a move teaches the next proposal."
        : "Filed on the board as proposals in the proposed team's project; the team accepts, moves or declines it there."),
      el("div", { class: "row ticket-reveal" },
        el("button", { class: "small", disabled: !t.counts.toReveal, onclick: () => reveal(false),
          "data-tip": "Reveal voicemails in arrival order until the next one makes a ticket" }, "Next voicemail ›"),
        el("button", { class: "small", disabled: !t.counts.toReveal, onclick: () => reveal(true) }, "Reveal the rest"),
        el("span", { class: "muted" }, `${t.counts.toReveal} to go · ${t.counts.notProblems} weren't problems`)),
      el("ol", { class: "queue-list ticket-list" }, [...t.tickets].reverse().map((x) => ticketCard(store, x, teams))));
  };
  const draw = (s) => {
    const mode = s.mode;
    // remember where the rows are now, so after the re-sort we can slide them (FLIP)
    const oldTop = {};
    for (const li of root.querySelectorAll(".queue-row")) oldTop[li.dataset.id] = li.getBoundingClientRect().top;
    const list = el("ol", { class: "queue-list" });
    let lastDay = null;
    const alerts = mode >= 1 ? s.queue.filter((m) => m.alert) : [];
    if (alerts.length) list.append(el("li", { class: "day-break lane-alert",
      "data-tip": "Voicemails with a code word (an attorney, a senator, someone at risk) go in front of a person at once" },
      `Alerts · ${alerts.length}`));
    let laneDone = !alerts.length;
    for (const m of s.queue) {
      if (!laneDone && !m.alert) {
        laneDone = true;
        list.append(el("li", { class: "day-break" }, "Everything else"));
      }
      if (mode === 0 && dayOf(m.receivedAt) !== lastDay) {
        lastDay = dayOf(m.receivedAt);
        list.append(el("li", { class: "day-break" }, lastDay === s.today ? "Today" : "Yesterday, after hours"));
      }
      const touch = s.touches?.[m.id];
      const urg = mode >= 1 ? el("span", { class: `urg u${m.urgency}`, "data-tip": `How urgent, in the AI's view: ${URGENCY[m.urgency] ?? m.urgency} (of 5)` }, m.urgency) : null;
      const badges = mode >= 1 ? [
        mode === 2 && m.repeat ? el("span", { class: "repeat-note", "data-tip": `The same caller left ${m.repeat.members.length} messages; they're handled together, once` },
          `${m.repeat.members.length} messages · ${m.repeat.note}`) : null,
        m.alert ? el("span", { class: `badge alert${m.alert.safety ? " safety" : ""}`,
          "data-tip": `A code word was heard (${m.alert.label.toLowerCase()}): it goes to a person at once` }, m.alert.label) : null,
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
    if (mode >= 1 && s.showJunk && s._junk) {        // the junk list: what was kept out, why, and a way back
      const rows = s._junk.filtered.map((j) => el("li", { class: "junk-row" },
        el("span", { class: "q-time" }, clock(j.receivedAt)),
        el("span", { class: "junk-what" }, el("span", { class: "junk-script" }, j.script),
          el("span", { class: "muted junk-why", "data-tip": `Decided by ${j.decidedBy.startsWith("rule:")
            ? "a rule (" + j.decidedBy.slice(5) + ")" : "the AI"}` }, j.reason)),
        el("button", { class: "small", onclick: async () => {
          await api.reopenJunk(j.id);
          store.set({ _junk: await api.junk(), queue: await api.queue(store.get().mode) });
        }, "data-tip": "Put it back in the queue for a person" }, "Reopen")));
      put(root,
        el("div", { class: "pane-head" }, el("h2", {}, `Kept out as junk · ${s._junk.filtered.length}`),
          el("button", { class: "small", onclick: () => store.set({ showJunk: false }) }, "Back to the queue")),
        el("p", { class: "queue-legend muted" }, "Nobody listened to these. Reopen anything that looks real."),
        el("ol", { class: "queue-list junk-list" }, rows));
      return;
    }
    if (mode >= 2 && s.showTickets && s._tickets) { drawTickets(s); return; }
    const kept = mode >= 1 && s._junk ? s._junk.filtered.length : 0;
    const filed = mode >= 2 && s._tickets ? s._tickets.tickets.length : null;
    put(root,
      kept ? el("button", { class: "junk-link", onclick: () => store.set({ showJunk: true }),
        "data-tip": "Robocalls, scams, silence and pocket dials the filter kept out: see them, reopen any" },
        `${kept} junk calls kept out ›`) : null,
      filed !== null ? el("button", { class: "junk-link tickets-link", onclick: () => store.set({ showTickets: true }),
        "data-tip": "Problems become tickets for the team routing memory proposes; people accept, move or decline them" },
        `${filed} ticket${filed === 1 ? "" : "s"} filed · ${s._tickets.counts.toReveal} voicemails to go ›`) : null,
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
  store.subscribe(draw, ["queue", "selected", "touches", "simClock", "mode", "incidents", "showJunk", "_junk",
                         "showTickets", "_tickets"]);
}