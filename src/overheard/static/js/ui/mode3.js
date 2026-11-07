// Mode 3: the archive views, one renderer each (main.js's tabs and present.js's slides both use them).
// In order: root causes (the Pareto), event impact, journeys, promises, equity, the letter lab, ask the archive,
// knowledge gaps, weak signals, the staffing forecast, and "Overlooked before today" (the retro search).

// Mode 3, view 1: why people call — the archive's time by root cause, the Pareto.
import { api } from "../core/api.js";
import { renderPareto, fmtHours } from "../charts/pareto.js";

export function renderRootCauses(el, data) {
  const top = data.causes[0];
  const top80 = data.causes.slice(0, data.top80Count);
  const top80Share = top80.reduce((a, b) => a + b.share, 0);
  const unres = top.resolutionRate < 0.5;
  el.innerHTML = `
    <div class="m3-head">
      <h2>Why people call <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">Every one of ${data.totalContacts.toLocaleString()} contacts over three years, labelled with the reason
        behind it — something no one could read by hand. Where the centre's time actually goes:</p>
      <div class="m3-stats">
        <div class="stat"><b>${data.causes.length}</b><span class="muted">reasons people call</span></div>
        <div class="stat"><b>${top80.length}</b>
          <span class="muted">of them take ${(top80Share * 100).toFixed(0)}% of the time</span></div>
        <div class="stat"><b>1 in ${Math.round(1 / top.share)}</b><span class="muted">hours go to the top one</span></div>
      </div>
      <p class="m3-headline"><b>${top.cause.replace(/-/g, " ")}</b> takes one in ${Math.round(1 / top.share)} of the
        centre's hours (${fmtHours(top.hours)} over three years)${unres
          ? `, and ${((1 - top.resolutionRate) * 100).toFixed(0)}% of those calls never get resolved` : ""}.
        Fix the cause and the calls stop coming.</p>
    </div>
    <section class="m3-chart" aria-label="Pareto chart"></section>
    <table class="m3-table">
      <thead><tr><th>reason</th><th class="num">contacts</th><th class="num">hours</th><th class="num">share of time</th>
        <th class="num">resolved</th></tr></thead>
      <tbody>
        ${data.causes.slice(0, 10).map((c) => `<tr>
          <td>${c.cause.replace(/-/g, " ")}</td>
          <td class="num">${c.contacts.toLocaleString()}</td>
          <td class="num">${fmtHours(c.hours)}</td>
          <td class="num">${(c.share * 100).toFixed(1)}%</td>
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
  const quietRatio = (e) => e.excess / Math.max(1, e.expected) < 3; // "quiet" = under 3x its usual level
  el.innerHTML = `
    <div class="m3-head">
      <h2>What the calendar did to the phone <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">Every letter mailed, system release and policy change in three years, set against the calls
        that followed: how many came in the days after, how many that reason usually gets, and so how many extra
        calls each one caused.</p>
      <p class="m3-headline"><b>${top.name}</b> caused the biggest rush of the three years:
        ${top.count.toLocaleString()} calls in the days after it, ${top.excess.toLocaleString()} more than usual
        (${top.excessHours.toFixed(0)} extra agent-hours). The three biggest together caused
        ${top3Share.toLocaleString()} extra calls. The quiet ones are what a smooth release looks like.</p>
    </div>
    <table class="m3-table">
      <thead><tr><th>#</th><th>event</th><th>type</th><th class="num">date</th>
        <th class="num" data-tip="Calls in the days after the event">calls</th>
        <th class="num" data-tip="What that reason for calling usually gets in the same number of days">usually</th>
        <th class="num" data-tip="Calls the event caused: calls minus usually">extra calls</th>
        <th class="num" data-tip="Agent time the extra calls took">extra hours</th>
        <th class="num" data-tip="This event's part of all the extra calls events caused">share</th></tr></thead>
      <tbody>
        ${events.map((e, i) => `<tr${i < 3 ? ' class="hot"' : ""}>
          <td class="num">${i + 1}</td>
          <td>${e.name}</td>
          <td>${e.type.replace(/-/g, " ")}</td>
          <td class="num">${e.date}</td>
          <td class="num">${e.count.toLocaleString()}</td>
          <td class="num">${e.expected.toLocaleString()}</td>
          <td class="num">${e.excess.toLocaleString()}${quietRatio(e) ? ` <b class="quiet" data-tip="Under three times its usual level: barely noticed">quiet</b>` : ""}</td>
          <td class="num">${e.excessHours.toFixed(1)}</td>
          <td class="num">${e.excessShare.toFixed(1)}%</td>
        </tr>`).join("")}
      </tbody>
    </table>`;
}
// Mode 3, view 3: caller journeys — who is stuck in a loop, and where the loops start.
export function renderJourneys(el, data) {
  const top = data.causes[0];
  const loopShare = (data.loopContacts / data.totalContacts) * 100;
  const worst = data.worst[0];
  el.innerHTML = `
    <div class="m3-head">
      <h2>The callers who keep calling <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">Every contact from the same caller about the same issue is one journey, linked across the whole
        archive. A loop is ${data.loopMinimum} or more contacts on one issue whose last contact is still unresolved —
        the caller keeps calling and nobody has closed it. Where they start tells you which process step leaks:</p>
      <div class="m3-stats">
        <div class="stat"><b>${data.loops.toLocaleString()}</b><span class="muted">callers stuck in a loop</span></div>
        <div class="stat"><b>${data.loopContacts.toLocaleString()}</b>
          <span class="muted">loop contacts (${loopShare.toFixed(1)}% of all contacts)</span></div>
        <div class="stat"><b>${fmtHours(data.loopHours)}</b><span class="muted">agent-hours spent in loops</span></div>
      </div>
      <p class="m3-headline"><b>${top.cause.replace(/-/g, " ")}</b> is where the loops start:
        ${top.loops} stuck callers with ${top.contacts.toLocaleString()} contacts on that one issue
        (${fmtHours(top.hours)} agent-hours). The worst single journey so far:
        <b>${worst.contacts} contacts</b> from ${worst.caseId} about ${worst.cause.replace(/-/g, " ")} over
        ${Math.round(worst.days / 30)} months, still unresolved.</p>
    </div>
    <table class="m3-table">
      <thead><tr><th>loops start at</th><th class="num">stuck callers</th><th class="num">loop contacts</th>
        <th class="num">agent-hours</th></tr></thead>
      <tbody>
        ${data.causes.map((c, i) => `<tr${i === 0 ? ' class="hot"' : ""}>
          <td>${c.cause.replace(/-/g, " ")}</td>
          <td class="num">${c.loops.toLocaleString()}</td>
          <td class="num">${c.contacts.toLocaleString()}</td>
          <td class="num">${fmtHours(c.hours)}</td>
        </tr>`).join("")}
      </tbody>
    </table>
    <h3 class="muted">The worst loops — most contacts, longest stuck</h3>
    <table class="m3-table">
      <thead><tr><th>caller</th><th>issue</th><th class="num">contacts</th><th class="num">stuck for</th>
        <th class="num">last contact</th></tr></thead>
      <tbody>
        ${data.worst.map((w) => `<tr class="hot">
          <td>${w.caseId}</td>
          <td>${w.cause.replace(/-/g, " ")}</td>
          <td class="num">${w.contacts}</td>
          <td class="num">${Math.round(w.days / 30)} mo</td>
          <td class="num">${w.last.slice(0, 10)}</td>
        </tr>`).join("")}
      </tbody>
    </table>`;
}

