"""OHLC + StdDev analytics computation.

Computes per-product daily OHLC, average price, volatility,
and population standard deviation from tick data.
Runs daily at 00:05 UTC+7 for the previous Vietnam calendar day.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from src.storage.repository import Repository

logger = logging.getLogger(__name__)

VIETNAM_TZ = timezone(timedelta(hours=7))


def vietnam_date_boundary(target_date: str) -> tuple[str, str]:
    """Convert a Vietnam date string to UTC start/end timestamps.

    A Vietnam day 2026-07-24 runs from 2026-07-23 17:00:00 UTC
    to 2026-07-24 16:59:59 UTC.

    Args:
        target_date: Date string in YYYY-MM-DD format (Vietnam timezone).

    Returns:
        Tuple of (start_of_day, end_of_day) as ISO 8601 UTC strings.
    """
    dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=VIETNAM_TZ)
    start_utc = dt.astimezone(UTC).isoformat()
    end_dt = dt.replace(hour=23, minute=59, second=59, microsecond=0)
    end_utc = end_dt.astimezone(UTC).isoformat()
    return start_utc, end_utc


def yesterday_vietnam() -> str:
    """Get yesterday's date in Vietnam timezone (YYYY-MM-DD).

    Returns:
        Date string in YYYY-MM-DD format.
    """
    today_utc = datetime.now(UTC)
    today_vn = today_utc.astimezone(VIETNAM_TZ)
    yesterday_vn = today_vn - timedelta(days=1)
    return yesterday_vn.strftime("%Y-%m-%d")


def compute_ohlc(prices: list[float]) -> dict[str, float | None]:
    """Compute OHLC + StdDev from a list of prices.

    Args:
        prices: Chronologically ordered list of prices.

    Returns:
        Dict with keys: opening, closing, highest, lowest,
        average, volatility, stddev.
        Returns None-valued fields if prices is empty.
    """
    if not prices:
        return {
            "opening": None,
            "closing": None,
            "highest": None,
            "lowest": None,
            "average": None,
            "volatility": None,
            "stddev": None,
        }

    opening = prices[0]
    closing = prices[-1]
    highest = max(prices)
    lowest = min(prices)
    avg = sum(prices) / len(prices)

    if closing == 0:
        volatility = None
    else:
        volatility = (highest - lowest) / closing * 100

    if len(prices) == 1:
        stddev = 0.0
    else:
        variance = sum((p - avg) ** 2 for p in prices) / len(prices)  # population
        stddev = math.sqrt(variance)

    return {
        "opening": opening,
        "closing": closing,
        "highest": highest,
        "lowest": lowest,
        "average": avg,
        "volatility": volatility,
        "stddev": stddev,
    }


def compute_domestic_summary(repo: Repository, target_date: str | None = None) -> int:
    """Compute daily OHLC + StdDev for domestic gold.

    Args:
        repo: Repository instance.
        target_date: Vietnam date string (YYYY-MM-DD). Defaults to yesterday.

    Returns:
        Number of products summarized.
    """
    if target_date is None:
        target_date = yesterday_vietnam()

    start_utc, end_utc = vietnam_date_boundary(target_date)

    raw = repo.get_raw_records_in_range("gold_prices", start_utc, end_utc)
    if not raw:
        logger.info("No domestic gold data for %s — skipping (may be weekend/holiday)", target_date)
        return 0

    # Group by product_name, preserving order
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in raw:
        name = row["product_name"]
        if name not in groups:
            groups[name] = []
        groups[name].append(row)

    records_inserted = 0
    for product_name, rows in groups.items():
        prices = [r["buy_price"] for r in rows]
        ohlc = compute_ohlc(prices)
        if ohlc["opening"] is None:
            continue

        record = {
            "date": target_date,
            "product_name": product_name,
            "opening_price": int(ohlc["opening"]),
            "closing_price": int(ohlc["closing"]),
            "highest_price": int(ohlc["highest"]),
            "lowest_price": int(ohlc["lowest"]),
            "average_price": ohlc["average"],
            "volatility": ohlc["volatility"],
            "stddev": ohlc["stddev"],
            "total_ticks": len(prices),
            "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        if repo.create_or_ignore("gold_daily_summary", record):
            records_inserted += 1

    logger.info(
        "Domestic summary for %s: %d products summarized",
        target_date,
        records_inserted,
    )
    return records_inserted


def compute_world_summary(repo: Repository, target_date: str | None = None) -> bool:
    """Compute daily OHLC + StdDev for world gold.

    Args:
        repo: Repository instance.
        target_date: Vietnam date string (YYYY-MM-DD). Defaults to yesterday.

    Returns:
        True if a summary row was inserted, False if no data.
    """
    if target_date is None:
        target_date = yesterday_vietnam()

    start_utc, end_utc = vietnam_date_boundary(target_date)

    raw = repo.get_raw_records_in_range("world_gold_prices", start_utc, end_utc)
    if not raw:
        logger.info("No world gold data for %s — skipping (may be weekend/holiday)", target_date)
        return False

    prices = [r["spot_usd_oz"] for r in raw]
    ohlc = compute_ohlc(prices)
    if ohlc["opening"] is None:
        return False

    record = {
        "date": target_date,
        "opening_price": ohlc["opening"],
        "closing_price": ohlc["closing"],
        "highest_price": ohlc["highest"],
        "lowest_price": ohlc["lowest"],
        "average_price": ohlc["average"],
        "volatility": ohlc["volatility"],
        "stddev": ohlc["stddev"],
        "total_ticks": len(prices),
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if repo.create_or_ignore("world_gold_daily_summary", record):
        logger.info("World gold summary for %s: inserted", target_date)
        return True

    logger.info("World gold summary for %s: already exists", target_date)
    return False


def run_analytics(repo: Repository | None = None, target_date: str | None = None) -> None:
    """Run full analytics pipeline for a given date.

    Computes domestic and world gold summaries.

    Args:
        repo: Repository instance. If None, creates a new one.
        target_date: Vietnam date string (YYYY-MM-DD). Defaults to yesterday.
    """
    if repo is None:
        repo = Repository()

    domestic_count = compute_domestic_summary(repo, target_date)
    world_inserted = compute_world_summary(repo, target_date)

    logger.info(
        "Analytics complete: domestic=%d products, world=%s",
        domestic_count,
        "inserted" if world_inserted else "no data",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_analytics()
