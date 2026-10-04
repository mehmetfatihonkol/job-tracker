from datetime import date

import pytest

from app.domain import Source
from app.schemas import ParsedJob
from app.services.parsing import HeuristicParser, LLMResponseError, guess_source, parse_listings

TODAY = date(2026, 10, 4)


def test_heuristic_parses_title_at_company() -> None:
    [job] = HeuristicParser().parse(
        "Senior Backend Engineer at Acme\nhttps://acme.com/jobs/1.", TODAY
    )

    assert (job.title, job.company) == ("Senior Backend Engineer", "Acme")
    assert job.job_url == "https://acme.com/jobs/1"
    assert job.source is Source.COMPANY_SITE
    assert job.applied_at == TODAY


def test_heuristic_parses_company_and_location_line() -> None:
    [job] = HeuristicParser().parse("Data Engineer\nGlobex · Munich · Hybrid", TODAY)

    assert (job.title, job.company, job.location) == ("Data Engineer", "Globex", "Munich")


def test_heuristic_splits_blocks() -> None:
    jobs = HeuristicParser().parse("Role A at X\n---\nRole B - Y\n\n---\n", TODAY)

    assert [(j.title, j.company) for j in jobs] == [("Role A", "X"), ("Role B", "Y")]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://www.linkedin.com/jobs/view/1", Source.LINKEDIN),
        ("About the job\nWe are hiring", Source.LINKEDIN),
        ("Apply at https://careers.acme.com", Source.COMPANY_SITE),
        ("Plain text listing", Source.OTHER),
    ],
)
def test_guess_source(text: str, expected: Source) -> None:
    assert guess_source(text) is expected


class _FailingParser:
    def parse(self, text: str, today: date) -> list[ParsedJob]:
        raise LLMResponseError("model refused")


class _StaticParser:
    def parse(self, text: str, today: date) -> list[ParsedJob]:
        return [ParsedJob(company="Acme", title="Engineer", applied_at=today)]


def test_parse_listings_uses_llm_when_available() -> None:
    result = parse_listings("anything", TODAY, _StaticParser())

    assert result.parser == "openai"
    assert result.jobs[0].company == "Acme"


def test_parse_listings_falls_back_and_reports_error() -> None:
    result = parse_listings("Engineer at Acme", TODAY, _FailingParser())

    assert result.parser == "heuristic"
    assert result.error == "model refused"
    assert result.jobs[0].company == "Acme"


def test_parse_listings_without_llm() -> None:
    result = parse_listings("Engineer at Acme", TODAY, None)

    assert (result.parser, result.error) == ("heuristic", None)