// Mode 3, view 4: promises vs. outcomes — the centre's callback promises, checked against what happened.
export function renderPromises(el, data) {
  const t = data.totals;
  const pct = (x) => x == null ? "–" : `${(x * 100).toFixed(0)}%`;
  const causes = data.causes.slice(0, 12);
  const maxRate = Math.max(0.01, ...causes.map((c) => c.brokenRate));
  const worst = data.worstOffender;
  el.innerHTML = `
    <div class="m3-head">
      <h2>Every promise, checked <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">${t.promises.toLocaleString()} callback promises (${(data.promiseShare * 100).toFixed(0)}% of
        ${data.totalContacts.toLocaleString()} contacts), each with a due date. ${t.settled.toLocaleString()} have
        come due inside the archive and can be checked; ${t.pending.toLocaleString()} are still open past its end.
        Kept means the contact closed within the window; broken means it didn't:</p>
      <div class="m3-stats">
        <div class="stat"><b>${pct(t.brokenRate)}</b><span class="muted">of due promises broken, centre-wide</span></div>
        <div class="stat"><b>${t.broken.toLocaleString()}</b><span class="muted">promises broken</span></div>
        <div class="stat"><b>${t.pending.toLocaleString()}</b><span class="muted">still open, undatable</span></div>
      </div>
      ${worst ? `<p class="m3-headline"><b>${worst.cause.replace(/-/g, " ")}</b> breaks its promises more than any other
        cause: ${pct(worst.brokenRate)} of its due promises went unkept (${worst.broken} of ${worst.settled}).
        ${data.worstOffenderCause !== undefined ? "" : "If you promised a caller on that issue, this is the one to remember to keep."}</p>` : ""}
    </div>
    <h3 class="muted">Broken rate of due promises, by cause</h3>
    <div class="m3-bars" aria-label="Broken promise rates by cause"></div>
    <table class="m3-table">
      <thead><tr><th>cause</th><th class="num">promises</th><th class="num">due</th><th class="num">kept</th>
        <th class="num">broken</th><th class="num">open</th><th class="num">broken rate</th></tr></thead>
      <tbody>
        ${causes.map((c) => `<tr${c.cause === worst && worst ? ' class="hot"' : ""}>
          <td>${c.cause.replace(/-/g, " ")}</td>
          <td class="num">${c.promises.toLocaleString()}</td>
          <td class="num">${c.settled.toLocaleString()}</td>
          <td class="num">${c.kept.toLocaleString()}</td>
          <td class="num">${c.broken.toLocaleString()}</td>
          <td class="num">${c.pending.toLocaleString()}</td>
          <td class="num">${pct(c.brokenRate)}</td>
        </tr>`).join("")}
      </tbody>
    </table>
    <h3 class="muted">By team</h3>
    <table class="m3-table">
      <thead><tr><th>team</th><th class="num">promises</th><th class="num">kept</th><th class="num">broken</th>
        <th class="num">open</th><th class="num">broken rate</th></tr></thead>
      <tbody>
        ${data.teams.map((tm) => `<tr>
          <td>${tm.team}</td>
          <td class="num">${tm.promises.toLocaleString()}</td>
          <td class="num">${tm.kept.toLocaleString()}</td>
          <td class="num">${tm.broken.toLocaleString()}</td>
          <td class="num">${tm.pending.toLocaleString()}</td>
          <td class="num">${pct(tm.brokenRate)}</td>
        </tr>`).join("")}
      </tbody>
    </table>`;
  const bars = el.querySelector(".m3-bars");
  bars.innerHTML = causes.map((c) => `
    <div class="m3-bar-row" title="${c.cause.replace(/-/g, " ")}: ${c.broken}/${c.settled} broken">
      <span class="m3-bar-label">${c.cause.replace(/-/g, " ")}</span>
      <span class="m3-bar-track"><span class="m3-bar-fill"
        style="width:${Math.max(1, (c.brokenRate / maxRate) * 100).toFixed(1)}%"></span></span>
      <span class="m3-bar-num">${pct(c.brokenRate)}</span>
    </div>`).join("");
}

