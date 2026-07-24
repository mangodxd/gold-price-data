from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import Engine, create_engine

from src.models import create_tables
from src.storage.repository import Repository


@pytest.fixture
def in_memory_engine() -> Engine:
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    create_tables(engine)
    return engine


@pytest.fixture
def repo(in_memory_engine: Engine) -> Repository:
    """Create a Repository backed by an in-memory SQLite database."""
    return Repository(engine=in_memory_engine)


@pytest.fixture
def temp_db_engine() -> Generator[Engine, None, None]:
    """Create a temporary file-based SQLite engine for testing.

    Cleanup is handled automatically after the test completes.
    """
    with TemporaryDirectory() as tmp_dir:
        db_path = str(Path(tmp_dir) / "test.db")
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        create_tables(engine)
        yield engine
