# job-tracker

Track daily job applications and keep role notes in one place.

Local FastAPI + SQLite. Database and `.env` stay out of git.

```powershell
cd job-tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

Optional: set `OPENAI_API_KEY` in `.env` so pasted listings are parsed with `gpt-4o-mini`. Without a key, heuristic parse is used. Separate multiple listings with `---`.
