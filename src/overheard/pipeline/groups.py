"""Mode 2 · reasoning across messages: similarity clusters, spike detection, repeat-caller
links and missing-info recovery.

Pure functions over the day's messages (plus the mode-1 bundles, which carry the
translation, the summary and the extracted facts), so the mode-2 queue, the
incident banner, the context pane and the tests all run the same code. No
network, no LLM here — the incident *card* (naming the cluster, drafting
actions) is the LLM's job and lives in pipeline/incidents.py.
"""

import math
import re
from datetime import datetime, timedelta

from overheard.data.models import Voicemail

#: the words that carry no topic
STOP = set(
    "the a an and or but so my me i we you your yours had has was were is are am "
    "to of on for at in it its this that those with about just want please could would like "
    "call back number case one two three four five six seven eight nine oh zero eleven twelve "
    "did do doesn didn't don't got get going right really think know".split()
)

_TOKEN = re.compile(r"[a-z][a-z'-]{2,}")
#: error codes and phone numbers callers actually say ("error four oh one two"
#: rendered as 4012, or "the E4012 page") carry as much topic as any word
_CODE = re.compile(r"\b[0-9]{3,}\b")



def _ordinal(n: int) -> str:
    """1 -> 1st, 2 -> 2nd, 3 -> 3rd, 11 -> 11th."""
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

def _tokens(text: str) -> list[str]:
    ts = [t for t in _TOKEN.findall(text.lower()) if t not in STOP and not t.isdigit()]
    return ts + [c.lower() for c in _CODE.findall(text)]


def _text(vm: Voicemail, bundles: dict[str, dict] | None) -> str:
    """What to compare: the English the team reads (the translation, if any), the
    summary, the extracted topic and the raw script — together they make a
    message as long and as varied as the ones the AI actually processed."""
    b = (bundles or {}).get(vm.id, {})
    parts: list[str] = []
    tr = (b.get("translation") or {}).get("data") or {}
    if tr.get("translated"):
        parts.append(tr["text"])
    sm = (b.get("summary") or {}).get("data") or {}
    if sm.get("summary"):
        parts.append(sm["summary"])
    ext = (b.get("extraction") or {}).get("data") or {}
    for k in ("program", "requestedAction"):
        val = (ext.get(k) or {}).get("value")
        if val:
            parts.append(str(val))
    parts.append(vm.script)
    return " ".join(parts)


def _tfidf(docs: list[list[str]]):
    n = len(docs)
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    vecs, norms = [], []
    for d in docs:
        tf: dict[str, int] = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        v = {t: (1 + math.log(c)) * idf[t] for t, c in tf.items()}
        vecs.append(v)
        norms.append(math.sqrt(sum(x * x for x in v.values())) or 1.0)
    return vecs, norms


def _cos(v1: dict, n1: float, v2: dict, n2: float) -> float:
    if not v1 or not v2:
        return 0.0
    if len(v1) > len(v2):
        v1, n1, v2, n2 = v2, n2, v1, n1
    return sum(w * v2.get(t, 0.0) for t, w in v1.items()) / (n1 * n2)


def group_day(messages: list[Voicemail], bundles: dict[str, dict] | None = None,
              threshold: float = 0.18) -> dict[str, list[str]]:
    """TF-IDF similarity clusters, single linkage in arrival order: a message joins
    a cluster when it is close to *any* member of it, otherwise it starts a new
    one. A live incident's callers each describe the same outage in their own
    words, and greedy centroid-merging falls behind as the cluster grows —
    linking to the members keeps them all together. Returns `{cluster id:
    [message ids]}`; a message with no match gets its own cluster."""
    vecs, norms = _tfidf([_tokens(_text(v, bundles)) for v in messages])
    parent = list(range(len(messages)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(len(messages)):
        for j in range(i + 1, len(messages)):
            if find(i) != find(j) and _cos(vecs[i], norms[i], vecs[j], norms[j]) >= threshold:
                parent[find(j)] = find(i)
    clusters: dict[str, list[str]] = {}
    for i, v in enumerate(messages):  # arrival order keeps cluster ids stable
        clusters.setdefault(find(i), []).append(v.id)
    return clusters


def _t(at: str) -> datetime:
    return datetime.fromisoformat(at)


def spike_in_cluster(member_msgs: list[Voicemail], window_min: int = 30, count: int = 8) -> dict | None:
    """The spike test, on one cluster's messages in arrival order: the moment a rolling
    `window_min` first holds `count` of them is the alert. Returns the incident's facts —
    `firstAt`, `alertAt`, `leadMin` (first → alert), `count` at the alert — or `None`."""
    msgs = sorted(member_msgs, key=lambda v: v.receivedAt)
    times = [_t(v.receivedAt) for v in msgs]
    limit = timedelta(minutes=window_min)
    first = 0
    for i, t in enumerate(times):
        while t - times[first] > limit:
            first += 1
        if i - first + 1 >= count:
            return {"firstAt": msgs[0].receivedAt, "alertAt": msgs[i].receivedAt,
                    "leadMin": int((t - times[0]).total_seconds() // 60),
                    "count": i - first + 1, "size": len(msgs)}
    return None


def link_repeats(messages: list[Voicemail], bundles: dict[str, dict]) -> dict[str, dict]:
    """Repeat-caller linking: same case number (what the AI heard) or same caller ID,
    two or more messages, collapse to the earliest one. The escalation note uses each
    contact's urgency so "3rd contact, rising frustration" is computed, not written in."""
    by_key: dict[tuple[str, str], list[Voicemail]] = {}
    for v in messages:
        data = bundles.get(v.id, {}).get("extraction", {}).get("data")
        case_id = (data or {}).get("caseId", {}).get("value") or ""
        by_key.setdefault((case_id, v.callerId), []).append(v)
    out: dict[str, dict] = {}
    for key, group in by_key.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda v: v.receivedAt)
        leader = group[0]
        urg = [int(bundles.get(v.id, {}).get("intent_urgency", {}).get("data", {}).get("urgency", 2)) for v in group]
        trend = "rising frustration" if urg[-1] > urg[0] else "same issue, still open"
        span_h = max(1, int((_t(group[-1].receivedAt) - _t(group[0].receivedAt)).total_seconds() // 3600))
        out[leader.id] = {"members": [v.id for v in group], "caseId": key[0] or None,
                          "note": f"{_ordinal(len(group))} contact in ~{span_h}h, {trend}",
                          "urgency": urg, "callers": group[0].truth.callerName}
    return out


def missing_info(messages: list[Voicemail], bundles: dict[str, dict], backend) -> dict[str, dict]:
    """Missing-info recovery: the caller didn't give a case number (the AI says so), so
    infer the case from the caller ID. If the case system knows the phone, the case is
    recovered and no one has to ask; if it doesn't, the message needs an automatic
    request for the missing detail before an agent touches it."""
    out: dict[str, dict] = {}
    for v in messages:
        data = bundles.get(v.id, {}).get("extraction", {}).get("data")
        said = (data or {}).get("caseNumberSaid", True)
        if said:
            continue
        cases = backend.by_phone(v.callerId)
        if cases:
            out[v.id] = {"needed": "case number", "recovered": cases[0].id,
                         "how": "caller ID matched the case system", "status": "recovered"}
        else:
            out[v.id] = {"needed": "case number", "recovered": None,
                         "how": "caller ID is not in the case system", "status": "request sent"}
    return out
