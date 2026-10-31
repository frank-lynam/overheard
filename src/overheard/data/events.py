"""The events calendar that drives the archive's volume: each event adds calls about one driver, peaking at its
start and fading over `days`. The planted signals Mode 3 should recover are marked."""

# (id, date, type, name, description, driver it drives, extra contacts per day at the start, days it lasts)
EVENTS = [
    ("ev-portal-40", "2023-09-12", "release", "Portal release 4.0", "New sign-in page", "portal-sign-in-failure", 3.0, 5),
    ("ev-cola-24", "2024-01-08", "mailing", "Cost-of-living letters 2024", "Annual adjustment notices", "cola-letter", 4.0, 20),
    ("ev-income-rule", "2024-01-22", "policy", "Monthly income reporting rule", "Income must be reported monthly", "income-reporting-question", 3.0, 60),
    ("ev-portal-41", "2024-04-16", "release", "Portal release 4.1", "Document upload redesign", "portal-navigation", 3.0, 6),
    # PLANTED: the confusing letter. Mailed twice a year; each mailing drives a large, slow-fading excess.
    ("ev-22b-1", "2024-06-03", "mailing", "Form 22-B re-verification letter (1st mailing)", "Re-verify address and income within 30 days", "form-22b-confusion", 9.0, 50),
    ("ev-1099-quiet", "2024-10-01", "policy", "Tax form vendor change", "1099s produced by a new vendor", "tax-form-1099", 0.25, 110),
    ("ev-22b-2", "2024-12-02", "mailing", "Form 22-B re-verification letter (2nd mailing)", "Re-verify address and income within 30 days", "form-22b-confusion", 9.0, 50),
    ("ev-cola-25", "2025-01-06", "mailing", "Cost-of-living letters 2025", "Annual adjustment notices", "cola-letter", 4.0, 20),
    # PLANTED: the weak signal that grew: a trickle of missing-1099 calls from October, then a spike in late January.
    ("ev-1099-spike", "2025-01-27", "mailing", "1099 tax forms mailed", "Annual tax forms", "tax-form-1099", 8.0, 20),
    # PLANTED: the big release that broke sign-in.
    ("ev-portal-42", "2025-05-06", "release", "Portal release 4.2", "Two-step verification for sign-in", "portal-sign-in-failure", 30.0, 9),
    ("ev-22b-3", "2025-06-02", "mailing", "Form 22-B re-verification letter (3rd mailing)", "Re-verify address and income within 30 days", "form-22b-confusion", 9.0, 50),
    ("ev-22b-4", "2025-12-01", "mailing", "Form 22-B re-verification letter (4th mailing)", "Re-verify address and income within 30 days", "form-22b-confusion", 9.0, 50),
    ("ev-cola-26", "2026-01-05", "mailing", "Cost-of-living letters 2026", "Annual adjustment notices", "cola-letter", 4.0, 20),
    ("ev-payday-12", "2026-02-27", "payment-shift", "Payment date moves to the 12th", "March payments move from the 3rd to the 12th", "payment-date-shift", 6.0, 14),
]
