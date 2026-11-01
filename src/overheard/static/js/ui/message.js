// The message pane. Mode 0: "listen" (the transcript appears at speaking pace), then the manual form.
// Mode 1: the transcript with the AI's low-confidence words marked, the seven AI panels with
// provenance badges and a "why" button, and every field editable — an edit is a correction, logged.
import { api } from "../core/api.js";
import { clock, el, hm, mmss, phone, put } from "../core/format.js";
import { DEADLINES, FIELDS, INTENTS, MOODS, NEXT_STEP, TEAMS, URGENCY, plain, word } from "../core/words.js";

const WPM = 150;
const CATEGORIES = ["", "Payment status", "Document status", "Portal / sign-in", "Address or contact change",
  "Direct deposit", "Form question", "Overpayment", "Complaint", "Records request", "Congressional",
  "Legal", "Welfare concern", "Urgent hardship", "Other"];
const DISPOSITIONS = ["", "Call back", "Written reply", "Escalate", "Refer to another team", "No action needed"];

const PANELS = [
  ["summary", "Summary", "What the caller said, in a sentence or two"],
  ["intent_urgency", "What they want", "Why they called and how soon someone should act"],
  ["routing", "Who should handle it", "The team the AI would send this to"],
  ["extraction", "Details", "Names, numbers and requests pulled out of the message, so no one types them in"],
  ["sentiment", "How they sound", "The caller's mood, and whether to follow up personally"],
  ["translation", "In English", "Messages in other languages, translated"],
  ["draft_reply", "Suggested reply", "A reply the AI drafted; a person checks it before anything is sent"],
];

const PROV = {
  mock: ["AI · demo", "Demo mode: made offline from the day's script, with a realistic share of mistakes"],
  llm: ["AI", "Written by the AI model, live"],
  fallback: ["fallback", "The AI's answer didn't check out, so this is a safe stand-in"],
  human: ["edited", "A person changed what the AI said"],
};

function reasonFor(task, data) {
  switch (task) {
    case "intent_urgency": return data.rationale || "";
    case "routing": return data.reason || "";
    case "sentiment":
      return data.escalation === "follow-up"
        ? `Tone or stakes say "follow-up": ${data.sentiment}, not just log-and-queue.`
        : `Tone reads as ${data.sentiment}; standard queue is fine.`;
    case "summary": return "Read the whole transcript — the summary is a direct restatement of it.";
    case "translation":
      return data.translated
        ? `Translated from ${data.sourceLang} to English; numbers, names and dates kept intact.`
        : "The transcript is already English, so nothing was translated.";
    case "draft_reply": return `Tone: ${data.tone}. A human approves before anything goes out.`;
    default: return "Look at the highlighted spans in the transcript.";
  }
}

function badge(part) {
  const [text, tip] = PROV[part.provenance] ?? [part.provenance, ""];
  return el("span", { class: `prov prov-${part.provenance}`, "data-tip": tip }, text);
}

function why(task, data) {
  const b = el("button", { class: "small why", type: "button", "aria-expanded": "false",
    "data-tip": "What in the message led the AI here" }, "Why?");
  b.addEventListener("click", () => {
    const old = b.nextElementSibling;
    if (old && old.classList.contains("why-pop")) { old.remove(); b.setAttribute("aria-expanded", "false"); return; }
    b.setAttribute("aria-expanded", "true");
    b.after(el("div", { class: "why-pop" }, reasonFor(task, data)));
  });
  return b;
}

