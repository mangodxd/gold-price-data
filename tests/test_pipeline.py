from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from src.collectors.base import CollectorResult
from src.storage.pipeline import Pipeline, StorageResult
from src.storage.repository import Repository


def _count_rows(repo: Repository, table: str) -> int:
    """Count rows in a table for assertion."""
    with repo.engine.begin() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()  # noqa: S608


# ---------- StorageResult ----------


class TestStorageResult:
    """StorageResult default values."""

    def test_defaults(self) -> None:
        """StorageResult should have correct default values."""
        r = StorageResult(collector_name="test", source="test", success=True)
        assert r.records_inserted == 0
        assert r.records_skipped_stale == 0
        assert r.records_skipped_duplicate == 0
        assert r.error_message is None


# ---------- Pipeline: API Logging ----------


class TestPipelineApiLogging:
    """API call logging on every collector result."""

    def test_logs_success(self, repo: Repository) -> None:
        """Successful collector run logs success entry."""
        pipe = Pipeline(repo)
        result = CollectorResult(
            source="vang.today",
            collector_name="domestic",
            success=True,
            status_code=200,
            response_time_ms=150,
        )
        pipe.process(result)
        assert _count_rows(repo, "api_logs") == 1

    def test_logs_failure(self, repo: Repository) -> None:
        """Failed collector run logs failure entry."""
        pipe = Pipeline(repo)
        result = CollectorResult(
            source="xaus.com",
            collector_name="world",
            success=False,
            status_code=503,
            response_time_ms=5000,
            error_message="Upstream unavailable",
        )
        pipe.process(result)
        assert _count_rows(repo, "api_logs") == 1

    def test_logs_multiple_collectors(self, repo: Repository) -> None:
        """Multiple collector runs log separate entries."""
        pipe = Pipeline(repo)
        results = [
            CollectorResult(source="a", collector_name="domestic", success=True),
            CollectorResult(source="b", collector_name="world", success=True),
            CollectorResult(source="c", collector_name="fx", success=True),
        ]
        pipe.process_all(results)
        assert _count_rows(repo, "api_logs") == 3


# ---------- Pipeline: Domestic Gold ----------


