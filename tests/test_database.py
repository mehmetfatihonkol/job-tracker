from pathlib import Path

from app import database


def _columns(path: Path) -> set[str]:
    with database.transaction(path) as conn:
        return {row["name"] for row in conn.execute("PRAGMA table_info(applications)")}


def test_migrate_creates_latest_schema(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    with database.transaction(path) as conn:
        database.migrate(conn)
        assert database.schema_version(conn) == len(database.MIGRATIONS)
    assert "rejected_at" in _columns(path)


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "twice.db"
    for _ in range(2):
        with database.transaction(path) as conn:
            database.migrate(conn)
    with database.transaction(path) as conn:
        assert database.schema_version(conn) == len(database.MIGRATIONS)


def test_migrate_backfills_rejected_at_for_legacy_rows(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with database.transaction(path) as conn:
        database.MIGRATIONS[0](conn)
        conn.execute(
            """
            INSERT INTO applications (company, title, status, applied_at, created_at, updated_at)
            VALUES ('Acme', 'Engineer', 'rejected', '2026-09-01', '2026-09-01 10:00:00',
                    '2026-09-15 09:30:00')
            """
        )

    with database.transaction(path) as conn:
        database.migrate(conn)
        row = conn.execute("SELECT rejected_at FROM applications").fetchone()

    assert row["rejected_at"] == "2026-09-15"
