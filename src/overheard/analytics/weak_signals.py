"""View 9 of Mode 3: missed weak signals.

For every call driver this asks the question the archive can only answer: when
could we have caught this before it spiked? For each major spike event it
looks at the weeks leading up to it for that driver's own weekly contact
series. The baseline is the driver's median week in the 24 weeks before the
scan window (outside event windows the generator knows about), so a slow cause
is judged against itself, not against the centre. A run of several weeks above
the baseline before a spike is a weak signal: it reports when it started, how
much above baseline it ran, how early an alert would have fired, and how small
the trickle was next to the spike it preceded. No LLM.
"""

from datetime import date, timedelta

from overheard.data.events import EVENTS

SPIKE_MIN_WEEKLY = 20     # a driver-week this big (baseline x MULTIPLE) is a spike
SCAN_WEEKS = 24           # how many weeks before a spike to look for a trickle
TRICKLE_MULTIPLE = 2.5    # a week is "elevated" at baseline x this many
TRICKLE_RUN = 3           # elevated weeks (consecutive or not) that make a signal


def _week_dates(day: date) -> tuple[date, date]:
    """The Mon..Mon week boundary containing `day`."""
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=7)


def _week_counts(con, driver: str, start: date, end: date) -> dict[date, int]:
    """Contacts per calendar week (Monday key) for one driver in [start, end)."""
    out: dict[date, int] = {}
    for row in con.execute(
            "SELECT date(at), COUNT(*) FROM contacts WHERE root_cause = ? AND at >= ? AND at < ? GROUP BY date(at)",
            (driver, start.isoformat(), end.isoformat())):
        day = date.fromisoformat(row[0])
        key = day - timedelta(days=day.weekday())
        out[key] = out.get(key, 0) + row[1]
    return out


def _event_windows() -> list[tuple[str, date, date, str, str]]:
    """(id, start, end, name, driver) for every calendar event."""
    return [(e[0], date.fromisoformat(e[1]),
             date.fromisoformat(e[1]) + timedelta(days=e[7]),
             e[3], e[5]) for e in EVENTS]


def _in_event_windows(day: date, windows: list[tuple[str, date, date, str, str]]) -> bool:
    return any(ws <= day < we for _, ws, we, _, _ in windows)


def _median(values: list[int]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def weak_signals(con) -> list[dict]:
    """One card per (driver, spike event) where the weeks before the spike ran
    elevated against the driver's own baseline: the spike, the trickle that
    preceded it (start, weeks, level vs baseline), and how early an alert on
    that level would have fired. Sorted earliest-prediction first."""
    windows = _event_windows()
    cards: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for ev_id, ev_start, _ev_end, ev_name, driver in windows:
        if (driver, ev_id) in seen:
            continue
        seen.add((driver, ev_id))
        # is this event a spike for its driver?
        w_start, w_end = _week_dates(ev_start)
        spike_count = sum(_week_counts(con, driver, w_start, w_end).values())
        if spike_count < SPIKE_MIN_WEEKLY:
            continue
        # baseline: the driver's median week across the 24 weeks before the
        # scan window, ignoring weeks inside any event window
        scan_start = w_start - timedelta(weeks=SCAN_WEEKS)
        baseline_floor = scan_start - timedelta(weeks=SCAN_WEEKS)
        pre = _week_counts(con, driver, baseline_floor, scan_start)
        full_weeks = [c for wk, c in pre.items()
                      if wk + timedelta(days=7) <= scan_start
                      and not _in_event_windows(wk, windows)]
        baseline = _median(full_weeks)
        if baseline < 1.0:
            continue
        # the scan window before the spike
        scan = _week_counts(con, driver, scan_start, w_start)
        elevated = [(wk, c) for wk, c in sorted(scan.items())
                    if c >= TRICKLE_MULTIPLE * baseline and c < SPIKE_MIN_WEEKLY]
        if len(elevated) < TRICKLE_RUN:
            continue
        trickle_start = elevated[0][0]
        trickle_end = elevated[-1][0] + timedelta(days=6)
        trickle_total = sum(c for _, c in elevated)
        weeks_early = (w_start - trickle_start).days / 7.0
        # what on the calendar lines up with the trickle?
        triggers = [{"id": t_id, "date": t_start.isoformat(), "name": t_name}
                    for t_id, t_start, t_end, t_name, t_driver in windows
                    if t_driver == driver and t_start >= trickle_start - timedelta(days=7)
                    and t_start <= trickle_end]
        cards.append({
            "driver": driver,
            "spikeEvent": {"id": ev_id, "date": ev_start.isoformat(), "name": ev_name},
            "spikeWeekContacts": spike_count,
            "baselinePerWeek": round(baseline, 1),
            "trickleStart": trickle_start.isoformat(),
            "trickleWeeks": len(elevated),
            "trickleTotal": trickle_total,
            "tricklePeak": max(c for _, c in elevated),
            "multipleOfBaseline": round(max(c for _, c in elevated) / baseline, 1),
            "weeksEarly": round(weeks_early, 1),
            "monthsEarly": round(weeks_early / 4.345, 1),
            "triggers": triggers,
        })
    cards.sort(key=lambda c: -c["weeksEarly"])
    return cards
