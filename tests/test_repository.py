from datetime import date

from app.domain import Source, Status
from app.repository import ApplicationRepository
from app.schemas import ApplicationCreate, ApplicationUpdate

from .conftest import FIXED_NOW

TODAY = FIXED_NOW.date()


def _create(repo: ApplicationRepository, **overrides: object) -> int:
    data = {"company": "Acme", "title": "Backend Engineer", **overrides}
    return repo.create(ApplicationCreate.model_validate(data)).id


def test_create_applies_defaults(repo: ApplicationRepository) -> None:
    app = repo.get(_create(repo, location="  ", notes=""))

    assert app is not None
    assert app.status is Status.APPLIED
    assert app.source is Source.OTHER
    assert app.applied_at == TODAY
    assert app.rejected_at is None
    assert app.location is None
    assert app.notes is None


def test_create_rejected_sets_rejection_date(repo: ApplicationRepository) -> None:
    app = repo.get(_create(repo, status="rejected"))

    assert app is not None
    assert app.rejected_at == TODAY


def test_update_tracks_rejection_lifecycle(repo: ApplicationRepository) -> None:
    app_id = _create(repo)

    rejected = repo.update(app_id, ApplicationUpdate(status=Status.REJECTED))
    assert rejected is not None
    assert rejected.rejected_at == TODAY

    corrected = repo.update(app_id, ApplicationUpdate(rejected_at=date(2026, 9, 30)))
    assert corrected is not None
    assert corrected.rejected_at == date(2026, 9, 30)

    edited = repo.update(app_id, ApplicationUpdate(notes="called back"))
    assert edited is not None
    assert edited.rejected_at == date(2026, 9, 30)

    reopened = repo.update(app_id, ApplicationUpdate(status=Status.INTERVIEW))
    assert reopened is not None
    assert reopened.rejected_at is None


def test_update_missing_application_returns_none(repo: ApplicationRepository) -> None:
    assert repo.update(999, ApplicationUpdate(notes="x")) is None


def test_search_filters_by_status_and_query(repo: ApplicationRepository) -> None:
    _create(repo, company="Acme", title="Data Engineer")
    _create(repo, company="Globex", title="ML Engineer", status="rejected")
    _create(repo, company="Initech", title="Designer", location="Munich")

    assert {a.company for a in repo.search(status=Status.REJECTED)} == {"Globex"}
    assert {a.company for a in repo.search(query="engineer")} == {"Acme", "Globex"}
    assert {a.company for a in repo.search(query="munich")} == {"Initech"}
    assert len(repo.search(limit=2)) == 2


def test_company_filter_and_stats_ignore_case(repo: ApplicationRepository) -> None:
    _create(repo, company="BMW AG", title="A")
    _create(repo, company="bmw ag", title="B", status="rejected")
    _create(repo, company="Acme", title="C")

    assert {a.title for a in repo.search(company="BMW AG")} == {"A", "B"}
    assert [(s.total, s.rejected, s.waiting) for s in repo.company_stats()] == [
        (2, 1, 1),
        (1, 0, 1),
    ]
    assert repo.company_stats()[0].company.casefold() == "bmw ag"


def test_delete(repo: ApplicationRepository) -> None:
    app_id = _create(repo)

    assert repo.delete(app_id) is True
    assert repo.get(app_id) is None
    assert repo.delete(app_id) is False


def test_analytics_queries(repo: ApplicationRepository) -> None:
    _create(repo, applied_at="2026-09-01", source="linkedin", status="rejected")
    _create(repo, applied_at="2026-09-01", source="linkedin")
    _create(repo, applied_at="2026-09-20", source="company_site", status="interview")

    assert repo.daily_counts("applied_at") == {date(2026, 9, 1): 2, date(2026, 9, 20): 1}
    assert repo.daily_counts("rejected_at") == {TODAY: 1}
    assert repo.status_counts() == {
        Status.APPLIED: 1,
        Status.REJECTED: 1,
        Status.INTERVIEW: 1,
    }
    assert repo.status_counts(since=date(2026, 9, 10)) == {Status.INTERVIEW: 1}

    awaiting = repo.awaiting_response(applied_before=date(2026, 9, 13))
    assert [a.applied_at for a in awaiting] == [date(2026, 9, 1)]
