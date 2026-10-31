"""Mode 3, view 10: event-driven staffing forecast.

Projects the next 14 days of call volume and the agent hours it will take,
from the two things this desk actually measures: the archive's recent weekday
average (the baseline, ~contacts/day) and the events calendar's own decay
curve (the same peak*exp(-3*age/days)*VOLUME the generator uses). Weekend days
have no baseline — the archive is weekdays only — so they project at whatever
the calendar adds, which is usually nothing. No LLM.
"""

import math
from datetime import date, timedelta

from overheard.data.events import EVENTS
from overheard.data.generator import VOLUME

FORECAST_DAYS = 14
BASELINE_WEEKDAYS = 90


def _today(con) -> date:
    row = con.execute("SELECT value FROM meta WHERE key='today'").fetchone()
    return date.fromisoformat(row[0])


def _weekday_baseline(con, today: date) -> float:
    """Mean contacts/day over the archive's trailing 90 weekdays before today."""
    counts: dict[str, int] = {}
    for d, c in con.execute(
            "SELECT date(at), COUNT(*) FROM contacts WHERE date(at) < ? GROUP BY date(at)",
            (today.isoformat(),)):
        if date.fromisoformat(d).weekday() < 5:
            counts[d] = c
    last90 = sorted(counts)[-BASELINE_WEEKDAYS:]
    if not last90:
        return 0.0
    return sum(counts[d] for d in last90) / len(last90)


def _driver_handle_min(con, driver: str) -> float:
    """Mean handling minutes/contact for one driver, from the archive."""
    row = con.execute(
        "SELECT AVG(handle_min) FROM contacts WHERE root_cause = ?", (driver,)).fetchone()
    return float(row[0] or 0.0)


def _global_handle_min(con) -> float:
    row = con.execute("SELECT AVG(handle_min) FROM contacts").fetchone()
    return float(row[0] or 0.0)


def staffing_forecast(con) -> dict:
    today = _today(con)
    baseline = _weekday_baseline(con, today)
    h_global = _global_handle_min(con)

    active = []  # events still adding volume in the window
    for _id, edate, etype, ename, _desc, driver, peak, days in EVENTS:
        start = date.fromisoformat(edate)
        end = start + timedelta(days=days)
        if start < today + timedelta(days=FORECAST_DAYS) and end > today:
            active.append((start, driver, float(peak), int(days), ename, etype, edate))

    day_rows = []
    for i in range(FORECAST_DAYS):
        day = today + timedelta(days=i)
        excess = 0.0
        excess_h = 0.0
        for start, driver, peak, days, _ename, _etype, _edate in active:
            age = (day - start).days
            if 0 <= age < days:
                e = peak * math.exp(-3.0 * age / days) * VOLUME
                excess += e
                excess_h += e * _driver_handle_min(con, driver)
        base = baseline if day.weekday() < 5 else 0.0
        day_rows.append({
            "date": day.isoformat(),
            "weekday": day.strftime("%A"),
            "baseline": round(base, 1),
            "eventExcess": round(excess, 1),
            "projectedContacts": round(base + excess, 1),
            "projectedAgentHours": round((base * h_global + excess_h) / 60.0, 1),
        })

    cards = []
    for start, driver, _peak, days, ename, etype, edate in active:
        end = start + timedelta(days=days)
        remaining = [
            d for d in day_rows if start <= date.fromisoformat(d["date"]) < end]
        excess = sum(d["eventExcess"] for d in day_rows
                     if start <= date.fromisoformat(d["date"]) < end)
        cards.append({
            "name": ename,
            "type": etype,
            "driver": driver,
            "date": edate,
            "remainingDays": len(remaining),
            "projectedExcessContacts": round(excess, 1),
            "projectedExcessAgentHours": round(
                sum(d["projectedAgentHours"] for d in remaining) -
                sum(d["baseline"] for d in remaining) * h_global / 60.0, 1),
        })

    return {
        "horizonStart": today.isoformat(),
        "horizonDays": FORECAST_DAYS,
        "weekdayBaseline": round(baseline, 1),
        "days": day_rows,
        "events": cards,
        "totalProjectedContacts": round(sum(d["projectedContacts"] for d in day_rows), 1),
        "totalProjectedAgentHours": round(sum(d["projectedAgentHours"] for d in day_rows), 1),
    }
