from __future__ import annotations

from sqlalchemy import Engine, text

from src.exceptions import StorageError
from src.storage.repository import Repository


class TestRepositoryTableCreation:
    """Verify all 6 tables are created successfully."""

    def test_all_tables_created(self, in_memory_engine: Engine) -> None:
        """Six tables should exist after create_tables()."""
        expected_tables = {
            "gold_prices",
            "world_gold_prices",
            "exchange_rates",
            "gold_daily_summary",
            "world_gold_daily_summary",
            "api_logs",
        }
        with in_memory_engine.begin() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            actual_tables = {row[0] for row in result.fetchall()}
        assert expected_tables.issubset(actual_tables), (
            f"Missing tables: {expected_tables - actual_tables}"
        )

    def test_idempotent_creation(self, repo: Repository) -> None:
        """Calling create_tables multiple times should not raise."""
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )
        # Second creation should be safe
        assert repo.exists("gold_prices", {"product_name": "SJL1L10"})


class TestRepositoryInsert:
    """Test insert, dedup, and bulk operations."""

    def test_insert_and_exists(self, repo: Repository) -> None:
        """Insert a row and verify it exists."""
        inserted = repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )
        assert inserted is True
        assert repo.exists("gold_prices", {"product_name": "SJL1L10"})

    def test_duplicate_ignored(self, repo: Repository) -> None:
        """Inserting the same record twice should ignore the second."""
        record = {
            "source": "vang.today",
            "product_name": "SJL1L10",
            "buy_price": 85500000,
            "sell_price": 88000000,
            "recorded_at": "2026-07-24T00:00:00Z",
        }
        first = repo.create_or_ignore("gold_prices", record)
        second = repo.create_or_ignore("gold_prices", record)
        assert first is True
        assert second is False

    def test_bulk_insert(self, repo: Repository) -> None:
        """Bulk insert multiple records."""
        records = [
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
            {
                "source": "vang.today",
                "product_name": "SJ9999",
                "buy_price": 85000000,
                "sell_price": 87500000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        ]
        count = repo.bulk_insert("gold_prices", records)
        assert count == 2

    def test_bulk_insert_empty(self, repo: Repository) -> None:
        """Bulk insert with empty list should return 0."""
        count = repo.bulk_insert("gold_prices", [])
        assert count == 0

    def test_unknown_table_raises(self, repo: Repository) -> None:
        """Inserting into an unknown table should raise StorageError."""
        import pytest

        with pytest.raises(StorageError):
            repo.create_or_ignore("nonexistent", {"foo": "bar"})


class TestRepositoryGetLatest:
    """Test get_latest method."""

    def test_get_latest_no_filter(self, repo: Repository) -> None:
        """Get the most recent record without filters."""
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85600000,
                "sell_price": 88100000,
                "recorded_at": "2026-07-24T00:05:00Z",
            },
        )
        latest = repo.get_latest("gold_prices")
        assert latest is not None
        assert latest["buy_price"] == 85600000

    def test_get_latest_with_filter(self, repo: Repository) -> None:
        """Get the most recent record filtered by product."""
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJ9999",
                "buy_price": 85000000,
                "sell_price": 87500000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )
        latest = repo.get_latest("gold_prices", {"product_name": "SJ9999"})
        assert latest is not None
        assert latest["product_name"] == "SJ9999"

    def test_get_latest_empty_table(self, repo: Repository) -> None:
        """Getting latest from an empty table should return None."""
        latest = repo.get_latest("gold_prices")
        assert latest is None


class TestStaleDetection:
    """Test stale data detection."""

    def test_not_stale_when_empty(self, repo: Repository) -> None:
        """Empty table should not be considered stale."""
        stale = repo.is_stale(
            "gold_prices",
            {"source": "vang.today", "product_name": "SJL1L10"},
            current_buy=85500000,
            current_sell=88000000,
        )
        assert stale is False

    def test_stale_when_prices_match(self, repo: Repository) -> None:
        """Same prices as latest record should be stale."""
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )
        stale = repo.is_stale(
            "gold_prices",
            {"source": "vang.today", "product_name": "SJL1L10"},
            current_buy=85500000,
            current_sell=88000000,
        )
        assert stale is True

    def test_not_stale_when_prices_differ(self, repo: Repository) -> None:
        """Different prices from latest record should not be stale."""
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )
        stale = repo.is_stale(
            "gold_prices",
            {"source": "vang.today", "product_name": "SJL1L10"},
            current_buy=85600000,
            current_sell=88000000,
        )
        assert stale is False


class TestApiLog:
    """Test API logging."""

    def test_log_success(self, repo: Repository) -> None:
        """Log a successful API call."""
        repo.log_api_call(
            collector_name="domestic",
            source="vang.today",
            success=True,
            status_code=200,
            response_time_ms=150,
        )
        assert repo.exists(
            "api_logs",
            {
                "collector_name": "domestic",
                "success": 1,
            },
        )

    def test_log_failure(self, repo: Repository) -> None:
        """Log a failed API call."""
        repo.log_api_call(
            collector_name="world",
            source="xaus.com",
            success=False,
            status_code=503,
            response_time_ms=5000,
            error_message="Upstream unavailable",
        )
        assert repo.exists(
            "api_logs",
            {
                "collector_name": "world",
                "success": 0,
                "error_message": "Upstream unavailable",
            },
        )
