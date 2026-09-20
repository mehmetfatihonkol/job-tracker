from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

from app.db import SOURCES, today_iso

load_dotenv()

JOB_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "jobs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "location": {"type": ["string", "null"]},
                    "source": {
                        "type": "string",
                        "enum": list(SOURCES),
                    },
                    "job_url": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                },
                "required": [
                    "company",
                    "title",
                    "location",
                    "source",
                    "job_url",
                    "description",
                ],
            },
        }
    },
    "required": ["jobs"],
}

URL_RE = re.compile(r"https?://[^\s)>\]]+", re.I)
AT_RE = re.compile(r"^(?P<title>.+?)\s+at\s+(?P<company>.+)$", re.I)
DASH_RE = re.compile(r"^(?P<title>.+?)\s+[–—-]\s+(?P<company>.+)$")


def _split_blocks(text: str) -> list[str]:
    chunks = re.split(r"\n\s*---+\s*\n", text.strip())
    return [c.strip() for c in chunks if c.strip()]


def _guess_source(text: str) -> str:
    lower = text.lower()
    if "linkedin.com" in lower or "about the job" in lower:
        return "linkedin"
    if "kariyer.net" in lower:
        return "kariyer_net"
    if re.search(r"https?://", text) and "linkedin" not in lower:
        return "company_site"
    return "other"


def parse_block_heuristic(block: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    title = ""
    company = ""
    location = None
    if lines:
        m = AT_RE.match(lines[0]) or DASH_RE.match(lines[0])
        if m:
            title = m.group("title").strip()
            company = m.group("company").strip()
        else:
            title = lines[0]
            if len(lines) > 1 and "·" in lines[1]:
                parts = [p.strip() for p in lines[1].split("·")]
                company = parts[0]
                if len(parts) > 1:
                    location = parts[1]
            elif len(lines) > 1 and not lines[1].lower().startswith("http"):
                company = lines[1]
    urls = URL_RE.findall(block)
    job_url = urls[0].rstrip(".,;") if urls else None
    description = block.strip()
    return {
        "company": company,
        "title": title,
        "location": location,
        "source": _guess_source(block),
        "job_url": job_url,
        "description": description,
        "applied_at": today_iso(),
        "notes": None,
    }


def parse_heuristic(text: str) -> list[dict[str, Any]]:
    return [parse_block_heuristic(block) for block in _split_blocks(text)]


def _normalize_jobs(raw_jobs: list[dict[str, Any]], original_text: str) -> list[dict[str, Any]]:
    today = today_iso()
    out: list[dict[str, Any]] = []
    for job in raw_jobs:
        source = job.get("source") or "other"
        if source not in SOURCES:
            source = "other"
        out.append(
            {
                "company": (job.get("company") or "").strip(),
                "title": (job.get("title") or "").strip(),
                "location": (job.get("location") or None),
                "source": source,
                "job_url": (job.get("job_url") or None),
                "description": job.get("description") or original_text.strip(),
                "applied_at": today,
                "notes": None,
            }
        )
    return out


def parse_openai(text: str) -> list[dict[str, Any]]:
    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract job listings from pasted text. "
                    "The user may paste one listing or several. "
                    "Blocks may be separated by --- . "
                    "source must be one of: linkedin, kariyer_net, company_site, other. "
                    "Keep description as the cleaned job body. "
                    "If a field is unknown, use empty string for company/title and null for optional fields."
                ),
            },
            {"role": "user", "content": text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "job_listings",
                "strict": True,
                "schema": JOB_SCHEMA,
            },
        },
    )
    content = completion.choices[0].message.content or "{}"
    payload = json.loads(content)
    jobs = payload.get("jobs") or []
    if not isinstance(jobs, list):
        raise ValueError("OpenAI response missing jobs array")
    return _normalize_jobs(jobs, text)


def parse_jobs(text: str) -> tuple[list[dict[str, Any]], str, str | None]:
    stripped = text.strip()
    if not stripped:
        return [], "heuristic", "empty text"
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if api_key:
        try:
            return parse_openai(stripped), "openai", None
        except Exception as exc:
            jobs = parse_heuristic(stripped)
            return jobs, "heuristic", str(exc)
    return parse_heuristic(stripped), "heuristic", None
