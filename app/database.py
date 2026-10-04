import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

Migration = Callable[[sqlite3.Connection], None]


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI may open a request-scoped connection in one worker thread and use it in
    # another; each connection is still used by a single request at a time.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _create_applications(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
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
    )


def _add_rejected_at(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(applications)")}
    # Databases created before schema versioning may already have this column.
    if "rejected_at" not in columns:
        conn.execute("ALTER TABLE applications ADD COLUMN rejected_at TEXT")
        # No exact rejection date exists for older rows; the last edit is the closest signal.
        conn.execute(
            "UPDATE applications SET rejected_at = date(updated_at) WHERE status = 'rejected'"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_applications_rejected_at ON applications(rejected_at)"
    )


MIGRATIONS: tuple[Migration, ...] = (
    _create_applications,
    _add_rejected_at,
)


def schema_version(conn: sqlite3.Connection) -> int:
    version: int = conn.execute("PRAGMA user_version").fetchone()[0]
    return version


def migrate(conn: sqlite3.Connection) -> None:
    """Apply pending migrations; `PRAGMA user_version` tracks the applied count."""
    current = schema_version(conn)
    for version, migration in enumerate(MIGRATIONS[current:], start=current + 1):
        migration(conn)
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()
