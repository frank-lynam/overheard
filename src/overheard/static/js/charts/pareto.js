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

// `data` must be the /api/archive/root-causes payload, pre-sorted by hours desc.
export function renderPareto(el, data) {
  const top = data.causes.slice(0, 12);
  const others = data.causes.slice(12);
  const bars = [...top, ...(others.length ? [{ cause: "all other causes", hours: others.reduce((a, b) => a + b.hours, 0), share: others.reduce((a, b) => a + b.share, 0) }] : [])];
  const W = 720, H = 300, padL = 44, padB = 58, padT = 14, padR = 44;
  const iw = W - padL - padR, ih = H - padT - padB;
  const maxH = Math.max(...bars.map((b) => b.hours));
  const bw = iw / bars.length;
  const pct = (x) => padL + (x * iw) / 100;

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

  // axes + hour gridlines
  for (let i = 0; i <= 4; i++) {
    const y = padT + ih - (ih * i) / 4;
    add("line", { x1: padL, y1: y, x2: W - padR, y2: y, stroke: "var(--line)", "stroke-width": 1 });
    add("text", { x: padL - 6, y: y + 4, "text-anchor": "end", fill: "var(--muted)", "font-size": 10 }, fmtHours((maxH * i) / 4));
  }
  // the 80% guide on the cumulative axis
  const y80 = padT + ih * 0.2;
  add("line", { x1: padL, y1: y80, x2: W - padR, y2: y80, stroke: "var(--late, #b3261e)", "stroke-dasharray": "4 4", "stroke-width": 1 });
  add("text", { x: W - padR, y: y80 - 4, "text-anchor": "end", fill: "var(--late, #b3261e)", "font-size": 10 }, "80%");

  let cum = 0;
  const line = [];
  bars.forEach((b, i) => {
    const h = (b.hours / maxH) * ih;
    const x = padL + i * bw;
    cum += b.share;
    const topY = padT + ih * (1 - cum);
    line.push([x + bw / 2, topY]);
    add("rect", { x: x + 2, y: padT + ih - h, width: bw - 4, height: h, fill: i < 12 ? PALETTE[Math.min(i, PALETTE.length - 1)] : "#c9c4ba", rx: 2 });
    const label = add("text", { x: x + bw / 2, y: H - padB + 14, "text-anchor": "end", fill: "var(--ink)", "font-size": 10 }, b.cause.replace(/-/g, " "));
    label.setAttribute("transform", `rotate(-32 ${x + bw / 2} ${H - padB + 14})`);
    add("text", { x: x + bw / 2, y: padT + ih - h - 4, "text-anchor": "middle", fill: "var(--muted)", "font-size": 9 }, (b.share * 100).toFixed(1) + "%");
  });
  add("polyline", { points: line.map((p) => p.join(",")).join(" "), fill: "none", stroke: "var(--accent, #2e5d8a)", "stroke-width": 2 });
  line.forEach((p) => add("circle", { cx: p[0], cy: p[1], r: 2.5, fill: "var(--accent, #2e5d8a)" }));

  el.innerHTML = "";
  el.appendChild(svg);
}

export { fmtHours, fmtUsd };