export function renderEquity(el, data) {
  const rows = (list, unit) => list.map((r) => `<tr>
      <td>${r.name}</td>
      <td class="num">${r.contacts.toLocaleString()}</td>
      <td class="num">${r.avgWaitMin.toFixed(1)}${unit}</td>
      <td class="num">${r.medianWaitMin.toFixed(1)}${unit}</td>
      <td class="num">${(r.resolveRate * 100).toFixed(0)}%</td>
      <td class="num">${r.avgDaysToResolve == null ? "–" : r.avgDaysToResolve.toFixed(0)}</td>
    </tr>`).join("");
  const table = (list, name, unit) => `
    <h3 class="muted">${name}</h3>
    <table class="m3-table">
      <thead><tr><th>${name.toLowerCase()}</th><th class="num">contacts</th><th class="num">avg wait</th>
        <th class="num">median wait</th><th class="num">resolved</th><th class="num">days to resolve</th></tr></thead>
      <tbody>${rows(list, unit)}</tbody>
    </table>`;
  const worst = data.worstLanguage;
  el.innerHTML = `
    <div class="m3-head">
      <h2>Who waits how long <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">${data.totalContacts.toLocaleString()} contacts, grouped by the caller's language and
        channel. "Wait" is the centre's handle time per contact; "days to resolve" is how long the issue stayed
        open on the ones that did close:</p>
      ${worst ? `<p class="m3-headline"><b>${worst.slow}</b> callers wait the longest: ${worst.slowWaitMin.toFixed(1)} min
        per contact on average — <b>${worst.waitRatio}x</b> the ${worst.fast} callers at ${worst.fastWaitMin.toFixed(1)} min —
        and their issues resolve less often (${(worst.slowResolveRate * 100).toFixed(0)}% vs ${(worst.fastResolveRate * 100).toFixed(0)}%)
        and slower (${worst.slowDays} vs ${worst.fastDays} days). That's a service gap, not an accident of the average.</p>` : ""}
      <div class="m3-stats">
        <div class="stat"><b>${worst ? worst.waitRatio : "–"}x</b><span class="muted">slowest vs fastest wait ratio</span></div>
        <div class="stat"><b>${data.languages.length}</b><span class="muted">languages in the archive</span></div>
        <div class="stat"><b>${data.channels.length}</b><span class="muted">channels</span></div>
      </div>
    </div>
    <h3 class="muted">Average wait per contact, by language</h3>
    <div class="m3-bars" aria-label="Average wait times by language"></div>
    ${table(data.languages, "By language", " min")}
    ${table(data.channels, "By channel", " min")}`;
  const bars = el.querySelector(".m3-bars");
  const maxWait = Math.max(0.01, ...data.languages.map((r) => r.avgWaitMin));
  bars.innerHTML = data.languages.map((r) => `
    <div class="m3-bar-row" title="${r.name}: ${r.avgWaitMin.toFixed(1)} min average">
      <span class="m3-bar-label">${r.name}</span>
      <span class="m3-bar-track"><span class="m3-bar-fill"
        style="width:${Math.max(1, (r.avgWaitMin / maxWait) * 100).toFixed(1)}%"></span></span>
      <span class="m3-bar-num">${r.avgWaitMin.toFixed(1)} min</span>
    </div>`).join("");
}

// Mode 3, view 6: the letter lab — pre-test a draft notice against the archive.
const LETTER_SAMPLE =
  "Dear Claimant, we have made a determination that your records require re-verification of your " +
  "address and income. Pursuant to our prescribed regulations, subject to further review, your benefits " +
  "will be stopped if the re-verification documentation is not returned to us within 30 days. If you fail " +
  "to return the documentation, your payment may be suspended and you may owe back benefits for the months " +
  "in which no re-verification was on file at all.";

export function renderLetterLab(el) {
  el.innerHTML = `
    <div class="m3-head">
      <h2>Pre-test a letter before you mail it <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">Paste a draft letter. The lab finds the past mailing it most resembles, shows how many
        calls that mailing caused and what readers asked, and suggests a clearer version with how many calls
        it would save. Vaguer letters cause more calls.</p>
    </div>
    <div class="m3-letterlab-form">
      <label for="ll-draft" class="muted">Your draft notice</label>
      <textarea id="ll-draft" class="m3-letterlab-draft" rows="7">${LETTER_SAMPLE}</textarea>
      <button id="ll-run" class="m3-letterlab-run">Pre-test this letter</button>
    </div>
    <div class="m3-letterlab-results" hidden></div>`;
  const results = el.querySelector(".m3-letterlab-results");
  el.querySelector("#ll-run").addEventListener("click", async () => {
    const text = el.querySelector("#ll-draft").value.trim();
    if (!text) return;
    const btn = el.querySelector("#ll-run");
    btn.disabled = true;
    btn.textContent = "Checking the archive…";
    try {
      const data = await api.letterLab(text);
      renderLetterLabResults(results, data);
      results.hidden = false;
      results.scrollIntoView({ block: "nearest" });
    } catch (e) {
      results.innerHTML = `<p class="muted">Could not run the letter lab: ${e.message}</p>`;
      results.hidden = false;
    } finally {
      btn.disabled = false;
      btn.textContent = "Pre-test this letter";
    }
  });
}

function renderLetterLabResults(el, data) {
  const det = data.detected;
  const p = data.predicted;
  const r = data.rewrite;
  const q = data.archiveQuestions;
  const windowRows = p.perMailing.map((w) => `<tr>
      <td>${w.name}</td><td class="num">${w.date}</td>
      <td class="num">${w.count.toLocaleString()}</td><td class="num">${w.excess.toLocaleString()}</td>
    </tr>`).join("");
  el.innerHTML = `
    <h3 class="muted">What the lab found</h3>
    <p class="m3-headline">This draft sounds like <b>${det.label}</b>
      (matched on ${det.matchedWords.length} words: ${det.matchedWords.join(", ")}).
      Each of those mailings caused <b>${p.low.toLocaleString()}–${p.high.toLocaleString()}</b> extra calls,
      and this wording should cause about <b>${p.mid.toLocaleString()}</b> per mailing.
      The centre already answered this letter's questions <b>${q.count.toLocaleString()}</b> times.</p>
    <div class="m3-stats">
      <div class="stat"><b>${p.mid.toLocaleString()}</b><span class="muted">extra calls expected per mailing</span></div>
      <div class="stat"><b>${r.questionsBefore} → ${r.questionsAfter}</b><span class="muted">reader questions: this draft → the rewrite</span></div>
      <div class="stat"><b>-${(r.reductionPct * 100).toFixed(0)}%</b><span class="muted">fewer calls with the rewrite</span></div>
    </div>
    <h3 class="muted">What makes this draft hard to follow</h3>
    <p>${data.clarity.issues.length ? data.clarity.issues.join(" · ") : "No clarity issues found."}</p>
    ${q.sample.length ? `
    <h3 class="muted">What readers actually asked about this notice</h3>
    <ul class="m3-letterlab-questions">
      ${q.sample.map((s) => `<li>"${s.text}" <span class="muted">— ${s.channel}, ${s.at.slice(0, 10)}</span></li>`).join("")}
    </ul>` : ""}
    <h3 class="muted">The suggested rewrite</h3>
    <pre class="m3-letterlab-rewrite">${r.text}</pre>
    <p class="m3-headline">With the rewrite: clarity <b>${Math.round(data.clarity.score * 100)} →
      ${Math.round(r.clarityScore * 100)}</b> out of 100, calls per mailing <b>${r.volumeBefore.toLocaleString()} →
      ${r.volumeAfter.toLocaleString()}</b>, reader questions <b>${r.questionsBefore} → ${r.questionsAfter}</b>.</p>
    ${p.perMailing.length ? `
    <h3 class="muted">The past mailings this was measured against</h3>
    <table class="m3-table">
      <thead><tr><th>mailing</th><th class="num">date</th><th class="num">calls after it</th>
        <th class="num">extra calls</th></tr></thead>
      <tbody>${windowRows}</tbody>
    </table>` : ""}`;
}

// Mode 3, view 7: ask the archive — plain-English questions over pre-computed totals.
const ASK_SAMPLE = "Why did contacts about the 22-B letter spike in June 2025?";

export function renderAsk(el) {
  el.innerHTML = `
    <div class="m3-head">
      <h2>Ask the archive <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">Ask about an issue, a state, a language, a month or a year. You get how many calls there
        were, how that compares with the period before, what was happening on the calendar, and real messages
        as evidence. If it can't tell what you mean, it says so instead of guessing.</p>
    </div>
    <div class="m3-ask-form">
      <label for="ask-q" class="muted">Your question</label>
      <div class="m3-ask-row">
        <input id="ask-q" class="m3-ask-input" type="text" placeholder="${ASK_SAMPLE}">
        <button id="ask-sample" class="m3-ask-sample" type="button">Try a sample</button>
        <button id="ask-run" class="m3-ask-run" type="button">Ask</button>
      </div>
    </div>
    <div class="m3-ask-results" hidden></div>`;
  const results = el.querySelector(".m3-ask-results");
  const run = () => {
    const text = el.querySelector("#ask-q").value.trim();
    if (!text) return;
    const btn = el.querySelector("#ask-run");
    btn.disabled = true;
    btn.textContent = "Counting…";
    api.askArchive(text)
      .then((data) => {
        renderAskResults(results, data);
        results.hidden = false;
        results.scrollIntoView({ block: "nearest" });
      })
      .catch((e) => {
        results.innerHTML = `<p class="muted">Could not ask the archive: ${e.message}</p>`;
        results.hidden = false;
      })
      .finally(() => {
        btn.disabled = false;
        btn.textContent = "Ask";
      });
  };
  el.querySelector("#ask-run").addEventListener("click", run);
  el.querySelector("#ask-q").addEventListener("keydown", (ev) => { if (ev.key === "Enter") run(); });
  el.querySelector("#ask-sample").addEventListener("click", () => {
    el.querySelector("#ask-q").value = ASK_SAMPLE;
    run();
  });
}

function renderAskResults(el, data) {
  const t = data.totals || {};
  const events = (t.events || []).map((e) => `<li>
      ${e.name} <span class="muted">— ${e.type}, ${e.window}</span>${e.sameCause ? " <b>(same issue)</b>" : ""}
    </li>`).join("");
  const evidence = (t.evidence || []).map((s) => `<li>"${s}"</li>`).join("");
  el.innerHTML = `
    <p class="m3-headline ${data.understood ? "" : "muted"}">${data.understood ? "" : "(I could not scope this) "}${data.answer}</p>
    ${t.events?.length ? `<h3 class="muted">Calendar events overlapping the period</h3><ul class="m3-ask-events">${events}</ul>` : ""}
    ${t.evidence?.length ? `<h3 class="muted">Evidence: real messages from the archive</h3><ul class="m3-ask-evidence">${evidence}</ul>` : ""}`;
}

export function renderKnowledgeGaps(el, data) {
  const gapRow = (g, i) => `<div class="m3-kg-row">
      <div class="m3-kg-gap">
        <b class="m3-kg-rank">#${i + 1}</b> <b>${g.name}</b>
        <span class="muted">${g.count.toLocaleString()} calls · ${g.sharePct}% of all calls · ${g.hours} agent-hours · ${Math.round(g.resolveRate * 100)}% resolved</span>
      </div>
      <div class="m3-kg-faq"><span class="prov" data-tip="A help article the AI drafted to fill the gap">help article draft</span><b>${g.faq.title}</b><p>${g.faq.body}</p></div>
      <div class="m3-kg-ivr"><span class="prov" data-tip="What the phone menu could say, so callers get the answer before they reach a person">phone menu line</span> ${g.ivr}</div>
    </div>`;
  const all = data.gaps || [];
  const gaps = all.slice(0, 6).map(gapRow).join("")
    + (all.length > 6 ? `<details class="m3-more"><summary>Show the other ${all.length - 6}</summary>
        <div class="m3-kg-gaps">${all.slice(6).map((g, i) => gapRow(g, i + 6)).join("")}</div></details>` : "");
  const weak = (data.weakCoverage || []).map((w) => {
    const words = Object.entries(w.uncovered || {}).slice(0, 8).map(([word, phr]) =>
      `<li><b>${word}</b> <span class="muted">— “${phr[0]}”</span></li>`).join("");
    return `<div class="m3-kg-weak"><b>${w.articleTitle}</b> <span class="muted">never uses the words callers use:</span>
      <ul>${words}</ul></div>`;
  }).join("");
  el.innerHTML = `
    <div class="m3-head">
      <h2>Questions no article answers <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">What callers keep asking that no help article answers, biggest first, each with a
        drafted help article and phone menu line, so the next caller gets the answer without waiting for a
        person.</p>
    </div>
    <p class="m3-headline">The help articles cover <b>${data.coveredDrivers} of ${data.drivers}</b> reasons people
      call: <b>${data.coveragePct}%</b> of calls. ${all.length} reasons have no article at all.</p>
    ${gaps ? `<h3 class="muted">Unanswered, biggest first</h3><div class="m3-kg-gaps">${gaps}</div>` : ""}
    ${weak ? `<details class="m3-more"><summary>Articles that exist but miss the words callers use</summary>
      <div class="m3-kg-weaks">${weak}</div></details>` : ""}`;
}

export function renderWeakSignals(el, data) {
  const cards = (data.signals || []).map((s) => {
    const trig = (s.triggers || []).map((t) => `${t.name} (${t.date})`).join(", ");
    return `<div class="m3-ws-card">
      <div class="m3-ws-title"><b>${s.spikeEvent.name}</b> <span class="muted">${s.spikeEvent.date}</span></div>
      <p class="muted">The worst week brought ${s.spikeWeekContacts.toLocaleString()} calls. But for
        ${s.trickleWeeks} weeks before, from ${s.trickleStart}, '${s.driver.replace(/-/g, " ")}' calls already ran
        high: up to ${s.tricklePeak} a week, ${s.multipleOfBaseline} times the usual ${s.baselinePerWeek}.</p>
      <p><span class="prov" data-tip="A simple alert on unusually many calls of one kind would have fired this early">could have been caught</span>
        about <b>${s.monthsEarly} months early</b> (${s.weeksEarly} weeks): ${s.trickleTotal} early calls, vs
        ${s.spikeWeekContacts.toLocaleString()} in the worst week.</p>
      ${trig ? `<p class="muted">The trickle lines up with: ${trig}.</p>` : ""}
    </div>`;
  }).join("");
  el.innerHTML = `
    <div class="m3-head">
      <h2>Early warnings that were missed <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">A rush of calls looks sudden the week it hits. This looks at the weeks <i>before</i> each
        rush: was there a trickle no one noticed, and how early could it have been caught?</p>
    </div>
    <p class="m3-headline">${data.headline}</p>
    ${cards ? `<h3 class="muted">The trickle before the rush</h3><div class="m3-ws-cards">${cards}</div>` : ""}`;
}

export function renderStaffingForecast(el, data) {
  const rows = (data.days || []).map((d) => `<tr>
      <td>${d.date}</td><td>${d.weekday}</td>
      <td>${d.baseline}</td><td>${d.eventExcess}</td>
      <td><b>${d.projectedContacts}</b></td><td>${d.projectedAgentHours}h</td>
    </tr>`).join("");
  const cards = (data.events || []).map((e) => `<div class="m3-sf-card">
      <div class="m3-sf-title"><b>${e.name}</b> <span class="muted">${e.date} · ${e.type.replace(/-/g, " ")}</span></div>
      <p class="muted">Still active in the window: <b>${e.remainingDays} day${e.remainingDays === 1 ? "" : "s"} left</b>.
        Expect about <b>${e.projectedExcessContacts} extra '${e.driver.replace(/-/g, " ")}' calls</b>
        (~${e.projectedExcessAgentHours} agent-hours) on top of a normal day.</p>
    </div>`).join("");
  el.innerHTML = `
    <div class="m3-head">
      <h2>Staffing forecast <span class="prov" data-tip="The AI labelled every contact once; this view counts those labels with ordinary code, so every number can be checked">counted from the archive</span></h2>
      <p class="muted">The next ${data.horizonDays} days: a normal weekday (${data.weekdayBaseline} calls, from
        the last 90 weekdays), plus the extra calls each event on the calendar is still bringing in, and the
        agent-hours that takes.</p>
    </div>
    <p class="m3-headline">${data.headline}</p>
    ${cards ? `<h3 class="muted">Calendar events in the window</h3><div class="m3-sf-cards">${cards}</div>` : ""}
    <h3 class="muted">Day by day</h3>
    <table class="m3-sf-table">
      <thead><tr><th>date</th><th>day</th><th>normal day</th><th>extra from events</th><th>expected calls</th><th>agent-hours</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="muted">In all: <b>${data.totalProjectedContacts} calls</b> and
      <b>${data.totalProjectedAgentHours} agent-hours</b>. The centre is closed at weekends, so those days are
      empty.</p>`;
}

// Mode 3: "Overlooked before today": today's new problem, searched for in past contacts nobody ticketed.
const escHtml = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fmtDay = (d) => new Date(`${d}T12:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });

