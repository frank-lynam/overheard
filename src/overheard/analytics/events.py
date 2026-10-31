"""Event impact over the archive: which moments (mailings, releases, policy changes) actually moved the call
volume, measured as contacts and handler-hours above the driver's own baseline.

The calendar's drivers and windows come from the EVENTS list (the same one that drives the generator); the
baseline is each cause's weekday contact rate in the 90 weekdays before the event, so a slow cause (tax-form-1099)
is not mistaken for a fast one just because it's on the list. Everything is plain SQL + math; no LLM.
"""

from datetime import date, timedelta

from overheard.data.events import EVENTS

BASELINE_DAYS = 90  # weekday-days before the event whose daily rate we call "business as usual"


def _weekdays(start: date, end: date) -> int:
    n, day = 0, start
    while day < end:
        if day.weekday() < 5:
            n += 1
        day += timedelta(days=1)
    return n


def _window_counts(con, driver: str, start: date, end: date) -> tuple[int, float]:
    """Weekday contacts for one root cause in [start, end): (count, handle-hours)."""
    row = con.execute(
        """SELECT COUNT(*), COALESCE(SUM(handle_min), 0)
           FROM contacts WHERE root_cause = ? AND at >= ? AND at < ?""",
        (driver, start.isoformat(), end.isoformat())).fetchone()
    return row[0], row[1] / 60.0


def _baseline_rate(con, driver: str, before: date) -> float:
    """Mean weekday contacts/day for the driver over the 90 weekdays before `before`."""
    end = before - timedelta(days=1)
    day, count = end, 0
    while count < BASELINE_DAYS:
        if day.weekday() < 5:
            count += 1
        day -= timedelta(days=1)
    total, _ = _window_counts(con, driver, day, end)
    return total / count


def event_impact(con) -> list[dict]:
    """Per-event impact, sorted by excess contacts descending: name/type/date, window contacts & hours,
    the baseline daily rate it was measured against, expected contacts (baseline x weekdays), excess
    contacts and excess hours (excess at the window's observed handle time), and the event's share of
    the archive's total excess hours."""
    rows = []
    for e in EVENTS:
        eid, dstr, etype, name, _desc, driver, _peak, days = e
        start = date.fromisoformat(dstr)
        end = start + timedelta(days=days)
        count, hours = _window_counts(con, driver, start, end)
        rate = _baseline_rate(con, driver, start)
        wd = _weekdays(start, end)
        exp_count = rate * wd
        excess = max(0, count - exp_count)
        excess_hours = max(0.0, (excess * (hours / count)) if count else 0.0)
        rows.append({
            "id": eid, "date": dstr, "type": etype, "name": name, "driver": driver,
            "count": count, "hours": round(hours, 1), "baselinePerDay": round(rate, 2),
            "expected": round(exp_count), "excess": round(excess), "excessHours": round(excess_hours, 1),
        })
    total_excess_hours = sum(r["excessHours"] for r in rows)
    for r in rows:
        r["excessShare"] = round(100.0 * r["excessHours"] / total_excess_hours, 1) if total_excess_hours else 0.0
    rows.sort(key=lambda r: (-r["excess"], -r["excessHours"], r["date"]))
    return rows
