"""Daily CSV export for gold market data.

Exports three CSV files per day:
- gold_prices_YYYY-MM-DD.csv
- world_gold_prices_YYYY-MM-DD.csv
- exchange_rates_YYYY-MM-DD.csv

Files named by Vietnam date (UTC+7), written to exports/ directory.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from src.analytics.ohlc import vietnam_date_boundary, yesterday_vietnam
from src.storage.repository import Repository

logger = logging.getLogger(__name__)

EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "exports"

TABLE_CONFIG: list[dict[str, Any]] = [
    {
        "table": "gold_prices",
        "filename_template": "gold_prices_{date}.csv",
        "columns": [
            "id",
            "source",
            "product_name",
            "category",
            "purity",
            "buy_price",
            "sell_price",
            "recorded_at",
            "created_at",
        ],
    },
    {
        "table": "world_gold_prices",
        "filename_template": "world_gold_prices_{date}.csv",
        "columns": [
            "id",
            "source",
            "spot_usd_oz",
            "per_gram_usd",
            "per_kg_usd",
            "currency",
            "unit",
            "recorded_at",
            "created_at",
        ],
    },
    {
        "table": "exchange_rates",
        "filename_template": "exchange_rates_{date}.csv",
        "columns": [
            "id",
            "base_currency",
            "target_currency",
            "rate",
            "recorded_at",
            "created_at",
        ],
    },
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


def export_daily_csvs(repo: Repository, target_date: str | None = None) -> list[Path]:
    """Export daily CSV files for all three data tables.

    Args:
        repo: Repository instance.
        target_date: Vietnam date string (YYYY-MM-DD). Defaults to yesterday.

    Returns:
        List of file paths that were written.
    """
    if target_date is None:
        target_date = yesterday_vietnam()

    start_utc, end_utc = vietnam_date_boundary(target_date)
    written: list[Path] = []

    for cfg in TABLE_CONFIG:
        filename = cfg["filename_template"].format(date=target_date)
        filepath = EXPORT_DIR / filename

        rows = repo.get_raw_records_in_range(cfg["table"], start_utc, end_utc)
        _write_csv(filepath, cfg["columns"], rows)
        written.append(filepath)

        logger.info("Exported %s: %d rows", filename, len(rows))

    return written