export function renderOverlooked(el, data) {
  const s = data?.suggested;
  el.innerHTML = `
    <div class="m3-head">
      <h2>Overlooked before today <span class="prov" data-tip="Retrieval finds past contacts close to the problem; the AI confirms each with a reason; the dates, counts and hours are counted with ordinary code">AI-confirmed, counted</span></h2>
      <p class="muted">Once a new problem is spotted, the AI reads back through the archive for callers who had it
        before anyone knew: calls that were taken for something else and never ticketed, or sent to the wrong team.
        It runs when you ask, never on every call.</p>
    </div>
    <form class="m3-retro-form">
      <label class="muted" for="retro-desc">The problem${s ? ` <span class="prov" data-tip="Offered from the spike Mode 2 found today: its title, its first callers' words, and the team that owns it">from ${escHtml(s.origin)}</span>` : ""}</label>
      <textarea id="retro-desc" rows="2">${escHtml(s?.description || "")}</textarea>
      <div class="m3-retro-row">
        <label class="muted">Look back from <input id="retro-since" type="date" value="${escHtml(s?.since || "")}"></label>
        <span class="muted">to ${s ? fmtDay(s.until) : "today"}</span>
        <button class="m3-ask-run" type="submit">Search the archive</button>
      </div>
      ${s?.examples?.length ? `<details class="m3-more"><summary>Today's callers it starts from (${s.examples.length})</summary>
        <ul class="m3-letterlab-questions">${s.examples.map((x) => `<li>“${escHtml(x)}”</li>`).join("")}</ul></details>` : ""}
    </form>
    <div class="m3-retro-results">${s ? "" : `<p class="muted">No spike today to start from: describe a problem above.</p>`}</div>`;
  const form = el.querySelector("form");
  const out = el.querySelector(".m3-retro-results");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const btn = form.querySelector("button");
    const description = el.querySelector("#retro-desc").value.trim();
    if (!description) return;
    btn.disabled = true; btn.textContent = "Reading back…";
    const def = { ...(s || { examples: [], until: new Date().toISOString().slice(0, 10) }), description,
      since: el.querySelector("#retro-since").value || s?.since };
    if (s && description !== s.description) def.origin = "analyst";
    api.retroSearch(def).then((r) => renderRetroResults(out, r))
      .catch((err) => { out.innerHTML = `<p class="muted">Could not search: ${escHtml(err.message)}</p>`; })
      .finally(() => { btn.disabled = false; btn.textContent = "Search the archive"; });
  });
  if (s) form.requestSubmit();   // the suggestion is the demo's point: show it found, then let them change it
}

