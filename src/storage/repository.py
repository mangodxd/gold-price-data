from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.exceptions import StorageError
from src.models import (
    ApiLog,
    ExchangeRate,
    GoldDailySummary,
    GoldPrice,
    WorldGoldDailySummary,
    WorldGoldPrice,
    create_tables,
)
from src.storage.connection import create_db_engine

MODEL_MAP: dict[str, type] = {
    "gold_prices": GoldPrice,
    "world_gold_prices": WorldGoldPrice,
    "exchange_rates": ExchangeRate,
    "gold_daily_summary": GoldDailySummary,
    "world_gold_daily_summary": WorldGoldDailySummary,
    "api_logs": ApiLog,
}


class Repository:
    """Storage layer for the Gold Market Pipeline.

    Provides idempotent insert, bulk insert, existence check,
    and latest-record lookup for all 6 database tables.

    Args:
        engine: Optional SQLAlchemy Engine. If None, creates one
            using the default database path.
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or create_db_engine()
        create_tables(self.engine)

    def create_or_ignore(self, table_name: str, data: dict[str, Any]) -> bool:
        """Insert a row, ignoring if a UNIQUE constraint violation occurs.

        Args:
            table_name: Name of the target table.
            data: Column-value mapping for the row.

        Returns:
            True if the row was inserted, False if ignored (duplicate).

        Raises:
            StorageError: If table_name is unknown.
        """
        model_class = MODEL_MAP.get(table_name)
        if model_class is None:
            raise StorageError(f"Unknown table: {table_name}")

        stmt = sqlite_insert(model_class).values(**data).on_conflict_do_nothing()

        with self.engine.begin() as conn:
            result = conn.execute(stmt)
            return result.rowcount > 0

    def bulk_insert(self, table_name: str, records: list[dict[str, Any]]) -> int:
        """Insert multiple rows, ignoring UNIQUE constraint violations.

        Args:
            table_name: Name of the target table.
            records: List of column-value mappings.

        Returns:
            Number of rows actually inserted.

        Raises:
            StorageError: If table_name is unknown.
        """
        model_class = MODEL_MAP.get(table_name)
        if model_class is None:
            raise StorageError(f"Unknown table: {table_name}")
        if not records:
            return 0

        stmt = sqlite_insert(model_class).on_conflict_do_nothing()

        with self.engine.begin() as conn:
            result = conn.execute(stmt, records)
            return result.rowcount

    def exists(self, table_name: str, conditions: dict[str, Any]) -> bool:
        """Check if a row matching all conditions exists.

        Args:
            table_name: Name of the target table.
            conditions: Column-value pairs for the WHERE clause (AND).

        Returns:
            True if at least one matching row exists.

        Raises:
            StorageError: If table_name is unknown.
        """
        model_class = MODEL_MAP.get(table_name)
        if model_class is None:
            raise StorageError(f"Unknown table: {table_name}")

        where_clauses = [f"{col} = :{col}" for col in conditions]
        where_sql = " AND ".join(where_clauses)
        sql = f"SELECT 1 FROM {table_name} WHERE {where_sql} LIMIT 1"

        with self.engine.begin() as conn:
            result = conn.execute(text(sql), conditions).fetchone()
            return result is not None

    def get_latest(
        self, table_name: str, filters: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Get the most recent row from a table, optionally filtered.

        Args:
            table_name: Name of the target table.
            filters: Optional column-value pairs for WHERE clause (AND).

        Returns:
            Row as a dictionary, or None if no matching row exists.

        Raises:
            StorageError: If table_name is unknown.
        """
        model_class = MODEL_MAP.get(table_name)
        if model_class is None:
            raise StorageError(f"Unknown table: {table_name}")

        where_sql = ""
        params: dict[str, Any] = {}
        if filters:
            where_clauses = [f"{col} = :{col}" for col in filters]
            where_sql = "WHERE " + " AND ".join(where_clauses)
            params = filters

        sql = f"SELECT * FROM {table_name} {where_sql} ORDER BY id DESC LIMIT 1"

        with self.engine.begin() as conn:
            row = conn.execute(text(sql), params).fetchone()
            if row is None:
                return None
            return dict(row._mapping)

    def log_api_call(
        self,
        collector_name: str,
        source: str,
        success: bool,
        status_code: int | None = None,
        response_time_ms: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record an API call result in the api_logs table.

        Args:
            collector_name: Name of the collector (e.g. 'domestic').
            source: Source URL or identifier.
            success: Whether the call succeeded.
            status_code: HTTP status code.
            response_time_ms: Response time in milliseconds.
            error_message: Error description if failed.
        """
        self.create_or_ignore(
            "api_logs",
            {
                "collector_name": collector_name,
                "source": source,
                "success": 1 if success else 0,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
                "error_message": error_message,
                "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    def get_raw_records_in_range(
        self,
        table_name: str,
        start_utc: str,
        end_utc: str,
    ) -> list[dict[str, Any]]:
        """Get all records from a table within a UTC time range.

        Args:
            table_name: Name of the target table.
            start_utc: Start of range (ISO 8601 UTC).
            end_utc: End of range (ISO 8601 UTC).

        Returns:
            List of row dicts ordered by recorded_at ASC.

        Raises:
            StorageError: If table_name is unknown.
        """
        model_class = MODEL_MAP.get(table_name)
        if model_class is None:
            raise StorageError(f"Unknown table: {table_name}")

        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"SELECT * FROM {table_name} "
                    "WHERE recorded_at BETWEEN :start AND :end "
                    "ORDER BY recorded_at ASC"
                ),
                {"start": start_utc, "end": end_utc},
            ).fetchall()
            return [dict(r._mapping) for r in rows]

    def is_stale(
        self,
        table_name: str,
        product_filter: dict[str, Any],
        current_buy: int,
        current_sell: int,
    ) -> bool:
        """Check if the latest record has identical prices (stale data).

        Used for domestic gold prices where we compare
        buy and sell prices.

        Args:
            table_name: Name of the target table.
            product_filter: Filter to identify the product
                (e.g. {'source': 'vang.today', 'product_name': 'SJL1L10'}).
            current_buy: Current buy price to compare.
            current_sell: Current sell price to compare.

        Returns:
            True if the latest record has the same buy AND sell prices.
        """
        latest = self.get_latest(table_name, product_filter)
        if latest is None:
            return False
        return latest.get("buy_price") == current_buy and latest.get("sell_price") == current_sell

    def is_value_stale(
        self,
        table_name: str,
        filters: dict[str, Any],
        column: str,
        current_value: int | float,
    ) -> bool:
        """Check if the latest record has the same value for a column (stale data).

        Used for world gold (spot_usd_oz) and FX (rate) where
        a single value determines staleness.

        Args:
            table_name: Name of the target table.
            filters: Filter to identify the record
                (e.g. {'source': 'xaus.com'}).
            column: Column name to compare.
            current_value: Current value to compare.

        Returns:
            True if the latest record has the same value.
        """
        latest = self.get_latest(table_name, filters)
        if latest is None:
            return False
        return float(latest.get(column, 0)) == float(current_value)
