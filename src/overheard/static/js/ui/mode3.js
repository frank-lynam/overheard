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

// Mode 3, view 2: the calendar, checked against the phone — which events actually moved the volume.
export function renderEventImpact(el, data) {
  const events = data.events;
  const top = events[0];
  const top3 = events.slice(0, 3);
  const top3Share = top3.reduce((a, b) => a + b.excess, 0);
  const quietRatio = (e) => e.excess / Math.max(1, e.expected) < 3; // "quiet" = less than 3x its own baseline
  el.innerHTML = `
    <div class="m3-head">
      <h2>What the calendar did to the phone <span class="prov">plain code · window vs. baseline</span></h2>
      <p class="muted">Each event on the archive's calendar (mailings, releases, policy changes) gets a window of
        days after it, compared against its own cause's weekday rate in the 90 weekdays before. Excess is the calls
        the event caused, above business as usual:</p>
      <p class="m3-headline"><b>${top.name}</b> drove the loudest spike of the three years:
        ${top.count.toLocaleString()} contacts in its window, ${top.excess.toLocaleString()} above what the cause's
        own baseline predicted (${top.excessHours.toFixed(0)} excess agent-hours, ${top.excessShare.toFixed(1)}% of
        all event-driven work). The three loudest events together account for
        ${top3Share.toLocaleString()} excess contacts. The quiet ones tell you the release was boring — as planned.</p>
    </div>
    <table class="m3-table">
      <thead><tr><th>#</th><th>event</th><th>type</th><th class="num">date</th><th class="num">contacts</th>
        <th class="num">expected</th><th class="num">excess</th><th class="num">excess hours</th>
        <th class="num">share of excess</th></tr></thead>
      <tbody>
        ${events.map((e, i) => `<tr${i < 3 ? ' class="hot"' : ""}>
          <td class="num">${i + 1}</td>
          <td>${e.name}</td>
          <td>${e.type}</td>
          <td class="num">${e.date}</td>
          <td class="num">${e.count.toLocaleString()}</td>
          <td class="num">${e.expected.toLocaleString()}</td>
          <td class="num">${e.excess.toLocaleString()}${quietRatio(e) ? ` <b class="quiet">quiet</b>` : ""}</td>
          <td class="num">${e.excessHours.toFixed(1)}</td>
          <td class="num">${e.excessShare.toFixed(1)}%</td>
        </tr>`).join("")}
      </tbody>
    </table>`;
}