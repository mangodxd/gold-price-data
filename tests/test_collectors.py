from __future__ import annotations

from typing import Any

import pytest

from src.collectors.base import CollectorResult
from src.collectors.domestic import DomesticCollector
from src.collectors.fx import FXCollector
from src.collectors.world import WorldCollector

# ---------- Base Collector Tests ----------


class TestBaseCollector:
    """Base collector error handling and retry."""

    def test_collector_result_defaults(self) -> None:
        """CollectorResult default values should be correct."""
        result = CollectorResult(
            source="test",
            collector_name="test",
            success=True,
        )
        assert result.status_code is None
        assert result.response_time_ms is None
        assert result.data == []
        assert result.error_message is None


# ---------- Domestic Collector Tests ----------


class TestDomesticCollector:
    """Domestic collector with mocked HTTP."""

    SAMPLE_RESPONSE: dict[str, Any] = {
        "success": True,
        "current_time": 1732456789,
        "data": [
            {
                "type_code": "SJL1L10",
                "buy": 85500000,
                "sell": 88000000,
                "change_buy": 100000,
                "change_sell": 100000,
                "update_time": 1732456789,
            },
            {
                "type_code": "SJ9999",
                "buy": 85000000,
                "sell": 87500000,
                "change_buy": 0,
                "change_sell": 50000,
                "update_time": 1732456789,
            },
        ],
    }

    @pytest.fixture
    def collector(self) -> DomesticCollector:
        """Create a DomesticCollector instance."""
        return DomesticCollector()

    def test_parse(self, collector: DomesticCollector) -> None:
        """Parse should return 2 records from sample response."""
        records = collector.parse(self.SAMPLE_RESPONSE)
        assert len(records) == 2
        assert records[0]["product_name"] == "SJL1L10"
        assert records[1]["product_name"] == "SJ9999"
        assert records[0]["buy_price"] == 85500000
        assert records[1]["sell_price"] == 87500000

    def test_validate_passes_valid(self, collector: DomesticCollector) -> None:
        """Validate should pass valid records."""
        records = collector.parse(self.SAMPLE_RESPONSE)
        valid = collector.validate(records)
        assert len(valid) == 2

    @pytest.mark.asyncio
    async def test_collect_with_mock_success(
        self, collector: DomesticCollector, httpx_mock: Any
    ) -> None:
        """Collect should return successful result with data on 200."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json=self.SAMPLE_RESPONSE,
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert result.status_code == 200
        assert len(result.data) == 2
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_collect_with_mock_500_then_success(
        self, collector: DomesticCollector, httpx_mock: Any
    ) -> None:
        """Collect should retry on 500 and succeed on second attempt."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json={},
            status_code=500,
        )
        httpx_mock.add_response(
            url=collector.endpoint,
            json=self.SAMPLE_RESPONSE,
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_collect_with_mock_404(
        self, collector: DomesticCollector, httpx_mock: Any
    ) -> None:
        """Collect should fail fast on 404 (no retry)."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json={},
            status_code=404,
        )
        result = await collector.collect()
        assert result.success is False
        assert result.data == []

    @pytest.mark.asyncio
    async def test_collect_with_mock_empty_data(
        self, collector: DomesticCollector, httpx_mock: Any
    ) -> None:
        """Collect with empty data array returns no data."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json={"success": True, "current_time": 1732456789, "data": []},
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert result.data == []


# ---------- World Collector Tests ----------

WORLD_SAMPLE: dict[str, Any] = {
    "xau": {"price": 4061.7, "currency": "USD", "unit": "troy_oz"},
    "spot_usd_oz": 4061.7,
    "per_gram_usd": 130.59,
    "per_kg_usd": 130590.0,
    "updated_at": "2026-07-24T14:50:09.811Z",
    "data_state": {"status": "fresh"},
}


class TestWorldCollector:
    """World gold (xaus.com) collector with mocked HTTP."""

    @pytest.fixture
    def collector(self) -> WorldCollector:
        """Create a WorldCollector instance."""
        return WorldCollector()

    def test_parse(self, collector: WorldCollector) -> None:
        """Parse should return 1 record from sample response."""
        records = collector.parse(WORLD_SAMPLE)
        assert len(records) == 1
        assert records[0]["source"] == "xaus.com"
        assert records[0]["spot_usd_oz"] == 4061.7

    def test_validate_passes_valid(self, collector: WorldCollector) -> None:
        """Validate should pass valid records."""
        records = collector.parse(WORLD_SAMPLE)
        valid = collector.validate(records)
        assert len(valid) == 1

    @pytest.mark.asyncio
    async def test_collect_with_mock_success(
        self, collector: WorldCollector, httpx_mock: Any
    ) -> None:
        """Collect should return successful result with data on 200."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json=WORLD_SAMPLE,
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert result.status_code == 200
        assert len(result.data) == 1
        assert result.data[0]["spot_usd_oz"] == 4061.7

    @pytest.mark.asyncio
    async def test_collect_with_stale_data(
        self, collector: WorldCollector, httpx_mock: Any
    ) -> None:
        """Stale data_state returns no data."""
        stale = dict(WORLD_SAMPLE)
        stale["data_state"] = {"status": "stale"}
        httpx_mock.add_response(
            url=collector.endpoint,
            json=stale,
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_collect_with_mock_500_then_success(
        self, collector: WorldCollector, httpx_mock: Any
    ) -> None:
        """Collect should retry on 500 and succeed."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json={},
            status_code=500,
        )
        httpx_mock.add_response(
            url=collector.endpoint,
            json=WORLD_SAMPLE,
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert len(result.data) == 1


# ---------- FX Collector Tests ----------

FX_SAMPLE: dict[str, Any] = {
    "base": "USD",
    "date": "2026-07-24",
    "rates": {"VND": 24350.00},
}


class TestFXCollector:
    """FX rate (exchangerate.fun) collector with mocked HTTP."""

    @pytest.fixture
    def collector(self) -> FXCollector:
        """Create an FXCollector instance."""
        return FXCollector()

    def test_parse(self, collector: FXCollector) -> None:
        """Parse should return 1 record from sample response."""
        records = collector.parse(FX_SAMPLE)
        assert len(records) == 1
        assert records[0]["base_currency"] == "USD"
        assert records[0]["rate"] == 24350.00

    def test_validate_passes_valid(self, collector: FXCollector) -> None:
        """Validate should pass valid records."""
        records = collector.parse(FX_SAMPLE)
        valid = collector.validate(records)
        assert len(valid) == 1

    @pytest.mark.asyncio
    async def test_collect_with_mock_success(self, collector: FXCollector, httpx_mock: Any) -> None:
        """Collect should return successful result with data on 200."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json=FX_SAMPLE,
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert result.status_code == 200
        assert len(result.data) == 1
        assert result.data[0]["rate"] == 24350.00

    @pytest.mark.asyncio
    async def test_collect_with_missing_vnd(self, collector: FXCollector, httpx_mock: Any) -> None:
        """Missing VND rate returns no data."""
        bad = dict(FX_SAMPLE)
        bad["rates"] = {}
        httpx_mock.add_response(
            url=collector.endpoint,
            json=bad,
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert result.data == []

    @pytest.mark.asyncio
    async def test_collect_with_mock_404(self, collector: FXCollector, httpx_mock: Any) -> None:
        """Collect should fail fast on 404."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json={},
            status_code=404,
        )
        result = await collector.collect()
        assert result.success is False

    @pytest.mark.asyncio
    async def test_collect_with_mock_500_then_success(
        self, collector: FXCollector, httpx_mock: Any
    ) -> None:
        """Collect should retry on 500 and succeed."""
        httpx_mock.add_response(
            url=collector.endpoint,
            json={},
            status_code=500,
        )
        httpx_mock.add_response(
            url=collector.endpoint,
            json=FX_SAMPLE,
            status_code=200,
        )
        result = await collector.collect()
        assert result.success is True
        assert len(result.data) == 1
