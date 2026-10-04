import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ValidationError

from app.domain import Source
from app.schemas import ParsedJob

logger = logging.getLogger(__name__)

_BLOCK_SEPARATOR = re.compile(r"\n\s*---+\s*\n")
_URL = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)
_TITLE_AT_COMPANY = re.compile(r"^(?P<title>.+?)\s+at\s+(?P<company>.+)$", re.IGNORECASE)
_TITLE_DASH_COMPANY = re.compile(r"^(?P<title>.+?)\s+[–—-]\s+(?P<company>.+)$")

_SYSTEM_PROMPT = (
    "Extract job listings from pasted text. "
    "The user may paste one listing or several; blocks may be separated by ---. "
    f"source must be one of: {', '.join(Source)}. "
    "Keep description as the cleaned job body. "
    "If a field is unknown, use an empty string for company/title and null for optional fields."
)


class ListingParser(Protocol):
    def parse(self, text: str, today: date) -> list[ParsedJob]: ...


class LLMResponseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ParseResult:
    jobs: list[ParsedJob]
    parser: Literal["openai", "heuristic"]
    error: str | None = None


def split_blocks(text: str) -> list[str]:
    return [block.strip() for block in _BLOCK_SEPARATOR.split(text.strip()) if block.strip()]


def guess_source(text: str) -> Source:
    lower = text.lower()
    if "linkedin.com" in lower or "about the job" in lower:
        return Source.LINKEDIN
    if _URL.search(text):
        return Source.COMPANY_SITE
    return Source.OTHER


class HeuristicParser:
    """Rule-based fallback: first line is the title, optionally followed by the company."""

    def parse(self, text: str, today: date) -> list[ParsedJob]:
        return [self._parse_block(block, today) for block in split_blocks(text)]

    @staticmethod
    def _parse_block(block: str, today: date) -> ParsedJob:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        title, company, location = "", "", None
        if lines:
            match = _TITLE_AT_COMPANY.match(lines[0]) or _TITLE_DASH_COMPANY.match(lines[0])
            if match:
                title = match["title"].strip()
                company = match["company"].strip()
            else:
                title = lines[0]
                second = lines[1] if len(lines) > 1 else ""
                if "·" in second:
                    company, _, rest = (part.strip() for part in second.partition("·"))
                    location = rest.split("·")[0].strip() or None
                elif second and not second.lower().startswith("http"):
                    company = second
        urls = _URL.findall(block)
        return ParsedJob(
            company=company,
            title=title,
            location=location,
            source=guess_source(block),
            job_url=urls[0].rstrip(".,;") if urls else None,
            description=block,
            applied_at=today,
        )


class _LLMJob(BaseModel):
    company: str
    title: str
    location: str | None
    source: Source
    job_url: str | None
    description: str | None


class _LLMJobs(BaseModel):
    jobs: list[_LLMJob]


class OpenAIParser:
    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def parse(self, text: str, today: date) -> list[ParsedJob]:
        completion = self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format=_LLMJobs,
        )
        result = completion.choices[0].message.parsed
        if result is None:
            raise LLMResponseError("LLM returned no structured output")
        return [
            ParsedJob(
                company=job.company.strip(),
                title=job.title.strip(),
                location=job.location,
                source=job.source,
                job_url=job.job_url,
                description=job.description or text,
                applied_at=today,
            )
            for job in result.jobs
        ]


def parse_listings(text: str, today: date, llm: ListingParser | None) -> ParseResult:
    heuristic = HeuristicParser()
    if llm is None:
        return ParseResult(heuristic.parse(text, today), "heuristic")
    try:
        return ParseResult(llm.parse(text, today), "openai")
    except (OpenAIError, ValidationError, LLMResponseError) as exc:
        logger.warning("LLM parsing failed; falling back to heuristic parser", exc_info=exc)
        return ParseResult(heuristic.parse(text, today), "heuristic", str(exc))
