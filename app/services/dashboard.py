"""Dashboard view model.

Data access is limited to `build_dashboard`; everything else is a pure function over
per-day counts so the bucketing logic can be tested without a database.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from app.domain import FREQUENT_COMPANY_THRESHOLD, FUNNEL_STAGES, Status
from app.repository import ApplicationRepository
from app.schemas import Application, CompanyStats

DayCounts = Mapping[date, int]
DateRange = tuple[date, date]

MIN_WINDOW_DAYS = 7
DENSE_DAILY_LIMIT = 31
CALENDAR_WEEKS = 6
STALE_AFTER_DAYS = 21
TR_MONTHS = ("Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")


class Period(StrEnum):
    LAST_14_DAYS = "14"
    LAST_30_DAYS = "30"
    ALL_TIME = "all"

    @property
    def days(self) -> int | None:
        return None if self is Period.ALL_TIME else int(self.value)

    @property
    def label(self) -> str:
        return "Tümü" if self is Period.ALL_TIME else f"{self.value} gün"


@dataclass(frozen=True, slots=True)
class BucketSpec:
    start: date
    end: date
    label: str
    title: str
    current: bool = False
    weekend: bool = False


@dataclass(frozen=True, slots=True)
class Bucket:
    spec: BucketSpec
    applied: int
    rejected: int
    applied_pct: int
    rejected_pct: int


@dataclass(frozen=True, slots=True)
class Series:
    buckets: list[Bucket]

    @property
    def applied_total(self) -> int:
        return sum(b.applied for b in self.buckets)

    @property
    def rejected_total(self) -> int:
        return sum(b.rejected for b in self.buckets)

    @property
    def applied_average(self) -> float:
        return round(self.applied_total / len(self.buckets), 1) if self.buckets else 0.0


@dataclass(frozen=True, slots=True)
class Cumulative:
    applied_points: str
    rejected_points: str
    applied_total: int
    rejected_total: int
    peak: int
    start_label: str
    end_label: str


@dataclass(frozen=True, slots=True)
class CalendarDay:
    day: int
    inside: bool
    today: bool
    level: int
    rejected: int
    title: str


@dataclass(frozen=True, slots=True)
class CalendarWeek:
    label: str
    days: list[CalendarDay]


@dataclass(frozen=True, slots=True)
class FunnelStage:
    status: Status
    count: int
    pct: int
    step_pct: int | None


@dataclass(frozen=True, slots=True)
class CompanyRow:
    stats: CompanyStats
    pct: int

    @property
    def frequent(self) -> bool:
        return self.stats.total >= FREQUENT_COMPANY_THRESHOLD


@dataclass(frozen=True, slots=True)
class CompanyBreakdown:
    repeated: list[CompanyRow]
    single_application_companies: int


@dataclass(frozen=True, slots=True)
class AwaitingResponse:
    application: Application
    days_waiting: int


@dataclass(frozen=True, slots=True)
class Kpis:
    today: int
    this_week: int
    this_month: int
    period_applied: int
    period_rejected: int

    @property
    def rejection_rate(self) -> int:
        return percent(self.period_rejected, self.period_applied)


@dataclass(frozen=True, slots=True)
class Dashboard:
    period: Period
    window: DateRange
    kpis: Kpis
    daily: Series
    weekly: Series
    monthly: Series
    cumulative: Cumulative
    calendar: list[CalendarWeek]
    funnel: list[FunnelStage]
    awaiting_response: list[AwaitingResponse]
    status_counts: dict[Status, int]
    companies: CompanyBreakdown
    stale_after_days: int = STALE_AFTER_DAYS

    @property
    def window_label(self) -> str:
        return f"{format_day(self.window[0])} – {format_day(self.window[1])}"

    @property
    def window_days(self) -> int:
        return (self.window[1] - self.window[0]).days + 1


def percent(value: int, total: int) -> int:
    return round(value / total * 100) if total else 0


def format_day(day: date) -> str:
    return f"{day.day} {TR_MONTHS[day.month - 1]}"


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def month_start(day: date, months_back: int = 0) -> date:
    index = day.year * 12 + day.month - 1 - months_back
    return date(index // 12, index % 12 + 1, 1)


def days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def sum_range(counts: DayCounts, start: date, end: date) -> int:
    return sum(count for day, count in counts.items() if start <= day < end)


def window_start(today: date, period: Period, first_activity: date | None) -> date:
    """Fixed periods cover exactly their length; all-time starts at the first activity."""
    if period.days is not None:
        return today - timedelta(days=period.days - 1)
    first = first_activity or today
    return min(first, today - timedelta(days=MIN_WINDOW_DAYS - 1))


def daily_specs(start: date, today: date) -> list[BucketSpec]:
    days = days_between(start, today)
    dense = len(days) > DENSE_DAILY_LIMIT
    specs = []
    for i, day in enumerate(days):
        if dense:
            label = format_day(day) if day.weekday() == 0 else ""
        else:
            label = format_day(day) if day.day == 1 or i == 0 else str(day.day)
        specs.append(
            BucketSpec(
                start=day,
                end=day + timedelta(days=1),
                label=label,
                title=format_day(day),
                current=day == today,
                weekend=day.weekday() >= 5,
            )
        )
    return specs


def weekly_specs(start: date, today: date) -> list[BucketSpec]:
    current = week_start(today)
    window_end = today + timedelta(days=1)
    specs = []
    week = week_start(start)
    while week <= current:
        next_week = week + timedelta(days=7)
        bucket_start, bucket_end = max(week, start), min(next_week, window_end)
        specs.append(
            BucketSpec(
                start=bucket_start,
                end=bucket_end,
                label=format_day(bucket_start),
                title=f"{format_day(bucket_start)} – {format_day(bucket_end - timedelta(days=1))}",
                current=week == current,
            )
        )
        week = next_week
    return specs


def monthly_specs(start: date, today: date) -> list[BucketSpec]:
    months_back = (today.year - start.year) * 12 + today.month - start.month
    specs = []
    for back in range(months_back, -1, -1):
        month = month_start(today, back)
        name = f"{TR_MONTHS[month.month - 1]} {month.year}"
        specs.append(
            BucketSpec(
                start=max(month, start),
                end=min(month_start(today, back - 1), today + timedelta(days=1)),
                label=name,
                title=name,
                current=back == 0,
            )
        )
    return specs


def build_series(specs: list[BucketSpec], applied: DayCounts, rejected: DayCounts) -> Series:
    totals = [
        (spec, sum_range(applied, spec.start, spec.end), sum_range(rejected, spec.start, spec.end))
        for spec in specs
    ]
    peak = max((max(a, r) for _, a, r in totals), default=0)
    return Series([Bucket(spec, a, r, percent(a, peak), percent(r, peak)) for spec, a, r in totals])


def build_cumulative(
    start: date, today: date, applied: DayCounts, rejected: DayCounts
) -> Cumulative:
    days = days_between(start, today)
    applied_running = sum(c for d, c in applied.items() if d < start)
    rejected_running = sum(c for d, c in rejected.items() if d < start)
    applied_values, rejected_values = [], []
    for day in days:
        applied_running += applied.get(day, 0)
        rejected_running += rejected.get(day, 0)
        applied_values.append(applied_running)
        rejected_values.append(rejected_running)
    peak = max(applied_running, rejected_running, 1)
    last = max(len(days) - 1, 1)

    def to_points(values: list[int]) -> str:
        return " ".join(
            f"{i / last * 100:.2f},{100 - v / peak * 100:.2f}" for i, v in enumerate(values)
        )

    return Cumulative(
        applied_points=to_points(applied_values),
        rejected_points=to_points(rejected_values),
        applied_total=applied_running,
        rejected_total=rejected_running,
        peak=peak,
        start_label=format_day(start),
        end_label=format_day(today),
    )


def build_calendar(
    start: date, today: date, applied: DayCounts, rejected: DayCounts
) -> list[CalendarWeek]:
    """Month-style calendar of the last `CALENDAR_WEEKS` weeks, ending with the current week.

    Days outside the selected window are still drawn for orientation but carry no counts.
    """
    peak = max((applied.get(day, 0) for day in days_between(start, today)), default=0)
    first_week = week_start(today) - timedelta(weeks=CALENDAR_WEEKS - 1)
    weeks = []
    for w in range(CALENDAR_WEEKS):
        week = first_week + timedelta(weeks=w)
        days = [week + timedelta(days=i) for i in range(7)]
        cells = []
        for day in days:
            inside = start <= day <= today
            count = applied.get(day, 0) if inside else 0
            rejected_count = rejected.get(day, 0) if inside else 0
            cells.append(
                CalendarDay(
                    day=day.day,
                    inside=inside,
                    today=day == today,
                    level=min(4, -(-count * 4 // peak)) if count else 0,
                    rejected=rejected_count,
                    title=f"{format_day(day)}: {count} başvuru, {rejected_count} red",
                )
            )
        month_label = next(
            (TR_MONTHS[d.month - 1] for d in days if d.day == 1),
            TR_MONTHS[week.month - 1] if w == 0 else "",
        )
        weeks.append(CalendarWeek(month_label, cells))
    return weeks


def build_funnel(status_counts: Mapping[Status, int]) -> list[FunnelStage]:
    """Approximate funnel from current statuses: reaching a stage implies passing earlier ones.

    Rejected and ghosted applications only count towards the first stage because the
    stage at which they dropped out is not recorded.
    """
    total = sum(status_counts.values())
    stages: list[FunnelStage] = []
    previous: int | None = None
    for i, status in enumerate(FUNNEL_STAGES):
        reached = total if i == 0 else sum(status_counts.get(s, 0) for s in FUNNEL_STAGES[i:])
        step = percent(reached, previous) if previous else None
        stages.append(FunnelStage(status, reached, percent(reached, total), step))
        previous = reached
    return stages


def build_company_breakdown(stats: list[CompanyStats]) -> CompanyBreakdown:
    repeated = [s for s in stats if s.total > 1]
    peak = max((s.total for s in repeated), default=0)
    return CompanyBreakdown(
        repeated=[CompanyRow(s, percent(s.total, peak)) for s in repeated],
        single_application_companies=len(stats) - len(repeated),
    )


def build_dashboard(repo: ApplicationRepository, period: Period, today: date) -> Dashboard:
    applied = repo.daily_counts("applied_at")
    rejected = repo.daily_counts("rejected_at")
    first_activity = min(applied.keys() | rejected.keys(), default=None)
    start = window_start(today, period, first_activity)
    tomorrow = today + timedelta(days=1)
    cutoff = today - timedelta(days=STALE_AFTER_DAYS)

    return Dashboard(
        period=period,
        window=(start, today),
        kpis=Kpis(
            today=applied.get(today, 0),
            this_week=sum_range(applied, week_start(today), tomorrow),
            this_month=sum_range(applied, month_start(today), tomorrow),
            period_applied=sum_range(applied, start, tomorrow),
            period_rejected=sum_range(rejected, start, tomorrow),
        ),
        daily=build_series(daily_specs(start, today), applied, rejected),
        weekly=build_series(weekly_specs(start, today), applied, rejected),
        monthly=build_series(monthly_specs(start, today), applied, rejected),
        cumulative=build_cumulative(start, today, applied, rejected),
        calendar=build_calendar(start, today, applied, rejected),
        funnel=build_funnel(repo.status_counts(since=start)),
        awaiting_response=[
            AwaitingResponse(app, (today - app.applied_at).days)
            for app in repo.awaiting_response(applied_before=cutoff)
        ],
        status_counts=repo.status_counts(),
        companies=build_company_breakdown(repo.company_stats()),
    )
