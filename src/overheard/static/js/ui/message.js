// Mode 0's message: "listen" (the transcript appears at speaking pace), then the manual form.
import { api } from "../core/api.js";
import { clock, el, hm, mmss, phone, put } from "../core/format.js";

const WPM = 150;
const CATEGORIES = ["", "Payment status", "Document status", "Portal / sign-in", "Address or contact change",
  "Direct deposit", "Form question", "Overpayment", "Complaint", "Records request", "Congressional",
  "Legal", "Welfare concern", "Urgent hardship", "Other"];
const DISPOSITIONS = ["", "Call back", "Written reply", "Escalate", "Refer to another team", "No action needed"];

export function renderMessage(root, store) {
  let timer = null, opened = 0, current = null;
  const stop = () => { clearInterval(timer); timer = null; };

  async function open(id) {
    stop();
    if (!id) { put(root, el("p", { class: "muted" }, "Pick a message.")); return; }
    current = await api.message(id);
    const saved = (await api.entries())[id] || {};
    let a = store.get().assumptions;
    if (!a) { a = await api.assumptions(); store.set({ assumptions: a }); }
    const listenMin = current.durationSec / 60;
    const workloadMin = listenMin + a.handleMin + a.callbackMin;
    opened = performance.now();
    const words = current.script.split(/\s+/);
    const totalSec = Math.max(current.durationSec, (words.length / WPM) * 60);
    let shown = 0, speed = 1;
    const text = el("p", { class: "transcript", "aria-live": "polite" });
    const bar = el("div", { class: "progress", title: "Click to jump" }, el("div", { class: "fill" }));
    const time = el("span", { class: "muted" }, `0:00 / ${mmss(totalSec)}`);
    const draw = () => {
      text.textContent = words.slice(0, Math.floor(shown)).join(" ") || "…";
      const frac = shown / words.length;
      bar.firstChild.style.width = `${Math.min(100, frac * 100)}%`;
      time.textContent = `${mmss(frac * totalSec)} / ${mmss(totalSec)}`;
    };
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
    bar.addEventListener("click", (e) => {
      const r = bar.getBoundingClientRect();
      shown = ((e.clientX - r.left) / r.width) * words.length;
      draw();
    });
    const playBtn = el("button", { onclick: play }, "▶ Play");
    const speedBtn = el("button", { class: "small", onclick: () => {
      speed = speed === 1 ? 2 : 1; speedBtn.textContent = `${speed}×`;
    } }, "1×");

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

    put(root, 
      el("div", { class: "pane-head" }, el("h2", {}, "Message"),
        el("span", { class: "muted" }, `${clock(current.receivedAt)} · ${phone(current.callerId)} · ${mmss(current.durationSec)}`)),
       el("p", { class: "workload muted" },
         `Costs the agent ${hm(workloadMin)}: ${hm(listenMin)} listening, ${hm(a.handleMin)} handling, ${hm(a.callbackMin)} on a callback.`),
      el("div", { class: "player" }, playBtn, speedBtn, bar, time),
      text,
      el("h3", {}, "Your entry"),
      form,
    );
    draw();
  }
  store.subscribe((s) => open(s.selected), ["selected"]);
}