class TestPipelineDomestic:
    """Domestic gold storage with stale detection."""

    DOMESTIC_RECORDS: list[dict[str, Any]] = [
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

    @pytest.fixture
    def pipe(self, repo: Repository) -> Pipeline:
        """Create a Pipeline backed by in-memory DB."""
        return Pipeline(repo)

    def test_inserts_all_records(self, pipe: Pipeline, repo: Repository) -> None:
        """All records inserted on first run."""
        result = CollectorResult(
            source="vang.today",
            collector_name="domestic",
            success=True,
            data=self.DOMESTIC_RECORDS,
        )
        sr = pipe.process(result)
        assert sr.records_inserted == 2
        assert sr.records_skipped_stale == 0
        assert _count_rows(repo, "gold_prices") == 2

    def test_skips_stale_records(self, pipe: Pipeline, repo: Repository) -> None:
        """Stale records (same prices) skipped."""
        result = CollectorResult(
            source="vang.today",
            collector_name="domestic",
            success=True,
            data=self.DOMESTIC_RECORDS,
        )
        # First run: insert 2
        pipe.process(result)
        # Second run: same data — stale
        sr = pipe.process(result)
        assert sr.records_inserted == 0
        assert sr.records_skipped_stale == 2
        assert _count_rows(repo, "gold_prices") == 2

    def test_inserts_changed_record(self, pipe: Pipeline, repo: Repository) -> None:
        """Changed price on one product inserts only that product."""
        result1 = CollectorResult(
            source="vang.today",
            collector_name="domestic",
            success=True,
            data=self.DOMESTIC_RECORDS,
        )
        pipe.process(result1)

        changed = [
            dict(self.DOMESTIC_RECORDS[0]),
            dict(self.DOMESTIC_RECORDS[1]),
        ]
        changed[1]["buy_price"] = 85100000  # SJ9999 price changed
        # Different recorded_at to avoid UNIQUE constraint conflict
        changed[1]["recorded_at"] = "2026-07-24T00:05:00Z"
        result2 = CollectorResult(
            source="vang.today",
            collector_name="domestic",
            success=True,
            data=changed,
        )
        sr = pipe.process(result2)
        assert sr.records_inserted == 1  # only the changed one
        assert sr.records_skipped_stale == 1  # SJL1L10 unchanged
        assert _count_rows(repo, "gold_prices") == 3

    def test_empty_data_no_insert(self, pipe: Pipeline, repo: Repository) -> None:
        """Empty data list inserts nothing."""
        result = CollectorResult(
            source="vang.today",
            collector_name="domestic",
            success=True,
            data=[],
        )
        sr = pipe.process(result)
        assert sr.records_inserted == 0
        assert _count_rows(repo, "gold_prices") == 0


# ---------- Pipeline: World Gold ----------


class TestPipelineWorld:
    """World gold storage (no stale detection, single record)."""

    WORLD_RECORDS: list[dict[str, Any]] = [
        {
            "source": "xaus.com",
            "spot_usd_oz": 4061.7,
            "per_gram_usd": 130.59,
            "per_kg_usd": 130590.0,
            "currency": "USD",
            "unit": "troy_oz",
            "recorded_at": "2026-07-24T14:50:09.811Z",
        },
    ]

    @pytest.fixture
    def pipe(self, repo: Repository) -> Pipeline:
        """Create a Pipeline backed by in-memory DB."""
        return Pipeline(repo)

    def test_inserts_record(self, pipe: Pipeline, repo: Repository) -> None:
        """World gold record inserted."""
        result = CollectorResult(
            source="xaus.com",
            collector_name="world",
            success=True,
            data=self.WORLD_RECORDS,
        )
        sr = pipe.process(result)
        assert sr.records_inserted == 1
        assert _count_rows(repo, "world_gold_prices") == 1

    def test_skips_duplicate_on_reinsert(self, pipe: Pipeline, repo: Repository) -> None:
        """Duplicate UNIQUE constraint skips silently."""
        result = CollectorResult(
            source="xaus.com",
            collector_name="world",
            success=True,
            data=self.WORLD_RECORDS,
        )
        pipe.process(result)
        sr = pipe.process(result)
        assert sr.records_inserted == 0
        assert sr.records_skipped_duplicate == 1
        assert _count_rows(repo, "world_gold_prices") == 1


# ---------- Pipeline: FX Rate ----------


class TestPipelineFX:
    """FX rate storage."""

    FX_RECORDS: list[dict[str, Any]] = [
        {
            "base_currency": "USD",
            "target_currency": "VND",
            "rate": 24350.0,
            "recorded_at": "2026-07-24T00:00:00Z",
        },
    ]

    @pytest.fixture
    def pipe(self, repo: Repository) -> Pipeline:
        """Create a Pipeline backed by in-memory DB."""
        return Pipeline(repo)

    def test_inserts_record(self, pipe: Pipeline, repo: Repository) -> None:
        """FX rate record inserted."""
        result = CollectorResult(
            source="exchangerate.fun",
            collector_name="fx",
            success=True,
            data=self.FX_RECORDS,
        )
        sr = pipe.process(result)
        assert sr.records_inserted == 1
        assert _count_rows(repo, "exchange_rates") == 1

    def test_skips_duplicate(self, pipe: Pipeline, repo: Repository) -> None:
        """Duplicate FX rate skipped."""
        result = CollectorResult(
            source="exchangerate.fun",
            collector_name="fx",
            success=True,
            data=self.FX_RECORDS,
        )
        pipe.process(result)
        sr = pipe.process(result)
        assert sr.records_inserted == 0
        assert sr.records_skipped_duplicate == 1


# ---------- Pipeline: Edge Cases ----------


class TestPipelineEdgeCases:
    """Pipeline error handling."""

    def test_failed_collector_stores_nothing(self, repo: Repository) -> None:
        """Failed collector logs API call but stores no data."""
        pipe = Pipeline(repo)
        result = CollectorResult(
            source="xaus.com",
            collector_name="world",
            success=False,
            status_code=500,
            error_message="Server error",
        )
        sr = pipe.process(result)
        assert sr.records_inserted == 0
        assert sr.success is True  # pipeline itself succeeded
        # API log still written
        assert _count_rows(repo, "api_logs") == 1

    def test_unknown_collector_name(self, repo: Repository) -> None:
        """Unknown collector name returns error and logs API call."""
        pipe = Pipeline(repo)
        result = CollectorResult(
            source="unknown",
            collector_name="unknown",
            success=True,
            data=[{"foo": "bar"}],
        )
        sr = pipe.process(result)
        assert sr.success is False
        assert "No table mapping" in (sr.error_message or "")
        # API log still written
        assert _count_rows(repo, "api_logs") == 1

    def test_process_all_continues_on_error(self, repo: Repository) -> None:
        """process_all continues processing remaining collectors on error."""
        pipe = Pipeline(repo)
        results = [
            CollectorResult(
                source="unknown",
                collector_name="unknown",
                success=True,
                data=[{"foo": "bar"}],
            ),
            CollectorResult(
                source="exchangerate.fun",
                collector_name="fx",
                success=True,
                data=[
                    {
                        "base_currency": "USD",
                        "target_currency": "VND",
                        "rate": 24350.0,
                        "recorded_at": "2026-07-24T00:00:00Z",
                    }
                ],
            ),
        ]
        storage_results = pipe.process_all(results)
        # First should fail (unknown collector)
        assert storage_results[0].success is False
        # Second should succeed
        assert storage_results[1].success is True
        assert storage_results[1].records_inserted == 1
        assert _count_rows(repo, "exchange_rates") == 1
        # Both logged
        assert _count_rows(repo, "api_logs") == 2
