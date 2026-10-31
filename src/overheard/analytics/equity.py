"""View 5 of Mode 3: equity — is service the same for every caller?

Groups the archive's contacts by language and by channel and compares how long
each group waits (mean/median handle time), how often the call actually gets
resolved, and how long resolution takes. Plain code over `contacts`; no LLM.
The generator plants `SLOW_LANG = "vi"`: Vietnamese callers wait ~1.35x longer
and their issue resolves less often and ~2x slower. This view surfaces that gap
as the slowest-vs-fastest ratio so it can't hide in the averages.
"""

import sqlite3
import statistics


def _group_rows(con: sqlite3.Connection, key: str) -> dict[str, dict]:
    """Per group: {contacts, waits:[...], resolved, days:[...]}."""
    out: dict[str, dict] = {}
    for k, handle, resolved, days in con.execute(f"SELECT {key}, handle_min, resolved, days_to_resolve FROM contacts"):
        row = out.setdefault(k, {"contacts": 0, "waits": [], "resolved": 0, "days": []})
        row["contacts"] += 1
        row["waits"].append(handle)
        if resolved:
            row["resolved"] += 1
            if days is not None:
                row["days"].append(days)
    return out


def _summary(sections: dict[str, dict]) -> list[dict]:
    rows = []
    for name, row in sections.items():
        waits = row["waits"]
        rows.append(
            {
                "name": name,
                "contacts": row["contacts"],
                "avgWaitMin": round(statistics.mean(waits), 2),
                "medianWaitMin": round(statistics.median(waits), 2),
                "resolveRate": round(row["resolved"] / row["contacts"], 4),
                "avgDaysToResolve": round(statistics.mean(row["days"]), 1) if row["days"] else None,
            }
        )
    return sorted(rows, key=lambda r: -r["avgWaitMin"])


def _worst(rows: list[dict]) -> dict | None:
    """The slowest group's ratio vs the fastest, plus the reverse resolution gap."""
    waits = {r["name"]: r["avgWaitMin"] for r in rows if r["contacts"] >= 10}
    if len(waits) < 2:
        return None
    slow_name, slow = max(waits.items(), key=lambda kv: kv[1])
    fast_name, fast = min(waits.items(), key=lambda kv: kv[1])
    by_name = {r["name"]: r for r in rows}
    return {
        "slow": slow_name,
        "fast": fast_name,
        "slowWaitMin": slow,
        "fastWaitMin": fast,
        "waitRatio": round(slow / fast, 2) if fast else None,
        "slowResolveRate": by_name[slow_name]["resolveRate"],
        "fastResolveRate": by_name[fast_name]["resolveRate"],
        "slowDays": by_name[slow_name]["avgDaysToResolve"],
        "fastDays": by_name[fast_name]["avgDaysToResolve"],
    }


def equity_report(con: sqlite3.Connection) -> dict:
    """Wait, resolution and time-to-resolution by language and by channel, and the gaps."""
    langs = _summary(_group_rows(con, "lang"))
    chans = _summary(_group_rows(con, "channel"))
    return {
        "totalContacts": con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
        "languages": langs,
        "channels": chans,
        "worstLanguage": _worst(langs),
        "worstChannel": _worst(chans),
    }
