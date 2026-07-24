"""Daily CSV export for gold market data.

Exports a single combined snapshot CSV per run:
- snapshot_YYYY-MM-DD_HHMM.csv

Contains data from all 3 tables (gold_prices, world_gold_prices, exchange_rates)
in one file with a table column to identify the source.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.analytics.ohlc import today_vietnam, vietnam_date_boundary
from src.storage.repository import Repository

logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "exports"

SNAPSHOT_COLUMNS = [
    "table",
    "type",
    "buy",
    "sell",
    "spot",
    "rate",
    "currency",
    "unit",
    "recorded_at",
]


def _write_csv(filepath: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    """Write rows to a CSV file with header.

    Args:
        filepath: Output file path.
        columns: Ordered column names for header.
        rows: List of row dicts.
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def export_snapshot(repo: Repository, target_date: str | None = None) -> Path:
    """Export a single combined CSV snapshot of all 3 data tables.

    Args:
        repo: Repository instance.
        target_date: Vietnam date string (YYYY-MM-DD). Defaults to today.

    Returns:
        Path to the written snapshot file.
    """
    if target_date is None:
        target_date = os.environ.get("TARGET_DATE") or today_vietnam()

    start_utc, end_utc = vietnam_date_boundary(target_date)

    gold_rows = repo.get_raw_records_in_range("gold_prices", start_utc, end_utc)
    world_rows = repo.get_raw_records_in_range("world_gold_prices", start_utc, end_utc)
    fx_rows = repo.get_raw_records_in_range("exchange_rates", start_utc, end_utc)

    combined: list[dict[str, Any]] = []

    for r in gold_rows:
        combined.append(
            {
                "table": "gold",
                "type": r.get("product_name", ""),
                "buy": r.get("buy_price", ""),
                "sell": r.get("sell_price", ""),
                "spot": "",
                "rate": "",
                "currency": "",
                "unit": "",
                "recorded_at": r.get("recorded_at", ""),
            }
        )

    for r in world_rows:
        combined.append(
            {
                "table": "world",
                "type": "XAU",
                "buy": "",
                "sell": "",
                "spot": r.get("spot_usd_oz", ""),
                "rate": "",
                "currency": r.get("currency", ""),
                "unit": r.get("unit", ""),
                "recorded_at": r.get("recorded_at", ""),
            }
        )

    for r in fx_rows:
        combined.append(
            {
                "table": "fx",
                "type": "USD/VND",
                "buy": "",
                "sell": "",
                "spot": "",
                "rate": r.get("rate", ""),
                "currency": "",
                "unit": "",
                "recorded_at": r.get("recorded_at", ""),
            }
        )

    now = datetime.now(UTC)
    timestamp = now.strftime("%Y%m%d_%H%M")
    filename = f"snapshot_{timestamp}.csv"
    filepath = EXPORT_DIR / filename
    _write_csv(filepath, SNAPSHOT_COLUMNS, combined)
    logger.info(
        "Exported snapshot %s: %d rows (%d gold, %d world, %d fx)",
        filename,
        len(combined),
        len(gold_rows),
        len(world_rows),
        len(fx_rows),
    )
    return filepath
