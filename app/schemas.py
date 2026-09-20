from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.db import SOURCES, STATUSES


class ParseRequest(BaseModel):
    text: str = Field(min_length=1)


class ParsedJob(BaseModel):
    company: str = ""
    title: str = ""
    location: Optional[str] = None
    source: str = "other"
    job_url: Optional[str] = None
    description: Optional[str] = None
    applied_at: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("source")
    @classmethod
    def valid_source(cls, v: str) -> str:
        return v if v in SOURCES else "other"


class ParseResponse(BaseModel):
    jobs: List[ParsedJob]
    parser: str
    error: Optional[str] = None


class ApplicationIn(BaseModel):
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: Optional[str] = None
    source: str = "other"
    job_url: Optional[str] = None
    description: Optional[str] = None
    status: str = "applied"
    applied_at: Optional[str] = None
    follow_up_at: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("source")
    @classmethod
    def valid_source(cls, v: str) -> str:
        return v if v in SOURCES else "other"

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in STATUSES:
            raise ValueError("invalid status")
        return v


class BulkSaveRequest(BaseModel):
    items: List[ApplicationIn]


class ApplicationPatch(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    job_url: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    applied_at: Optional[str] = None
    follow_up_at: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("source")
    @classmethod
    def valid_source(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v if v in SOURCES else "other"

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in STATUSES:
            raise ValueError("invalid status")
        return v
