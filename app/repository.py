import sqlite3
from collections.abc import Callable, Iterable
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from app.domain import Status, resolve_rejected_at
from app.schemas import Application, ApplicationCreate, ApplicationUpdate, CompanyStats

Clock = Callable[[], datetime]
DateColumn = Literal["applied_at", "rejected_at"]

_COLUMNS = (
    "company",
    "title",
    "location",
    "source",
    "job_url",
    "description",
    "status",
    "applied_at",
    "follow_up_at",
    "rejected_at",
    "notes",
)


def _to_db(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return value


def _timestamp(moment: datetime) -> str:
    return moment.isoformat(sep=" ", timespec="seconds")


def _to_application(row: sqlite3.Row) -> Application:
    return Application.model_validate(dict(row))


class ApplicationRepository:
    def __init__(self, conn: sqlite3.Connection, now: Clock = datetime.now) -> None:
        self._conn = conn
        self._now = now

    def search(
        self,
        *,
        status: Status | None = None,
        company: str | None = None,
        query: str | None = None,
        limit: int | None = None,
    ) -> list[Application]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        if company:
            clauses.append("company = ? COLLATE NOCASE")
            params.append(company.strip())
        if query:
            like = f"%{query.strip()}%"
            clauses.append("(company LIKE ? OR title LIKE ? OR location LIKE ?)")
            params.extend([like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM applications {where} ORDER BY applied_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [_to_application(row) for row in self._conn.execute(sql, params)]

    def get(self, application_id: int) -> Application | None:
        row = self._conn.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        return _to_application(row) if row else None

    def create(self, data: ApplicationCreate) -> Application:
        now = self._now()
        today = now.date()
        values = data.model_dump()
        values["applied_at"] = data.applied_at or today
        values["rejected_at"] = resolve_rejected_at(data.status, data.rejected_at, None, today)
        placeholders = ", ".join("?" for _ in (*_COLUMNS, "created_at", "updated_at"))
        cursor = self._conn.execute(
            f"""
            INSERT INTO applications ({", ".join(_COLUMNS)}, created_at, updated_at)
            VALUES ({placeholders})
            """,
            (*(_to_db(values[column]) for column in _COLUMNS), _timestamp(now), _timestamp(now)),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return an id for the inserted application")
        created = self.get(cursor.lastrowid)
        if created is None:
            raise RuntimeError(f"Application {cursor.lastrowid} vanished after insert")
        return created

    def create_many(self, items: Iterable[ApplicationCreate]) -> list[Application]:
        return [self.create(item) for item in items]

    def update(self, application_id: int, patch: ApplicationUpdate) -> Application | None:
        current = self.get(application_id)
        if current is None:
            return None
        changes = patch.model_dump(exclude_unset=True)
        status = changes.get("status") or current.status
        changes["rejected_at"] = resolve_rejected_at(
            status, changes.get("rejected_at"), current.rejected_at, self._now().date()
        )
        assignments = ", ".join(f"{column} = ?" for column in changes)
        values = [_to_db(value) for value in changes.values()]
        self._conn.execute(
            f"UPDATE applications SET {assignments}, updated_at = ? WHERE id = ?",
            (*values, _timestamp(self._now()), application_id),
        )
        return self.get(application_id)

    def delete(self, application_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))
        return cursor.rowcount > 0

    def daily_counts(self, column: DateColumn) -> dict[date, int]:
        rows = self._conn.execute(
            f"""
            SELECT date({column}) AS day, COUNT(*) AS cnt
            FROM applications
            WHERE date({column}) IS NOT NULL
            GROUP BY date({column})
            """
        )
        return {date.fromisoformat(row["day"]): row["cnt"] for row in rows}

    def status_counts(self, since: date | None = None) -> dict[Status, int]:
        rows = self._conn.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM applications
            WHERE ? IS NULL OR date(applied_at) >= ?
            GROUP BY status
            """,
            (_to_db(since), _to_db(since)),
        )
        return {Status(row["status"]): row["cnt"] for row in rows}

    def company_stats(self) -> list[CompanyStats]:
        rows = self._conn.execute(
            """
            SELECT MIN(company) AS company,
                   COUNT(*) AS total,
                   COALESCE(SUM(status = 'rejected'), 0) AS rejected,
                   COALESCE(SUM(status = 'applied'), 0) AS waiting
            FROM applications
            GROUP BY company COLLATE NOCASE
            ORDER BY total DESC, company COLLATE NOCASE ASC
            """
        )
        return [CompanyStats.model_validate(dict(row)) for row in rows]

    def awaiting_response(self, applied_before: date) -> list[Application]:
        rows = self._conn.execute(
            """
            SELECT * FROM applications
            WHERE status = ? AND date(applied_at) <= ?
            ORDER BY date(applied_at) ASC, id ASC
            """,
            (Status.APPLIED.value, applied_before.isoformat()),
        )
        return [_to_application(row) for row in rows]
