from datetime import date
from enum import StrEnum


class Status(StrEnum):
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    GHOSTED = "ghosted"

    @property
    def label(self) -> str:
        return _STATUS_LABELS[self]


class Source(StrEnum):
    LINKEDIN = "linkedin"
    COMPANY_SITE = "company_site"
    OTHER = "other"

    @property
    def label(self) -> str:
        return _SOURCE_LABELS[self]


_STATUS_LABELS = {
    Status.APPLIED: "Başvuruldu",
    Status.SCREENING: "Ön eleme",
    Status.INTERVIEW: "Mülakat",
    Status.OFFER: "Teklif",
    Status.REJECTED: "Reddedildi",
    Status.GHOSTED: "Yanıtsız",
}

_SOURCE_LABELS = {
    Source.LINKEDIN: "LinkedIn",
    Source.COMPANY_SITE: "Şirket sitesi",
    Source.OTHER: "Diğer",
}

FREQUENT_COMPANY_THRESHOLD = 3
"""Applications to the same company at which the UI starts warning."""

FUNNEL_STAGES: tuple[Status, ...] = (
    Status.APPLIED,
    Status.SCREENING,
    Status.INTERVIEW,
    Status.OFFER,
)


def resolve_rejected_at(
    status: Status,
    requested: date | None,
    current: date | None,
    today: date,
) -> date | None:
    """Keep `rejected_at` consistent with `status`.

    A rejection date only exists while the application is rejected. An explicit
    date wins, then the previously stored one, and finally today.
    """
    if status is not Status.REJECTED:
        return None
    return requested or current or today
