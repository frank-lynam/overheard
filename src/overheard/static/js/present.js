// Presenter mode: a full-screen slide deck over the Mode 3 archive views.
// The same renderers as the workbench (js/ui/mode3.js), one view per slide,
// with keyboard navigation, staggered reveal, and an assumptions panel.
import { api } from "./core/api.js";
import {
  renderRootCauses, renderEventImpact, renderJourneys, renderPromises,
  renderEquity, renderLetterLab, renderAsk, renderKnowledgeGaps,
  renderWeakSignals, renderStaffingForecast,
} from "./ui/mode3.js";

const SLIDES = [
  { id: "root-causes", title: "Root causes", load: () => api.rootCauses(), render: (el, d) => renderRootCauses(el, d) },
  { id: "event-impact", title: "Event impact", load: () => api.eventImpact(), render: (el, d) => renderEventImpact(el, d) },
  { id: "journeys", title: "Journeys", load: () => api.journeys(), render: (el, d) => renderJourneys(el, d) },
  { id: "promises", title: "Promises", load: () => api.promises(), render: (el, d) => renderPromises(el, d) },
  { id: "equity", title: "Equity", load: () => api.equity(), render: (el, d) => renderEquity(el, d) },
  { id: "letter-lab", title: "Letter lab", load: () => null, render: (el) => renderLetterLab(el) },
  { id: "ask", title: "Ask the archive", load: () => null, render: (el) => renderAsk(el) },
  { id: "knowledge-gaps", title: "Knowledge gaps", load: () => api.knowledgeGaps(), render: (el, d) => renderKnowledgeGaps(el, d) },
  { id: "weak-signals", title: "Weak signals", load: () => api.weakSignals(), render: (el, d) => renderWeakSignals(el, d) },
  { id: "staffing-forecast", title: "Staffing", load: () => api.staffingForecast(), render: (el, d) => renderStaffingForecast(el, d) },
];

const stage = document.querySelector("#p-stage");
const dots = document.querySelector(".p-dots");
const count = document.querySelector("#p-count");
let current = -1;
const rendered = new Set(); // slide ids whose content is already in the stage

function buildDots() {
  SLIDES.forEach((s, i) => {
    const b = document.createElement("button");
    b.className = "p-dot";
    b.title = s.title;
    b.setAttribute("aria-label", `Slide ${i + 1}: ${s.title}`);
    b.addEventListener("click", () => go(i));
    dots.appendChild(b);
  });
}

function marks(el) {
  // Staggered reveal: mark the slide's top-level content blocks in order, then
  // let the CSS bring them in one by one (--reveal-step scales with the speed).
  const speed = document.body.dataset.speed || "normal";
  document.body.dataset.reveal = speed === "off" ? "0" : "1";
  const blocks = [...el.children];
  blocks.forEach((b, i) => {
    b.classList.add("p-reveal");
    b.style.setProperty("--i", i);
    b.classList.remove("in");
  });
  void el.offsetWidth; // force a reflow so the .in batch below is a fresh transition
  blocks.forEach((b) => b.classList.add("in"));
}

async function go(i) {
  i = Math.max(0, Math.min(SLIDES.length - 1, i));
  if (i === current && rendered.has(SLIDES[i].id)) return;
  current = i;
  const s = SLIDES[i];
  stage.innerHTML = "";
  const wrap = document.createElement("section");
  wrap.className = "p-slide";
  stage.appendChild(wrap);
  wrap.innerHTML = `<p class="muted">Reading the archive…</p>`;
  try {
    const data = await s.load();
    if (i !== current) return; // navigated away mid-load
    s.render(wrap, data);
    rendered.add(s.id);
    marks(wrap);
  } catch (e) {
    wrap.innerHTML = `<p class="muted">Could not read ${s.title}: ${e.message}</p>`;
  }
  [...dots.children].forEach((d, j) => d.classList.toggle("active", j === i));
  count.textContent = `${i + 1} / ${SLIDES.length}`;
  document.title = `Overheard — ${s.title}`;
  stage.scrollTop = 0;
}

// --- keyboard navigation -------------------------------------------------
document.addEventListener("keydown", (ev) => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
  switch (ev.key) {
    case "ArrowRight":
    case "PageDown":
    case " ":
      ev.preventDefault(); go(current + 1); break;
    case "ArrowLeft":
    case "PageUp":
      ev.preventDefault(); go(current - 1); break;
    case "Home":
      ev.preventDefault(); go(0); break;
    case "End":
      ev.preventDefault(); go(SLIDES.length - 1); break;
    case "a":
    case "A":
      toggleAssumptions(); break;
    default:
      if (/^[0-9]$/.test(ev.key)) go(parseInt(ev.key, 10) - 1);
  }
});

// --- assumptions panel ----------------------------------------------------
let assumptionsOpen = false;
let assumptionFacts = null;
const assumeBtn = document.querySelector("#p-assumptions");
const assumePanel = document.querySelector("#p-assumptions-panel");
const assumeFacts = document.querySelector("#p-assume-facts");

async function loadAssumptionFacts() {
  if (assumptionFacts) return assumptionFacts;
  assumptionFacts = { a: await api.assumptions() };
  return assumptionFacts;
}

async function toggleAssumptions() {
  assumptionsOpen = !assumptionsOpen;
  assumePanel.hidden = !assumptionsOpen;
  assumeBtn.setAttribute("aria-expanded", String(assumptionsOpen));
  if (assumptionsOpen) {
    assumeFacts.innerHTML = "<dd class='muted'>…</dd>";
    try {
      const { a } = await loadAssumptionFacts();
      const row = (k, v) => `<dt>${k}</dt><dd>${v}</dd>`;
      assumeFacts.innerHTML = [
        row("Archive span", "3 years of weekday voicemail (seeded, synthetic)"),
        row("Handling time", `${a.handleMin} min/message + listening at ${a.listenSpeed}x`),
        row("Callback", `${a.callbackMin} min, when a message needs one`),
        row("Shift", `${a.shiftStart}–${a.shiftEnd}, lunch ${a.lunch} for ${a.lunchMin} min`),
        row("Urgent window", `welfare/urgent hardship reached within ${a.urgentWithinMin} min`),
        row("Approving an AI answer", `${a.approveMin} min (mode 2: no listening, no callback)`),
      ].join("");
    } catch (e) {
      assumeFacts.innerHTML = `<dd class="muted">Could not read assumptions: ${e.message}</dd>`;
    }
  }
}
assumeBtn.addEventListener("click", toggleAssumptions);

// --- reveal speed ---------------------------------------------------------
document.querySelector("#p-speed").addEventListener("change", (ev) => {
  document.body.dataset.speed = ev.target.value;
  if (current >= 0) marks(document.querySelector(".p-slide")); // re-run the reveal
});

// --- full screen ------------------------------------------------------------
document.querySelector("#p-fullscreen").addEventListener("click", async () => {
  if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
  else await document.documentElement.requestFullscreen().catch(() => {});
});

buildDots();
go(0);