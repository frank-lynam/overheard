// A hand-written Pareto chart: bars by cost, a cumulative-share line, an 80% guide. No libraries.
const PALETTE = ["#2e5d8a", "#5b86ad", "#8aa8c5", "#b3c7da", "#d4c9a8", "#a8a29a"];

function fmtHours(h) {
  return h >= 1000 ? (h / 1000).toFixed(1) + "k" : String(Math.round(h));
}

function fmtUsd(n) {
  if (n >= 1_000_000) return "$" + (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1000) return "$" + Math.round(n / 1000) + "k";
  return "$" + n;
}

// A round axis: the top tick at or above `max`, in steps of 1, 2, 2.5 or 5 times a power of ten.
function niceTicks(max, count = 4) {
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  return Array.from({ length: Math.ceil(max / step) + 1 }, (_, i) => i * step);
}

// `data` must be the /api/archive/root-causes payload, pre-sorted by hours desc. The biggest causes
// get bars; the rest are summed in a note under the chart (one lumped bar would dwarf the real ones).
export function renderPareto(el, data, shown = 12) {
  const bars = data.causes.slice(0, shown);
  const rest = data.causes.slice(shown);
  const W = 720, H = 330, padL = 96, padB = 96, padT = 16, padR = 40;
  const iw = W - padL - padR, ih = H - padT - padB;
  const ticks = niceTicks(Math.max(...bars.map((b) => b.hours)));
  const top = ticks[ticks.length - 1];
  const bw = iw / bars.length;

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Pareto chart of agent-hours by root cause");
  const add = (tag, attrs, text) => {
    const n = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text != null) n.textContent = text;
    svg.appendChild(n);
    return n;
  };

  // hours on the left, gridlines at round values
  ticks.forEach((t) => {
    const y = padT + ih - (ih * t) / top;
    add("line", { x1: padL, y1: y, x2: W - padR, y2: y, stroke: "var(--line)", "stroke-width": 1 });
    add("text", { x: padL - 6, y: y + 4, "text-anchor": "end", fill: "var(--muted)", "font-size": 10 }, fmtHours(t));
  });
  add("text", { x: padL - 6, y: padT - 4, "text-anchor": "end", fill: "var(--muted)", "font-size": 9 }, "hours");
  // the cumulative share on the right, with the 80% guide
  [0, 25, 50, 75, 100].forEach((p) => {
    add("text", { x: W - padR + 6, y: padT + ih - (ih * p) / 100 + 4, fill: "var(--muted)", "font-size": 10 }, p + "%");
  });
  const y80 = padT + ih * 0.2;
  add("line", { x1: padL, y1: y80, x2: W - padR, y2: y80, stroke: "var(--late, #b3261e)", "stroke-dasharray": "4 4", "stroke-width": 1 });
  add("text", { x: W - padR - 4, y: y80 - 4, "text-anchor": "end", fill: "var(--late, #b3261e)", "font-size": 10 }, "80% of all hours");

  let cum = 0;
  const line = [];
  bars.forEach((b, i) => {
    const h = (b.hours / top) * ih;
    const x = padL + i * bw;
    cum += b.share;
    line.push([x + bw / 2, padT + ih * (1 - cum)]);
    add("rect", { x: x + 2, y: padT + ih - h, width: bw - 4, height: h, fill: PALETTE[Math.min(i, PALETTE.length - 1)], rx: 2 });
    const name = b.cause.replace(/-/g, " ");
    const label = add("text", { x: x + bw / 2, y: H - padB + 12, "text-anchor": "end", fill: "var(--ink)", "font-size": 10 },
      name.length > 22 ? name.slice(0, 21) + "…" : name);
    label.setAttribute("transform", `rotate(-40 ${x + bw / 2} ${H - padB + 12})`);
    const tip = document.createElementNS(ns, "title");  // the full name, on hover
    tip.textContent = name;
    label.appendChild(tip);
    add("text", { x: x + bw / 2, y: padT + ih - h - 4, "text-anchor": "middle", fill: "var(--muted)", "font-size": 9 }, (b.share * 100).toFixed(1) + "%");
  });
  add("polyline", { points: line.map((p) => p.join(",")).join(" "), fill: "none", stroke: "var(--accent, #2e5d8a)", "stroke-width": 2 });
  line.forEach((p) => add("circle", { cx: p[0], cy: p[1], r: 2.5, fill: "var(--accent, #2e5d8a)" }));

  el.innerHTML = "";
  el.appendChild(svg);
  if (rest.length) {
    const note = document.createElement("p");
    note.className = "muted m3-chart-note";
    const share = rest.reduce((a, b) => a + b.share, 0);
    note.textContent = `Not shown: the other ${rest.length} causes, ${(share * 100).toFixed(0)}% of hours between them, `
      + `none above ${(rest[0].share * 100).toFixed(1)}%.`;
    el.appendChild(note);
  }
}

export { fmtHours, fmtUsd };