function renderRetroResults(el, r) {
  const m = r.summary;
  if (!m.count) {
    el.innerHTML = `<p class="m3-headline muted">Nothing overlooked: of ${r.checked} close past contacts, none was this problem and missed.</p>`;
    return;
  }
  const recorded = [...new Set(r.items.map((i) => i.recordedAs.replace(/-/g, " ")))];
  const mark = (text, words) => {
    const set = new Set(words);
    return escHtml(text).replace(/[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/g, (w) => set.has(w.toLowerCase()) ? `<mark>${w}</mark>` : w);
  };
  el.innerHTML = `
    <p class="m3-headline"><b>${m.count} callers</b> had this problem before today, on ${m.days} different days from
      ${fmtDay(m.first)} to ${fmtDay(m.last)}: <b>${m.leadDays} days</b> before it broke out. They were taken for
      ${recorded.join(", ")} and never reached ${escHtml(m.team || "the owning team")}, and they took
      <b>${m.agentHours} agent-hours</b> that a ticket on the first one could have saved.</p>
    <div class="m3-stats">
      <div class="stat"><b>${m.count}</b><span class="muted">overlooked callers</span></div>
      <div class="stat"><b>${m.leadDays} days</b><span class="muted">sooner it could have been spotted</span></div>
      <div class="stat"><b>${m.agentHours} h</b><span class="muted">of agent time on them</span></div>
    </div>
    <table class="m3-table m3-retro-table">
      <thead><tr><th>when</th><th>recorded as</th><th>what they said</th><th>why it's a match</th></tr></thead>
      <tbody>${r.items.map((i) => `<tr>
        <td class="num">${fmtDay(i.at.slice(0, 10))}</td>
        <td>${escHtml(i.recordedAs.replace(/-/g, " "))} <span class="muted">· ${escHtml(i.overlooked)}</span></td>
        <td data-tip="Matching words: ${escHtml(i.matched.join(", "))}">${mark(i.text, i.matched)}</td>
        <td class="muted">${escHtml(i.reason)}</td></tr>`).join("")}</tbody>
    </table>
    <p class="muted">${r.checked} close past contacts were checked; ${m.count} confirmed.</p>`;
}
