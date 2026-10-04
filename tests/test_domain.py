from datetime import date

import pytest

from app.domain import Status, resolve_rejected_at

TODAY = date(2026, 10, 4)
EARLIER = date(2026, 9, 20)
EXPLICIT = date(2026, 9, 30)


@pytest.mark.parametrize(
    ("status", "requested", "current", "expected"),
    [
        (Status.APPLIED, EXPLICIT, EARLIER, None),
        (Status.INTERVIEW, None, EARLIER, None),
        (Status.REJECTED, None, None, TODAY),
        (Status.REJECTED, None, EARLIER, EARLIER),
        (Status.REJECTED, EXPLICIT, EARLIER, EXPLICIT),
    ],
)
def test_resolve_rejected_at(
    status: Status, requested: date | None, current: date | None, expected: date | None
) -> None:
    assert resolve_rejected_at(status, requested, current, TODAY) == expected