export function renderMessage(root, store) {
  let timer = null, opened = 0, current = null, analysis = null;
  const stop = () => { clearInterval(timer); timer = null; };

  // Spans in the analysis are [start, end) CHARACTER offsets into the script;
  // the transcript is word spans, so map via the per-word start offsets in t._offsets.
  function markSpans() {
    const t = root.querySelector(".transcript");
    if (!t) return;
    const correction = store.get().correction;
    t.querySelectorAll(".word-watch, .word-edited").forEach((w) => w.classList.remove("word-watch", "word-edited"));
    const extract = analysis?.extraction?.data;
    const offsets = t._offsets || [];
    for (const f of ["caller", "callbackNumber", "caseId", "program", "requestedAction"]) {
      const env = extract?.[f];
      const s = env?.span, v = env?.value;
      if (!s?.length || !v) continue;
      offsets.forEach((off, i) => {
        if (off < s[0] || off >= s[1]) return;
        const w = t.querySelector(`[data-w="${i}"]`);
        w?.classList.add("word-watch");
        if (correction?.task === "extraction" && correction.field === f &&
            String(correction.value).toLowerCase() !== v.toLowerCase())
          w?.classList.add("word-edited");
      });
    }
  }

  // one AI field: label + editable input + provenance badge; an edit becomes a logged correction
  // `choices` ({code: plain words}) makes it a dropdown: people pick the words, the code is what's scored
  function aiField(id, label, value, part, choices) {
    const corr = store.get().correction;
    const corrected = corr?.task === id?.task && corr?.field === id?.field;
    const said = choices ? word(choices, value) : value;
    const tip = corrected ? `A person corrected this (the AI said “${said ?? ""}”)`
      : `The AI's answer: ${said ?? "nothing"}. Change it if it's wrong; the scoreboard counts corrections.`;
    let input;
    if (choices) {
      const codes = Object.keys(choices);
      if (value != null && !codes.includes(String(value))) codes.push(String(value));
      input = el("select", { class: "ai-value", "data-task": id.task, "data-field": id.field, "data-tip": tip },
        codes.map((c) => el("option", { value: c }, word(choices, c))));
      input.value = value == null ? "" : String(value);
    } else {
      input = el("input", {
        class: "ai-value", type: "text", "data-task": id.task, "data-field": id.field,
        value: value ?? "", placeholder: "—", "data-tip": tip,
      });
    }
    input.addEventListener("change", async () => {
      try {
        await api.postCorrection({
          voicemail: store.get().selected, task: id.task, field: id.field,
          value: input.value.trim() ? input.value.trim() : null,
        });
      } catch { /* keep editing; the correction endpoint 404s only for unknown messages */ }
      const c = await api.corrections(store.get().selected).catch(() => []);
      const hit = c.find((x) => x.task === id.task && x.field === id.field) || null;
      store.set({ correction: { id: Date.now(), task: id.task, field: id.field, value: input.value.trim() || null, ts: hit?.at ?? Date.now() } });
      markSpans();
    });
    return el("label", { class: "ai-field" },
      el("span", { class: "ai-label" }, label),
      input,
      corrected ? el("span", { class: "prov prov-human", "data-tip": "A person changed what the AI said" }, "edited") : badge(part));
  }

  function panel(task, title, part, tip) {
    const data = part?.data;
    if (!data) return null;
    const body = [];
    if (task === "summary") {
      body.push(el("div", { class: "ai-line" }, data.summary));
      body.push(aiField({ task, field: "short" }, "In one line", data.short, part));
    } else if (task === "intent_urgency") {
      body.push(el("div", { class: "ai-line" }, data.rationale));
      body.push(aiField({ task, field: "intent" }, "Calling about", data.intent, part, INTENTS));
      body.push(aiField({ task, field: "urgency" }, "How urgent", data.urgency, part, URGENCY));
      if (data.obligations?.length) {
        body.push(el("div", { class: "ai-line muted" }, "Has a deadline: ",
          data.obligations.map((o, i) => el("span", { "data-tip": DEADLINES[o] ? `${DEADLINES[o][0]}: ${DEADLINES[o][1]}` : plain(o) },
            (i ? ", " : "") + (DEADLINES[o]?.[0] ?? plain(o))))));
      }
    } else if (task === "routing") {
      body.push(el("div", { class: "ai-line" }, data.reason));
      body.push(aiField({ task, field: "team" }, "Send to", data.team, part, TEAMS));
    } else if (task === "extraction") {
      for (const f of ["caller", "callbackNumber", "caseId", "program", "requestedAction"]) {
        body.push(aiField({ task, field: f }, FIELDS[f] ?? plain(f), data[f]?.value, part));
      }
    } else if (task === "sentiment") {
      body.push(aiField({ task, field: "sentiment" }, "They sound", data.sentiment, part, MOODS));
      body.push(aiField({ task, field: "escalation" }, "Next step", data.escalation, part, NEXT_STEP));
    } else if (task === "translation") {
      if (!data.translated) body.push(el("div", { class: "ai-line muted" }, "Already English — nothing to translate."));
      else {
        body.push(el("div", { class: "ai-line" }, `From ${data.sourceLang}:`));
        body.push(el("div", { class: "ai-text" }, data.text));
      }
    } else if (task === "draft_reply") {
      body.push(el("div", { class: "ai-line muted" }, `Tone: ${data.tone} · a person approves it before it goes out`));
      body.push(el("div", { class: "ai-text" }, data.text));
    }
    return el("section", { class: "ai-panel", "data-panel": task },
      el("header", { class: "ai-panel-head" }, el("b", { "data-tip": tip }, title), badge(part), why(task, data)),
      body);
  }

  function transcript(text, current) {
    const words = text.split(/\s+/);
    const offsets = [];
    { let pos = 0; for (const w of words) { offsets.push(pos); pos += w.length + 1; } }
    const totalSec = Math.max(current.durationSec, (words.length / WPM) * 60);
    let shown = 0, speed = 1;
    const t = Object.assign(el("p", { class: "transcript", "aria-live": "polite" }), { _offsets: offsets });
    words.forEach((w, i) => t.append(el("span", { class: "word", "data-w": i, "data-v": w }, w), " "));
    const bar = el("div", { class: "progress", title: "Click to jump" }, el("div", { class: "fill" }));
    const time = el("span", { class: "muted" }, `0:00 / ${mmss(totalSec)}`);
    const draw = () => {
      const upTo = Math.floor(shown);
      t.replaceChildren(...words.flatMap((w, i) => [
        el("span", { class: i < upTo ? "word" : "word dim", "data-w": i, "data-v": w }, w), " "]));
      const frac = shown / words.length;
      bar.firstChild.style.width = `${Math.min(100, frac * 100)}%`;
      time.textContent = `${mmss(frac * totalSec)} / ${mmss(totalSec)}`;
      markSpans();
    };
    const playBtn = el("button", {});
    const play = () => {
      if (timer) { stop(); playBtn.textContent = "▶ Play"; return; }
      if (shown >= words.length) shown = 0;
      playBtn.textContent = "❚❚ Pause";
      const step = words.length / totalSec / 10;
      timer = setInterval(() => {
        shown = Math.min(words.length, shown + step * speed);
        draw();
        if (shown >= words.length) { stop(); playBtn.textContent = "▶ Play again"; }
      }, 100);
    };
    playBtn.textContent = "▶ Play";
    bar.addEventListener("click", (e) => {
      const r = bar.getBoundingClientRect();
      shown = ((e.clientX - r.left) / r.width) * words.length;
      draw();
    });
    const speedBtn = el("button", { class: "small", onclick: () => {
      speed = speed === 1 ? 2 : 1; speedBtn.textContent = `${speed}×`;
    } }, "1×");
    draw();
    return el("div", {}, el("div", { class: "player" }, playBtn, speedBtn, bar, time), t);
  }

  async function open(id) {
    stop();
    const mode = store.get().mode;
    if (!id) { put(root, el("p", { class: "muted" }, "Pick a message.")); return; }
    put(root, el("div", { class: "pane-head" }, el("h2", {}, "Message"),
      el("span", { class: "muted" }, `opening ${id}…`)));
    current = await api.message(id, mode);
    analysis = mode ? current.analysis : null;
    // a human's last correction (if any) survives re-opening the message
    if (mode) {
      const saved2 = (await api.corrections(id).catch(() => []));
      const last = saved2[saved2.length - 1];
      store.set({ correction: last ? { task: last.task, field: last.field, value: last.value } : null });
    } else store.set({ correction: null });
    const saved = (await api.entries())[id] || {};
    let a = store.get().assumptions;
    if (!a) { a = await api.assumptions(); store.set({ assumptions: a }); }
    const listenMin = current.durationSec / 60;
    const workloadMin = listenMin + a.handleMin + a.callbackMin;
    opened = performance.now();
    // the player always plays the ORIGINAL script (spans point into it); the translation panel carries the English
    const shown = current.script;

    const field = (name, label, input) => el("label", {}, el("span", {}, label), input);
    const input = (name) => el("input", { name, value: saved[name] ?? "" });
    const select = (name, options) => {
      const s = el("select", { name }, options.map((o) => el("option", { value: o }, o || "—")));
      s.value = saved[name] ?? "";
      return s;
    };
    const effort = el("span", { class: "effort muted" });
    const form = el("form", { class: "entry", onsubmit: async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      data.priority = data.priority ? Number(data.priority) : null;
      data.secondsSpent = (performance.now() - opened) / 1000;
      await api.saveEntry(id, data);
      store.emit("saved", { id, seconds: data.secondsSpent });
    } },
      field("callerName", "Caller name", input("callerName")),
      field("callbackNumber", "Callback number", input("callbackNumber")),
      field("caseNumber", "Case number", input("caseNumber")),
      field("category", "Category", select("category", CATEGORIES)),
      field("priority", "Priority (1 low – 5 urgent)", select("priority", ["", "1", "2", "3", "4", "5"])),
      field("disposition", "Disposition", select("disposition", DISPOSITIONS)),
      el("label", { class: "wide" }, el("span", {}, "Notes"), el("textarea", { name: "notes", rows: 3 }, saved.notes ?? "")),
      el("div", { class: "form-actions" }, el("button", { type: "submit" }, "Save"), effort),
    );
    const tick = () => { effort.textContent = `open ${mmss((performance.now() - opened) / 1000)}`; };
    tick();
    clearInterval(root._effort);
    root._effort = setInterval(tick, 1000);

    const panels = mode ? el("div", { class: "ai-panels" },
      PANELS.map(([t, title, tip]) => panel(t, title, analysis?.[t], tip)).filter(Boolean)) : null;
    put(root,
      el("div", { class: "pane-head" }, el("h2", {}, mode === 2 ? "Message · Mode 2" : mode ? "Message · Mode 1" : "Message"),
        el("span", { class: "muted" }, `${clock(current.receivedAt)} · ${phone(current.callerId)} · ${mmss(current.durationSec)}`)),
      mode ? null : el("p", { class: "workload muted" },
        `Costs the agent ${hm(workloadMin)}: ${hm(listenMin)} listening, ${hm(a.handleMin)} handling, ${hm(a.callbackMin)} on a callback.`),
      transcript(shown, current),
      panels,
      mode ? el("p", { class: "muted ai-hint" },
        "Every AI field is editable — an edit is a correction, and the scoreboard scores it out. Highlighted words are what the AI is watching for.") : null,
      el("h3", {}, "Your entry"),
      form,
    );
    markSpans();
  }
  store.subscribe((s) => open(s.selected), ["selected", "mode"]);
}