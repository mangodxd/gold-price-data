from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.analytics.ohlc import (
    compute_domestic_summary,
    compute_ohlc,
    compute_world_summary,
    vietnam_date_boundary,
    yesterday_vietnam,
)
from src.storage.repository import Repository

VIETNAM_TZ = timezone(timedelta(hours=7))
NOW_UTC = datetime(2026, 7, 25, 0, 0, 0, tzinfo=UTC)
YESTERDAY_VN = "2026-07-24"


# ---------- OHLC Computation ----------


class TestComputeOHLC:
    """OHLC + StdDev computation from price lists."""

    def test_empty_list(self) -> None:
        """Empty price list returns None for all fields."""
        result = compute_ohlc([])
        assert result["opening"] is None
        assert result["closing"] is None
        assert result["stddev"] is None

    def test_single_price(self) -> None:
        """Single price: all OHLC same, stddev 0."""
        result = compute_ohlc([100.0])
        assert result["opening"] == 100.0
        assert result["closing"] == 100.0
        assert result["highest"] == 100.0
        assert result["lowest"] == 100.0
        assert result["average"] == 100.0
        assert result["stddev"] == 0.0

    def test_known_sequence(self) -> None:
        """Known price sequence produces correct OHLC + stddev."""
        prices = [100.0, 102.0, 101.0, 105.0, 103.0]
        result = compute_ohlc(prices)
        assert result["opening"] == 100.0
        assert result["closing"] == 103.0
        assert result["highest"] == 105.0
        assert result["lowest"] == 100.0
        assert result["average"] == 102.2  # (100+102+101+105+103)/5
        # population stddev
        mean = 102.2
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        expected_stddev = math.sqrt(variance)
        assert result["stddev"] == pytest.approx(expected_stddev)
        # volatility = (105 - 100) / 103 * 100
        expected_vol = (105.0 - 100.0) / 103.0 * 100
        assert result["volatility"] == pytest.approx(expected_vol)

    def test_volatility_zero_on_constant(self) -> None:
        """Constant prices produce 0 volatility."""
        result = compute_ohlc([100.0, 100.0, 100.0])
        assert result["volatility"] == 0.0
        assert result["stddev"] == 0.0

    def test_population_stddev(self) -> None:
        """StdDev uses population formula (N not N-1)."""
        prices = [10.0, 12.0, 14.0]
        result = compute_ohlc(prices)
        # population: sqrt(((10-12)^2 + (12-12)^2 + (14-12)^2) / 3)
        # = sqrt((4 + 0 + 4) / 3) = sqrt(8/3) = 1.63299
        assert result["stddev"] == pytest.approx(math.sqrt(8 / 3))


# ---------- Date Boundary ----------


class TestDateBoundary:
    """Vietnam date to UTC range conversion."""

    def test_vietnam_date(self) -> None:
        """2026-07-24 Vietnam = 2026-07-23 17:00 UTC to 2026-07-24 16:59 UTC."""
        start, end = vietnam_date_boundary("2026-07-24")
        assert start == "2026-07-23T17:00:00+00:00"
        assert end == "2026-07-24T16:59:59+00:00"

    def test_yesterday_format(self) -> None:
        """yesterday_vietnam returns YYYY-MM-DD format."""
        date_str = yesterday_vietnam()
        assert len(date_str) == 10
        assert date_str.count("-") == 2


# ---------- Domestic Summary ----------


