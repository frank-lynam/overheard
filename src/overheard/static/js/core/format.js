// Small formatting helpers shared by the panes.
export const clock = (iso) => {
  const t = iso.includes("T") ? iso.split("T")[1] : iso;
  let [h, m] = t.split(":").map(Number);
  const pm = h >= 12;
  h = h % 12 || 12;
  return `${h}:${String(m).padStart(2, "0")} ${pm ? "pm" : "am"}`;
};
export const dayOf = (iso) => iso.split("T")[0];
// "2026-03-12" -> "Thu, Mar 12"
export const day = (iso) => new Date(`${iso.slice(0, 10)}T12:00`).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
export const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
export const hm = (min) => (min >= 60 ? `${Math.floor(min / 60)}h ${Math.round(min % 60)}m` : `${Math.round(min)}m`);
export const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
};

// replaceChildren, leaving out empty slots (null, false), so a missing piece never shows up as the text "null"
export const put = (root, ...kids) => root.replaceChildren(...kids.flat().filter((k) => k != null && k !== false));
// "+1-614-555-0142" -> "(614) 555-0142"
export const phone = (p) => {
  const d = (p || "").replace(/\D/g, "").slice(-10);
  return d.length === 10 ? `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}` : p;
};
