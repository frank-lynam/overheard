// Mode 3, view 1: the archive dashboard — cost by root cause, the Pareto.
import { api } from "../core/api.js";
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
// Mode 3, view 3: caller journeys — who is stuck in a loop, and where the loops start.
export function renderJourneys(el, data) {
  const top = data.causes[0];
  const loopShare = (data.loopContacts / data.totalContacts) * 100;
  const worst = data.worst[0];
  el.innerHTML = `
    <div class="m3-head">
      <h2>The callers who keep calling <span class="prov">plain code · journeys over the archive</span></h2>
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
      <h2>Every promise, checked <span class="prov">plain code · promises vs. the archive</span></h2>
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
    <div class="m3-promises-bars" aria-label="Broken promise rates by cause"></div>
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
  const bars = el.querySelector(".m3-promises-bars");
  bars.innerHTML = causes.map((c) => `
    <div class="m3-promise-row" title="${c.cause.replace(/-/g, " ")}: ${c.broken}/${c.settled} broken">
      <span class="m3-promise-label">${c.cause.replace(/-/g, " ")}</span>
      <span class="m3-promise-track"><span class="m3-promise-fill"
        style="width:${Math.max(1, (c.brokenRate / maxRate) * 100).toFixed(1)}%"></span></span>
      <span class="m3-promise-num">${pct(c.brokenRate)}</span>
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
      <h2>Who waits how long <span class="prov">plain code · contacts by language and channel</span></h2>
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
    <div class="m3-equity-bars" aria-label="Average wait times by language"></div>
    ${table(data.languages, "By language", " min")}
    ${table(data.channels, "By channel", " min")}`;
  const bars = el.querySelector(".m3-equity-bars");
  const maxWait = Math.max(0.01, ...data.languages.map((r) => r.avgWaitMin));
  bars.innerHTML = data.languages.map((r) => `
    <div class="m3-equity-row" title="${r.name}: ${r.avgWaitMin.toFixed(1)} min average">
      <span class="m3-equity-label">${r.name}</span>
      <span class="m3-equity-track"><span class="m3-equity-fill"
        style="width:${Math.max(1, (r.avgWaitMin / maxWait) * 100).toFixed(1)}%"></span></span>
      <span class="m3-equity-num">${r.avgWaitMin.toFixed(1)} min</span>
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
      <h2>Pre-test a letter before you mail it <span class="prov">plain code · archive patterns</span></h2>
      <p class="muted">Paste a draft notice and the lab checks it against three years of the archive: which
        past mailing it sounds like, the calls that mailing actually drove, the questions its readers asked,
        and a clearer rewrite with a before/after prediction. "Sounds like" is word overlap with that
        driver's real phrasings and its events; volume is the similar past mailings' measured excess above
        that driver's own baseline, scaled by a readability score of the draft (vague letters cost more).</p>
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
      The archive's similar past mailings each drove <b>${p.low.toLocaleString()}-${p.high.toLocaleString()}</b>
      contacts above that cause's own baseline, and this wording predicts
      <b>${p.low.toLocaleString()}-${p.high.toLocaleString()}</b> per mailing
      (mid <b>${p.mid.toLocaleString()}</b>).
      The centre already answered this letter's questions <b>${q.count.toLocaleString()}</b> times.</p>
    <div class="m3-stats">
      <div class="stat"><b>${p.mid.toLocaleString()}</b><span class="muted">predicted contacts per mailing</span></div>
      <div class="stat"><b>${r.questionsBefore} → ${r.questionsAfter}</b><span class="muted">expected questions, draft vs. rewrite</span></div>
      <div class="stat"><b>-${(r.reductionPct * 100).toFixed(0)}%</b><span class="muted">predicted volume after the rewrite</span></div>
    </div>
    <h3 class="muted">Clarity of this draft</h3>
    <p>${data.clarity.issues.length ? data.clarity.issues.join(" · ") : "No clarity issues found."}</p>
    ${q.sample.length ? `
    <h3 class="muted">What readers actually asked about this notice</h3>
    <ul class="m3-letterlab-questions">
      ${q.sample.map((s) => `<li>"${s.text}" <span class="muted">— ${s.channel}, ${s.at.slice(0, 10)}</span></li>`).join("")}
    </ul>` : ""}
    <h3 class="muted">The suggested rewrite</h3>
    <pre class="m3-letterlab-rewrite">${r.text}</pre>
    <p class="m3-headline">After the rewrite: clarity <b>${data.clarity.score.toFixed(2)} →
      ${r.clarityScore.toFixed(2)}</b>, predicted volume <b>${r.volumeBefore.toLocaleString()} →
      ${r.volumeAfter.toLocaleString()}</b> per mailing, expected questions <b>${r.questionsBefore} →
      ${r.questionsAfter}</b>.</p>
    ${p.perMailing.length ? `
    <h3 class="muted">The past mailings this was measured against</h3>
    <table class="m3-table">
      <thead><tr><th>mailing</th><th class="num">date</th><th class="num">window contacts</th>
        <th class="num">excess over baseline</th></tr></thead>
      <tbody>${windowRows}</tbody>
    </table>` : ""}`;
}

// Mode 3, view 7: ask the archive — plain-English questions over pre-computed totals.
const ASK_SAMPLE = "Why did contacts about the 22-B letter spike in June 2025?";

export function renderAsk(el) {
  el.innerHTML = `
    <div class="m3-head">
      <h2>Ask the archive <span class="prov">plain code · totals over the archive</span></h2>
      <p class="muted">Ask in plain English — an issue, a state, a language, a month or year. The answer is
        plain code counting the archive's pre-computed totals: how many, how it compares with the equal
        period before, which calendar events overlap, and real messages from the archive cited as evidence.
        A question it can't scope gets an honest "I don't know", not a guess.</p>
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
  const gaps = (data.gaps || []).map((g, i) => `<div class="m3-kg-row">
      <div class="m3-kg-gap">
        <b class="m3-kg-rank">#${i + 1}</b> <b>${g.name}</b>
        <span class="muted">${g.count.toLocaleString()} contacts · ${g.sharePct}% of archive · ${g.hours}h · ${Math.round(g.resolveRate * 100)}% resolved</span>
      </div>
      <div class="m3-kg-faq"><span class="prov">FAQ draft</span><b>${g.faq.title}</b><p>${g.faq.body}</p></div>
      <div class="m3-kg-ivr"><span class="prov">IVR line</span> ${g.ivr}</div>
    </div>`).join("");
  const weak = (data.weakCoverage || []).map((w) => {
    const words = Object.entries(w.uncovered || {}).slice(0, 8).map(([word, phr]) =>
      `<li><b>${word}</b> <span class="muted">— “${phr[0]}”</span></li>`).join("");
    return `<div class="m3-kg-weak"><b>${w.articleTitle}</b> <span class="muted">claims to cover a topic but never says:</span>
      <ul>${words}</ul></div>`;
  }).join("");
  el.innerHTML = `
    <div class="m3-head">
      <h2>Knowledge gaps <span class="prov">plain code · kb_articles against the archive</span></h2>
      <p class="muted">What callers ask about that no knowledge-base article answers, ranked by archive
        volume, with a drafted FAQ entry and IVR line for each — plain code, from the driver's measured
        data. Under that: articles that claim a topic but whose body never uses the words callers actually
        use (weak coverage).</p>
    </div>
    <p class="m3-headline">${data.coveredDrivers} of ${data.drivers} topics covered · ${data.coveragePct}% of archive contacts on covered topics · ${data.articles} articles</p>
    ${gaps ? `<h3 class="muted">Unanswered questions, ranked</h3><div class="m3-kg-gaps">${gaps}</div>` : ""}
    <h3 class="muted">Weak coverage: claimed but not really explained</h3>
    <div class="m3-kg-weaks">${weak}</div>`;
}