class TestDomesticSummary:
    """Domestic gold daily summary computation."""

    def _insert_tick(self, repo: Repository, product: str, price: int, recorded_at: str) -> None:
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": product,
                "buy_price": price,
                "sell_price": price + 100000,
                "category": None,
                "purity": None,
                "recorded_at": recorded_at,
            },
        )

    def test_computes_summary(self, repo: Repository) -> None:
        """Summary computed for one product with multiple ticks."""
        self._insert_tick(repo, "SJL1L10", 85500000, "2026-07-24T00:00:00Z")
        self._insert_tick(repo, "SJL1L10", 85600000, "2026-07-24T00:05:00Z")
        self._insert_tick(repo, "SJL1L10", 85700000, "2026-07-24T00:10:00Z")
        compute_domestic_summary(repo, "2026-07-24")
        assert repo.exists("gold_daily_summary", {"date": "2026-07-24"})
        # Verify total_ticks
        latest = repo.get_latest(
            "gold_daily_summary",
            {"date": "2026-07-24", "product_name": "SJL1L10"},
        )
        assert latest is not None
        assert latest["total_ticks"] == 3

    def test_multiple_products(self, repo: Repository) -> None:
        """Multiple products each get a summary row."""
        self._insert_tick(repo, "SJL1L10", 85500000, "2026-07-24T00:00:00Z")
        self._insert_tick(repo, "SJ9999", 85000000, "2026-07-24T00:00:00Z")
        count = compute_domestic_summary(repo, "2026-07-24")
        assert count == 2
        latest = repo.get_latest(
            "gold_daily_summary",
            {"date": "2026-07-24", "product_name": "SJL1L10"},
        )
        assert latest is not None
        assert latest["total_ticks"] == 1

    def test_empty_day_returns_zero(self, repo: Repository) -> None:
        """No data for date returns 0."""
        count = compute_domestic_summary(repo, "2026-07-24")
        assert count == 0

    def test_single_tick(self, repo: Repository) -> None:
        """Single tick produces valid summary."""
        self._insert_tick(repo, "SJL1L10", 85500000, "2026-07-24T00:00:00Z")
        count = compute_domestic_summary(repo, "2026-07-24")
        assert count == 1
        latest = repo.get_latest(
            "gold_daily_summary",
            {"date": "2026-07-24", "product_name": "SJL1L10"},
        )
        assert latest is not None
        assert latest["total_ticks"] == 1

    def test_ohlc_values_correct(self, repo: Repository) -> None:
        """OHLC values computed correctly for known sequence."""
        self._insert_tick(repo, "SJL1L10", 85500000, "2026-07-24T00:00:00Z")
        self._insert_tick(repo, "SJL1L10", 85700000, "2026-07-24T00:05:00Z")
        self._insert_tick(repo, "SJL1L10", 85600000, "2026-07-24T00:10:00Z")
        self._insert_tick(repo, "SJL1L10", 85800000, "2026-07-24T00:15:00Z")
        compute_domestic_summary(repo, "2026-07-24")
        latest = repo.get_latest("gold_daily_summary", {"date": "2026-07-24"})
        assert latest is not None
        assert latest["opening_price"] == 85500000
        assert latest["closing_price"] == 85800000
        assert latest["highest_price"] == 85800000
        assert latest["lowest_price"] == 85500000
        assert latest["average_price"] == pytest.approx(85650000.0)
        assert latest["total_ticks"] == 4


# ---------- World Summary ----------


class TestWorldSummary:
    """World gold daily summary computation."""

    def _insert_tick(self, repo: Repository, price: float, recorded_at: str) -> None:
        repo.create_or_ignore(
            "world_gold_prices",
            {
                "source": "xaus.com",
                "spot_usd_oz": price,
                "per_gram_usd": price / 31.1035,
                "per_kg_usd": price / 31.1035 * 1000,
                "currency": "USD",
                "unit": "troy_oz",
                "recorded_at": recorded_at,
            },
        )

    def test_computes_summary(self, repo: Repository) -> None:
        """World gold summary computed."""
        self._insert_tick(repo, 4061.7, "2026-07-24T14:00:00Z")
        self._insert_tick(repo, 4062.5, "2026-07-24T14:05:00Z")
        assert compute_world_summary(repo, "2026-07-24") is True
        latest = repo.get_latest("world_gold_daily_summary", {"date": "2026-07-24"})
        assert latest is not None
        assert latest["total_ticks"] == 2

    def test_empty_day(self, repo: Repository) -> None:
        """No data returns False."""
        assert compute_world_summary(repo, "2026-07-24") is False

    def test_ohlc_values(self, repo: Repository) -> None:
        """OHLC values correct."""
        self._insert_tick(repo, 4060.0, "2026-07-24T14:00:00Z")
        self._insert_tick(repo, 4065.0, "2026-07-24T14:05:00Z")
        self._insert_tick(repo, 4062.0, "2026-07-24T14:10:00Z")
        compute_world_summary(repo, "2026-07-24")
        latest = repo.get_latest("world_gold_daily_summary", {"date": "2026-07-24"})
        assert latest is not None
        assert latest["opening_price"] == 4060.0
        assert latest["closing_price"] == 4062.0
        assert latest["highest_price"] == 4065.0
        assert latest["lowest_price"] == 4060.0
        assert latest["total_ticks"] == 3
