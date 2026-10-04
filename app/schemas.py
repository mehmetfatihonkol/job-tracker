from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, model_validator

from app.domain import Source, Status


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str | None, BeforeValidator(_blank_to_none)]
OptionalDate = Annotated[date | None, BeforeValidator(_blank_to_none)]
OptionalStatus = Annotated[Status | None, BeforeValidator(_blank_to_none)]


class Application(BaseModel):
    id: int
    company: str
    title: str
    location: str | None
    source: Source
    job_url: str | None
    description: str | None
    status: Status
    applied_at: date
    follow_up_at: date | None
    rejected_at: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationCreate(BaseModel):
    company: RequiredText
    title: RequiredText
    location: OptionalText = None
    source: Source = Source.OTHER
    job_url: OptionalText = None
    description: OptionalText = None
    status: Status = Status.APPLIED
    applied_at: OptionalDate = None
    follow_up_at: OptionalDate = None
    rejected_at: OptionalDate = None
    notes: OptionalText = None


class ApplicationUpdate(BaseModel):
    company: RequiredText | None = None
    title: RequiredText | None = None
    location: OptionalText = None
    source: Source | None = None
    job_url: OptionalText = None
    description: OptionalText = None
    status: Status | None = None
    applied_at: OptionalDate = None
    follow_up_at: OptionalDate = None
    rejected_at: OptionalDate = None
    notes: OptionalText = None

    @model_validator(mode="after")
    def _required_columns_not_null(self) -> Self:
        for name in ("company", "title", "source", "status", "applied_at"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be empty")
        return self


class ApplicationFilters(BaseModel):
    status: OptionalStatus = None
    company: OptionalText = None
    q: OptionalText = None


class CompanyStats(BaseModel):
    company: str
    total: int
    rejected: int
    waiting: int


class BulkCreateRequest(BaseModel):
    items: list[ApplicationCreate] = Field(min_length=1)


class BulkCreateResponse(BaseModel):
    ids: list[int]
    count: int


class ParseRequest(BaseModel):
    text: RequiredText


class ParsedJob(BaseModel):
    company: str = ""
    title: str = ""
    location: str | None = None
    source: Source = Source.OTHER
    job_url: str | None = None
    description: str | None = None
    applied_at: date


class ParseResponse(BaseModel):
    jobs: list[ParsedJob]
    parser: Literal["openai", "heuristic"]
    error: str | None = None