export function renderWeakSignals(el, data) {
  const cards = (data.signals || []).map((s) => {
    const trig = (s.triggers || []).map((t) => `${t.name} (${t.date})`).join(", ");
    return `<div class="m3-ws-card">
      <div class="m3-ws-title"><b>${s.spikeEvent.name}</b> <span class="muted">${s.spikeEvent.date}</span></div>
      <p class="muted">The spike week did ${s.spikeWeekContacts.toLocaleString()} contacts. But the weeks before it
        already ran high: ${s.trickleWeeks} elevated weeks from ${s.trickleStart}, peaking at ${s.tricklePeak}
        (${s.multipleOfBaseline}x the ${s.driver} baseline of ${s.baselinePerWeek}/week).</p>
      <p><span class="prov">could have been caught</span> about <b>${s.monthsEarly} months early</b>
        (${s.weeksEarly} weeks) on a simple threshold alert — ${s.trickleTotal} early contacts vs
        ${s.spikeWeekContacts.toLocaleString()} in the spike week.</p>
      ${trig ? `<p class="muted">The trickle lines up with: ${trig}.</p>` : ""}
    </div>`;
  }).join("");
  el.innerHTML = `
    <div class="m3-head">
      <h2>Missed weak signals <span class="prov">${data.prov}</span></h2>
      <p class="muted">Spikes look sudden in the week they happen. This looks at the weeks <i>before</i>
        each spike and asks: how early could we have caught it? Baseline is each driver's own median
        week outside event windows, so a slow cause is judged against itself.</p>
    </div>
    <p class="m3-headline">${data.headline}</p>
    ${cards ? `<h3 class="muted">The trickle that preceded the spike</h3><div class="m3-ws-cards">${cards}</div>` : ""}`;
}

