from datetime import date

import pytest

from app.domain import Status
from app.repository import ApplicationRepository
from app.schemas import ApplicationCreate, CompanyStats
from app.services.dashboard import (
    CALENDAR_WEEKS,
    Period,
    build_calendar,
    build_company_breakdown,
    build_cumulative,
    build_dashboard,
    build_funnel,
    build_series,
    daily_specs,
    month_start,
    monthly_specs,
    weekly_specs,
    window_start,
)

from .conftest import FIXED_NOW

TODAY = date(2026, 10, 4)  # Sunday


@pytest.mark.parametrize(
    ("period", "first_activity", "expected"),
    [
        (Period.LAST_14_DAYS, date(2026, 9, 20), date(2026, 9, 21)),
        (Period.LAST_30_DAYS, date(2026, 9, 20), date(2026, 9, 5)),
        (Period.LAST_30_DAYS, None, date(2026, 9, 5)),
        (Period.ALL_TIME, date(2026, 8, 1), date(2026, 8, 1)),
        (Period.ALL_TIME, date(2026, 10, 3), date(2026, 9, 28)),
        (Period.ALL_TIME, None, date(2026, 9, 28)),
    ],
)
def test_window_start(period: Period, first_activity: date | None, expected: date) -> None:
    assert window_start(TODAY, period, first_activity) == expected


def test_month_start_crosses_year_boundary() -> None:
    assert month_start(date(2026, 1, 15), months_back=1) == date(2025, 12, 1)
    assert month_start(date(2026, 12, 15), months_back=-1) == date(2027, 1, 1)


def test_bucket_specs_cover_window() -> None:
    start = date(2026, 9, 20)

    daily = daily_specs(date(2026, 9, 21), TODAY)
    weekly = weekly_specs(start, TODAY)
    monthly = monthly_specs(start, TODAY)

    assert len(daily) == 14
    assert [d.label for d in daily[:3]] == ["21 Eyl", "22", "23"]
    assert daily[-1].current
    assert [w.start for w in weekly] == [date(2026, 9, 20), date(2026, 9, 21), date(2026, 9, 28)]
    assert weekly[0].title == "20 Eyl – 20 Eyl"
    assert [m.label for m in monthly] == ["Eyl 2026", "Eki 2026"]
    assert monthly[0].start == start
    assert monthly[-1].end == date(2026, 10, 5)
    assert monthly[-1].current


def test_daily_specs_only_label_mondays_when_dense() -> None:
    specs = daily_specs(date(2026, 7, 1), TODAY)

    labelled = [s.start for s in specs if s.label]
    assert labelled
    assert all(day.weekday() == 0 for day in labelled)


def test_build_series_scales_to_peak() -> None:
    specs = weekly_specs(date(2026, 9, 21), TODAY)
    applied = {date(2026, 9, 22): 4, date(2026, 9, 29): 1, date(2026, 10, 4): 1}
    rejected = {date(2026, 10, 1): 1}

    series = build_series(specs, applied, rejected)

    assert [(b.applied, b.rejected) for b in series.buckets] == [(4, 0), (2, 1)]
    assert [b.applied_pct for b in series.buckets] == [100, 50]
    assert series.applied_total == 6
    assert series.applied_average == 3.0


def test_cumulative_includes_activity_before_window() -> None:
    start = date(2026, 10, 1)
    applied = {date(2026, 9, 1): 3, date(2026, 10, 2): 1}

    cumulative = build_cumulative(start, TODAY, applied, {})

    assert cumulative.applied_total == 4
    assert cumulative.applied_points.split()[0] == "0.00,25.00"
    assert cumulative.applied_points.split()[-1] == "100.00,0.00"


def test_calendar_ends_with_current_week_and_marks_window() -> None:
    start = date(2026, 10, 1)  # Thursday
    weeks = build_calendar(start, TODAY, {date(2026, 10, 2): 2, TODAY: 1}, {TODAY: 1})

    assert len(weeks) == CALENDAR_WEEKS
    assert weeks[0].label == "Ağu"
    assert [w.label for w in weeks[1:]] == ["Eyl", "", "", "", "Eki"]
    assert not any(day.inside for week in weeks[:-1] for day in week.days)

    current = weeks[-1].days
    assert [d.day for d in current] == [28, 29, 30, 1, 2, 3, 4]
    assert [d.inside for d in current] == [False, False, False, True, True, True, True]
    assert current[4].level == 4
    assert current[6].level == 2
    assert current[6].rejected == 1
    assert current[6].today
    assert not any(d.today for d in current[:6])


def test_company_breakdown_keeps_repeated_companies() -> None:
    stats = [
        CompanyStats(company="BMW AG", total=5, rejected=1, waiting=4),
        CompanyStats(company="TRUMPF", total=2, rejected=0, waiting=2),
        CompanyStats(company="Acme", total=1, rejected=0, waiting=1),
        CompanyStats(company="Globex", total=1, rejected=1, waiting=0),
    ]

    breakdown = build_company_breakdown(stats)

    assert [(r.stats.company, r.pct, r.frequent) for r in breakdown.repeated] == [
        ("BMW AG", 100, True),
        ("TRUMPF", 40, False),
    ]
    assert breakdown.single_application_companies == 2


def test_funnel_counts_later_stages_as_passed() -> None:
    funnel = build_funnel(
        {Status.APPLIED: 5, Status.SCREENING: 2, Status.INTERVIEW: 2, Status.REJECTED: 1}
    )

    assert [(s.status, s.count) for s in funnel] == [
        (Status.APPLIED, 10),
        (Status.SCREENING, 4),
        (Status.INTERVIEW, 2),
        (Status.OFFER, 0),
    ]
    assert [s.step_pct for s in funnel] == [None, 40, 50, 0]


@pytest.mark.parametrize(
    ("period", "window_start_day", "applied", "rejection_rate"),
    [
        (Period.LAST_14_DAYS, date(2026, 9, 21), 2, 50),
        (Period.LAST_30_DAYS, date(2026, 9, 5), 3, 33),
        (Period.ALL_TIME, date(2026, 9, 20), 3, 33),
    ],
)
def test_build_dashboard_scopes_to_period(
    repo: ApplicationRepository,
    period: Period,
    window_start_day: date,
    applied: int,
    rejection_rate: int,
) -> None:
    for applied_at, status in [
        ("2026-09-20", "applied"),
        ("2026-09-21", "rejected"),
        ("2026-10-04", "interview"),
    ]:
        repo.create(
            ApplicationCreate(
                company="Acme", title="Engineer", applied_at=applied_at, status=status
            )
        )

    dashboard = build_dashboard(repo, period, FIXED_NOW.date())

    assert dashboard.window == (window_start_day, TODAY)
    assert dashboard.kpis.today == 1
    assert dashboard.kpis.period_applied == applied
    assert dashboard.kpis.period_rejected == 1
    assert dashboard.kpis.rejection_rate == rejection_rate
    for series in (dashboard.daily, dashboard.weekly, dashboard.monthly):
        assert series.applied_total == applied
        assert series.rejected_total == 1
    assert dashboard.funnel[0].count == applied
    assert dashboard.awaiting_response == []
