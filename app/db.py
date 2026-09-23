from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "job_tracker.db"

STATUSES = ("applied", "screening", "interview", "offer", "rejected", "ghosted")
SOURCES = ("linkedin", "kariyer_net", "company_site", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    source TEXT NOT NULL DEFAULT 'other',
    job_url TEXT,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'applied',
    applied_at TEXT NOT NULL,
    follow_up_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_title ON applications(title);
CREATE INDEX IF NOT EXISTS idx_applications_applied_at ON applications(applied_at);
"""


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def today_iso() -> str:
    return date.today().isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def list_applications(
    *,
    status: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if q:
        like = f"%{q.strip()}%"
        clauses.append("(company LIKE ? OR title LIKE ? OR location LIKE ?)")
        params.extend([like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM applications {where} ORDER BY applied_at DESC, id DESC"
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_application(app_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return _row(conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone())


def insert_application(item: dict[str, Any]) -> int:
    ts = now_iso()
    applied = item.get("applied_at") or today_iso()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO applications (
                company, title, location, source, job_url, description,
                status, applied_at, follow_up_at, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["company"].strip(),
                item["title"].strip(),
                (item.get("location") or "").strip() or None,
                item.get("source") or "other",
                (item.get("job_url") or "").strip() or None,
                item.get("description") or None,
                item.get("status") or "applied",
                applied,
                (item.get("follow_up_at") or "").strip() or None,
                (item.get("notes") or "").strip() or None,
                ts,
                ts,
            ),
        )
        return int(cur.lastrowid)


def insert_many(items: list[dict[str, Any]]) -> list[int]:
    return [insert_application(item) for item in items]


def update_application(app_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {
        "company",
        "title",
        "location",
        "source",
        "job_url",
        "description",
        "status",
        "applied_at",
        "follow_up_at",
        "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_application(app_id)
    for key in ("location", "job_url", "follow_up_at", "notes", "description"):
        if key in updates and isinstance(updates[key], str) and not updates[key].strip():
            updates[key] = None
    sets = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [now_iso(), app_id]
    with connect() as conn:
        conn.execute(
            f"UPDATE applications SET {sets}, updated_at = ? WHERE id = ?",
            params,
        )
    return get_application(app_id)


def delete_application(app_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        return cur.rowcount > 0


def dashboard_stats() -> dict[str, Any]:
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE date(applied_at) = date('now', 'localtime')"
        ).fetchone()[0]
        week = conn.execute(
            """
            SELECT COUNT(*) FROM applications
            WHERE date(applied_at) >= date('now', 'localtime', '-6 days')
            """
        ).fetchone()[0]
        by_status = {
            row["status"]: row["cnt"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM applications GROUP BY status"
            )
        }
        by_title = [
            dict(row)
            for row in conn.execute(
                """
                SELECT title, COUNT(*) AS cnt
                FROM applications
                GROUP BY title
                ORDER BY cnt DESC, title ASC
                LIMIT 20
                """
            )
        ]
        counted = {
            row["d"]: int(row["cnt"])
            for row in conn.execute(
                """
                SELECT date(applied_at) AS d, COUNT(*) AS cnt
                FROM applications
                WHERE date(applied_at) >= date('now', 'localtime', '-13 days')
                GROUP BY date(applied_at)
                """
            )
        }
    today_d = date.today()
    by_day = []
    for i in range(13, -1, -1):
        d = (today_d - timedelta(days=i)).isoformat()
        by_day.append({"date": d, "cnt": counted.get(d, 0)})
    by_day_max = max((d["cnt"] for d in by_day), default=0)
    return {
        "total": total,
        "today": today,
        "week": week,
        "by_status": by_status,
        "by_title": by_title,
        "by_day": by_day,
        "by_day_max": by_day_max,
    }