export function renderStaffingForecast(el, data) {
  const rows = (data.days || []).map((d) => `<tr>
      <td>${d.date}</td><td>${d.weekday}</td>
      <td>${d.baseline}</td><td>${d.eventExcess}</td>
      <td><b>${d.projectedContacts}</b></td><td>${d.projectedAgentHours}h</td>
    </tr>`).join("");
  const cards = (data.events || []).map((e) => `<div class="m3-sf-card">
      <div class="m3-sf-title"><b>${e.name}</b> <span class="muted">${e.date} · ${e.type}</span></div>
      <p class="muted">Still active in the window: <b>${e.remainingDays} day${e.remainingDays === 1 ? "" : "s"} left</b>.
        Projected to add <b>${e.projectedExcessContacts} more ${e.driver} calls</b>
        (~${e.projectedExcessAgentHours} agent-hours) on top of the baseline.</p>
    </div>`).join("");
  el.innerHTML = `
    <div class="m3-head">
      <h2>Staffing forecast <span class="prov">${data.prov}</span></h2>
      <p class="muted">The next ${data.horizonDays} days, projected from the archive's trailing
        90-weekday average (${data.weekdayBaseline} contacts a weekday) plus the events calendar's own
        decay curve, with the agent-hours each day needs at the archive's measured handling times.</p>
    </div>
    <p class="m3-headline">${data.headline}</p>
    ${cards ? `<h3 class="muted">Calendar events in the window</h3><div class="m3-sf-cards">${cards}</div>` : ""}
    <h3 class="muted">Day by day</h3>
    <table class="m3-sf-table">
      <thead><tr><th>date</th><th>day</th><th>baseline</th><th>event excess</th><th>projected contacts</th><th>agent-hours</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="muted">Totals: <b>${data.totalProjectedContacts} contacts</b> and
      <b>${data.totalProjectedAgentHours} agent-hours</b> across the window. Weekends project at the
      calendar alone — the archive is weekdays, so there is no weekday baseline to add.</p>`;
}
