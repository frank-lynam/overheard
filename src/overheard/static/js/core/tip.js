// Hover hints: one styled tooltip for every element with data-tip (or a title, which is taken over so
// the browser's plain one doesn't show too). Shows on hover and on keyboard focus; never blocks a click.
const tip = document.createElement("div");
tip.className = "tip";
tip.setAttribute("role", "tooltip");
tip.hidden = true;
document.addEventListener("DOMContentLoaded", () => document.body.append(tip));
if (document.body) document.body.append(tip);

let shownFor = null;
function show(target) {
  if (target.hasAttribute("title")) {
    target.dataset.tip = target.getAttribute("title");
    target.removeAttribute("title");
  }
  const text = target.dataset.tip;
  if (!text) return;
  shownFor = target;
  tip.textContent = text;
  tip.hidden = false;
  const r = target.getBoundingClientRect(), t = tip.getBoundingClientRect();
  const above = r.top - t.height - 8;
  const top = above > 8 ? above : r.bottom + 8;
  const left = Math.min(Math.max(8, r.left + r.width / 2 - t.width / 2), innerWidth - t.width - 8);
  tip.style.top = `${top}px`;
  tip.style.left = `${left}px`;
}
function hide() { shownFor = null; tip.hidden = true; }
const find = (e) => e.target.closest?.("[data-tip], [title]:not(svg *)");
document.addEventListener("pointerover", (e) => { const t = find(e); if (t && t !== shownFor) show(t); else if (!t) hide(); });
document.addEventListener("focusin", (e) => { const t = find(e); if (t) show(t); });
document.addEventListener("focusout", hide);
addEventListener("scroll", hide, true);
