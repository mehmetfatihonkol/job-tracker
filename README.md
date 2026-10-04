# job-tracker

Local-first job application tracker. Paste listings, track their status and see how your
search is going on an analytics dashboard.

- **Dashboard** – daily / weekly / monthly applications vs. rejections, cumulative trend,
  calendar heatmap, status funnel, per-source rejection rate and a list of applications
  still waiting for a response.
- **Bulk import** – paste one or many listings (separated by `---`). With an OpenAI key they
  are extracted via structured outputs; otherwise a rule-based parser is used.
- **Private by default** – data lives in a local SQLite file that never leaves your machine.

## Stack

FastAPI · Jinja2 · SQLite · Pydantic v2 · OpenAI SDK · vanilla JS (ES modules) · uv · pytest · Ruff · mypy

## Getting started

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env        # optional: add OPENAI_API_KEY
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

## Development

```bash
uv run pytest               # tests
uv run ruff check .         # lint
uv run ruff format .        # format
uv run mypy app tests       # type check
```

## Architecture

```
app/
├── main.py            # app factory, lifespan (runs migrations)
├── config.py          # typed settings from environment / .env
├── domain.py          # Status / Source enums and domain rules
├── schemas.py         # Pydantic request / response models
├── database.py        # connections, transactions, versioned migrations
├── repository.py      # all SQL lives here
├── services/
│   ├── dashboard.py   # dashboard view model (pure functions over daily counts)
│   └── parsing.py     # heuristic + OpenAI listing parsers
├── web/
│   ├── dependencies.py
│   ├── pages.py       # server-rendered HTML routes
│   ├── api.py         # JSON API under /api
│   └── templating.py
├── templates/
└── static/            # css/, js/
tests/                 # unit tests per layer + API tests with an isolated database
```

Requests flow `web → services → repository → SQLite`. Each request gets its own
transaction through a FastAPI dependency, and schema changes are applied as ordered
migrations tracked with `PRAGMA user_version`.
