from __future__ import annotations

import logging
from dataclasses import dataclass

from src.collectors.base import CollectorResult
from src.storage.repository import Repository

logger = logging.getLogger(__name__)

# Collector name → target DB table
COLLECTOR_TABLE_MAP: dict[str, str] = {
    "domestic": "gold_prices",
    "world": "world_gold_prices",
    "fx": "exchange_rates",
}


@dataclass
class StorageResult:
    """Result of persisting a single collector's data.

    Attributes:
        collector_name: Collector identifier.
        source: API source.
        success: Whether storage succeeded.
        records_inserted: Number of new records inserted.
        records_skipped_stale: Number of records skipped as stale.
        records_skipped_duplicate: Number of records skipped as duplicates.
        error_message: Error description if failed.
    """

    collector_name: str
    source: str
    success: bool
    records_inserted: int = 0
    records_skipped_stale: int = 0
    records_skipped_duplicate: int = 0
    error_message: str | None = None


class Pipeline:
    """Orchestrates collector results into persistent storage.

    Takes CollectorResult from each pipeline stage, maps to the
    correct database table, applies stale detection (domestic gold),
    bulk inserts, and logs API call results.

    Args:
        repository: Repository instance for DB access.
    """

    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def _log_api_call(self, result: CollectorResult) -> None:
        """Log collector API call result to api_logs table.

        Args:
            result: Collector result to log.
        """
        self.repository.log_api_call(
            collector_name=result.collector_name,
            source=result.source,
            success=result.success,
            status_code=result.status_code,
            response_time_ms=result.response_time_ms,
            error_message=result.error_message,
        )

    def _store_domestic(self, result: CollectorResult) -> StorageResult:
        """Store domestic gold data with stale detection per product.

        Args:
            result: Domestic collector result.

        Returns:
            StorageResult with insert counts.
        """
        inserted = 0
        skipped_stale = 0
        skipped_dup = 0

        for record in result.data:
            product_filter = {
                "source": "vang.today",
                "product_name": record["product_name"],
            }
            if self.repository.is_stale(
                "gold_prices",
                product_filter,
                current_buy=record["buy_price"],
                current_sell=record["sell_price"],
            ):
                skipped_stale += 1
                logger.info("Skipped stale data for %s", record["product_name"])
                continue

            if self.repository.create_or_ignore("gold_prices", record):
                inserted += 1
            else:
                skipped_dup += 1

        return StorageResult(
            collector_name=result.collector_name,
            source=result.source,
            success=True,
            records_inserted=inserted,
            records_skipped_stale=skipped_stale,
            records_skipped_duplicate=skipped_dup,
        )

    def _store_single_record(self, result: CollectorResult, table_name: str) -> StorageResult:
        """Store single-record collector data (world gold or FX).

        Args:
            result: Collector result.
            table_name: Target database table.

        Returns:
            StorageResult with insert counts.
        """
        inserted = 0
        skipped_dup = 0

        for record in result.data:
            if self.repository.create_or_ignore(table_name, record):
                inserted += 1
            else:
                skipped_dup += 1

        return StorageResult(
            collector_name=result.collector_name,
            source=result.source,
            success=True,
            records_inserted=inserted,
            records_skipped_duplicate=skipped_dup,
        )

    def process(self, result: CollectorResult) -> StorageResult:
        """Process a single collector result through the storage pipeline.

        1. Logs API call to api_logs
        2. Maps collector to target table
        3. If domestic: runs stale detection per product
        4. Bulk inserts records
        5. Returns storage summary

        Args:
            result: Collector result to persist.

        Returns:
            StorageResult with counts of inserted/skipped records.
        """
        # Always log API call
        self._log_api_call(result)

        # If collection failed, nothing to store
        if not result.success or not result.data:
            return StorageResult(
                collector_name=result.collector_name,
                source=result.source,
                success=True,
                records_inserted=0,
            )

        table_name = COLLECTOR_TABLE_MAP.get(result.collector_name)
        if table_name is None:
            logger.warning("Unknown collector: %s — no table mapping", result.collector_name)
            return StorageResult(
                collector_name=result.collector_name,
                source=result.source,
                success=False,
                error_message=f"No table mapping for {result.collector_name}",
            )

        if result.collector_name == "domestic":
            return self._store_domestic(result)
        return self._store_single_record(result, table_name)

    def process_all(self, results: list[CollectorResult]) -> list[StorageResult]:
        """Process multiple collector results.

        Each result is processed independently — one collector
        failure does not affect others.

        Args:
            results: List of collector results.

        Returns:
            List of storage results, one per collector.
        """
        return [self.process(r) for r in results]
