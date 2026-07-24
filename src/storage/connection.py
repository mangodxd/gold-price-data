from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine


def get_db_path() -> str:
    """Resolve the database file path from environment variable or default.

    Returns:
        Database file path as a string.
    """
    import os

    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        return env_path
    return str(Path(__file__).resolve().parent.parent.parent / "data" / "gold_pipeline.db")


def create_db_engine(db_path: str | None = None) -> Engine:
    """Create and configure a SQLite engine with WAL mode.

    Args:
        db_path: Path to the SQLite database file. If None, uses
            the default path from get_db_path().

    Returns:
        Configured SQLAlchemy Engine instance.
    """
    if db_path is None:
        db_path = get_db_path()

    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_wal(dbapi_connection, connection_record):  # noqa: ANN001
        """Enable WAL mode on SQLite connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine
