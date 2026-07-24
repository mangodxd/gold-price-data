"""Tests for the main.py orchestrator entry point."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.collectors.base import CollectorResult
from src.main import _make_collectors, run_collect


class TestMakeCollectors:
    """Collector instantiation."""

    def test_returns_three_collectors(self) -> None:
        """_make_collectors returns 3 collector instances."""
        collectors = _make_collectors()
        assert len(collectors) == 3
        names = [c.collector_name for c in collectors]
        assert "domestic" in names
        assert "world" in names
        assert "fx" in names


class TestRunCollect:
    """Collection orchestration."""

    DOMESTIC_SUCCESS = CollectorResult(
        source="vang.today",
        collector_name="domestic",
        success=True,
        status_code=200,
        response_time_ms=150,
        data=[
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        ],
    )

    WORLD_SUCCESS = CollectorResult(
        source="xaus.com",
        collector_name="world",
        success=True,
        status_code=200,
        response_time_ms=100,
        data=[
            {
                "source": "xaus.com",
                "spot_usd_oz": 4061.7,
                "per_gram_usd": 130.59,
                "per_kg_usd": 130590.0,
                "currency": "USD",
                "unit": "troy_oz",
                "recorded_at": "2026-07-24T14:50:09.811Z",
            },
        ],
    )

    FX_SUCCESS = CollectorResult(
        source="exchangerate.fun",
        collector_name="fx",
        success=True,
        status_code=200,
        response_time_ms=80,
        data=[
            {
                "base_currency": "USD",
                "target_currency": "VND",
                "rate": 24350.0,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        ],
    )

    @pytest.fixture(autouse=True)
    def _mock_collectors(self) -> Any:
        """Mock all 3 collectors to return success without HTTP calls."""
        patcher = patch(
            "src.main._run_collectors",
            new=AsyncMock(
                return_value=[
                    self.DOMESTIC_SUCCESS,
                    self.WORLD_SUCCESS,
                    self.FX_SUCCESS,
                ]
            ),
        )
        patcher.start()
        yield
        patcher.stop()

    def test_run_collect_returns_zero(self) -> None:
        """run_collect returns 0 on success."""
        exit_code = run_collect()
        assert exit_code == 0


class TestRunCollectAllFail:
    """All collectors fail scenario."""

    @pytest.fixture(autouse=True)
    def _mock_all_fail(self) -> Any:
        """Mock all collectors to fail."""
        patcher = patch(
            "src.main._run_collectors",
            new=AsyncMock(
                return_value=[
                    CollectorResult(
                        source="vang.today",
                        collector_name="domestic",
                        success=False,
                        status_code=500,
                        error_message="Server error",
                    ),
                    CollectorResult(
                        source="xaus.com",
                        collector_name="world",
                        success=False,
                        status_code=503,
                        error_message="Unavailable",
                    ),
                    CollectorResult(
                        source="exchangerate.fun",
                        collector_name="fx",
                        success=False,
                        status_code=500,
                        error_message="Timeout",
                    ),
                ]
            ),
        )
        patcher.start()
        yield
        patcher.stop()

    def test_returns_one_when_all_fail(self) -> None:
        """run_collect returns 1 when all collectors fail."""
        exit_code = run_collect()
        assert exit_code == 1


class TestRunCollectPartialFail:
    """Partial collector failure."""

    DOMESTIC_FAIL = CollectorResult(
        source="vang.today",
        collector_name="domestic",
        success=False,
        status_code=500,
        error_message="Server error",
    )
    WORLD_OK = CollectorResult(
        source="xaus.com",
        collector_name="world",
        success=True,
        status_code=200,
        response_time_ms=100,
        data=[
            {"source": "xaus.com", "spot_usd_oz": 4061.7, "recorded_at": "2026-07-24T14:50:09.811Z"}
        ],
    )

    @pytest.fixture(autouse=True)
    def _mock_partial(self) -> Any:
        """Mock domestic fail, world + fx succeed."""
        patcher = patch(
            "src.main._run_collectors",
            new=AsyncMock(
                return_value=[
                    self.DOMESTIC_FAIL,
                    self.WORLD_OK,
                    CollectorResult(
                        source="exchangerate.fun",
                        collector_name="fx",
                        success=True,
                        status_code=200,
                        response_time_ms=80,
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
            ),
        )
        patcher.start()
        yield
        patcher.stop()

    def test_returns_zero_on_partial(self) -> None:
        """run_collect returns 0 if any collector succeeded."""
        exit_code = run_collect()
        assert exit_code == 0
