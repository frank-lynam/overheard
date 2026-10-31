"""View 1 of Mode 3: cost by root cause — the Pareto.

Every archived contact already carries its root-cause label and how long the agent
spent on it, so the cost model is plain arithmetic: SUM(handle_min) per cause,
times a configurable fully-loaded labor rate. No scaling: the archive *is* the
whole centre, so the headline numbers are whatever it actually produces.
"""

import sqlite3


def root_causes(con: sqlite3.Connection, labor_rate: float = 55.0) -> dict:
    """The archive's contacts by root cause: counts, hours, dollars, resolution.

    `labor_rate` is the fully-loaded dollars per agent-hour (config, OVERHEARD_LABOR_RATE).
    Causes are ranked by cost; `share` is the share of the centre's total agent-hours.
    """
    rows = con.execute(
        "SELECT root_cause, COUNT(*), SUM(handle_min), SUM(CASE WHEN resolved THEN 1 ELSE 0 END), "
        "MIN(at), MAX(at) FROM contacts GROUP BY root_cause"
    ).fetchall()
    total_hours = con.execute("SELECT SUM(handle_min) / 60.0 FROM contacts").fetchone()[0]
    causes = []
    for cause, n, minutes, resolved, first, last in rows:
        hours = (minutes or 0) / 60.0
        causes.append(
            {
                "cause": cause,
                "contacts": n,
                "hours": round(hours, 1),
                "share": round(hours / total_hours, 4) if total_hours else 0.0,
                "annualCostUsd": round(hours * 3 * labor_rate),  # the archive spans 3 years
                "resolutionRate": round(resolved / n, 3),
                "first": first,
                "last": last,
            }
        )
    causes.sort(key=lambda c: c["hours"], reverse=True)
    # the cumulative Pareto share: where does the top fraction of the cost sit
    for i, c in enumerate(causes):
        c["cumShare"] = round(sum(x["share"] for x in causes[: i + 1]), 4)
    top_n = next((i + 1 for i, c in enumerate(causes) if c["cumShare"] >= 0.80), len(causes))
    span_years = 3.0
    return {
        "laborRate": labor_rate,
        "totalContacts": sum(c["contacts"] for c in causes),
        "totalHours": round(total_hours, 1),
        "annualHours": round(total_hours / span_years, 1),
        "annualCostUsd": round(total_hours / span_years * labor_rate),
        "top80Count": top_n,  # how many causes hold the top 80% of the cost
        "causes": causes,
    }
