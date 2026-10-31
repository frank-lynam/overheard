// Mode 3, view 1: the archive dashboard — cost by root cause, the Pareto.
import { renderPareto, fmtHours, fmtUsd } from "../charts/pareto.js";

export function renderRootCauses(el, data) {
  const top = data.causes[0];
  const top80 = data.causes.slice(0, data.top80Count);
  const top80Share = top80.reduce((a, b) => a + b.share, 0);
  const unres = top.resolutionRate < 0.5;
  el.innerHTML = `
    <div class="m3-head">
      <h2>The archive, by the numbers <span class="prov">plain code · pre-labeled</span></h2>
      <p class="muted">${data.totalContacts.toLocaleString()} contacts over three years
        (${Math.round(data.totalHours / 3).toLocaleString()} agent-hours a year, at a labour rate of
        $${data.laborRate}/hr). What it costs, and where it goes:</p>
      <div class="m3-stats">
        <div class="stat"><b>${fmtUsd(data.annualCostUsd)}</b><span class="muted">agent-hours a year</span></div>
        <div class="stat"><b>${fmtHours(data.annualHours)}</b><span class="muted">hours / year, all causes</span></div>
        <div class="stat"><b>${top80.length} of ${data.causes.length}</b>
          <span class="muted">causes hold ${(top80Share * 100).toFixed(0)}% of the cost</span></div>
      </div>
      <p class="m3-headline"><b>${top.cause.replace(/-/g, " ")}</b> is the costliest single cause:
        ${fmtHours(top.hours)} hours over three years (${(top.share * 100).toFixed(1)}% of all agent-hours) —
        one in ${Math.round(1 / top.share)} of the centre's hours.
        ${unres ? `And ${((1 - top.resolutionRate) * 100).toFixed(0)}% of them are never resolved.` : ""}</p>
    </div>
    <section class="m3-chart" aria-label="Pareto chart"></section>
    <table class="m3-table">
      <thead><tr><th>cause</th><th class="num">contacts</th><th class="num">hours</th><th class="num">share</th>
        <th class="num">est. cost / yr</th><th class="num">resolved</th></tr></thead>
      <tbody>
        ${data.causes.slice(0, 10).map((c) => `<tr>
          <td>${c.cause.replace(/-/g, " ")}</td>
          <td class="num">${c.contacts.toLocaleString()}</td>
          <td class="num">${fmtHours(c.hours)}</td>
          <td class="num">${(c.share * 100).toFixed(1)}%</td>
          <td class="num">${fmtUsd(c.annualCostUsd)}</td>
          <td class="num">${(c.resolutionRate * 100).toFixed(0)}%</td>
        </tr>`).join("")}
      </tbody>
    </table>`;
  renderPareto(el.querySelector(".m3-chart"), data);
}