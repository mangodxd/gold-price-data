from __future__ import annotations

from typing import Any

import pytest

from src.collectors.base import CollectorResult
from src.collectors.domestic import DomesticCollector


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

    def test_validate_returns_all(self, collector: DomesticCollector) -> None:
        """Validate returns all items (filtering done in parse layer)."""
        records = collector.parse(self.SAMPLE_RESPONSE)
        valid = collector.validate(records)
        assert len(valid) == 2  # same as parsed

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

    @pytest.mark.asyncio
    async def test_source_and_collector_name(self, collector: DomesticCollector) -> None:
        """Source and collector_name should be set correctly."""
        assert collector.source == "vang.today"
        assert collector.collector_name == "domestic"
