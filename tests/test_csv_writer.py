"""Tests for the CSV export module."""

from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from src.export.csv_writer import _write_csv, export_daily_csvs
from src.storage.repository import Repository


class TestWriteCSV:
    """CSV file writing internals."""

    def test_writes_header_and_rows(self) -> None:
        """CSV file has BOM, correct header, and data rows."""
        with TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "test.csv"
            columns = ["name", "price"]
            rows = [
                {"name": "SJC", "price": 85500000},
                {"name": "PNJ", "price": 85000000},
            ]
            _write_csv(filepath, columns, rows)

            # Check BOM via raw bytes (utf-8-sig writes BOM on write
            # and strips it on read, so check raw bytes)
            with open(filepath, "rb") as f:
                raw = f.read(3)
            assert raw == b"\xef\xbb\xbf"

            # Read with utf-8-sig for DictReader (BOM stripped automatically)
            with open(filepath, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                assert reader.fieldnames == columns
                data = list(reader)
            assert len(data) == 2
            assert data[0]["name"] == "SJC"

    def test_empty_rows_produces_header_only(self) -> None:
        """No data rows produces header-only CSV."""
        with TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "empty.csv"
            columns = ["col_a", "col_b"]
            _write_csv(filepath, columns, [])

            # Check BOM via raw bytes
            with open(filepath, "rb") as f:
                raw = f.read(3)
            assert raw == b"\xef\xbb\xbf"

            # Read with utf-8-sig for DictReader (BOM stripped)
            with open(filepath, newline="", encoding="utf-8-sig") as f:
                content = f.read()
            assert "col_a" in content
            assert content.count("\n") == 1  # header only

    def test_missing_columns_filled_with_empty(self) -> None:
        """Missing columns in a row are filled with empty string."""
        with TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "partial.csv"
            columns = ["a", "b", "c"]
            rows = [{"a": "x", "c": "z"}]  # 'b' missing
            _write_csv(filepath, columns, rows)

            with open(filepath, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                row = next(reader)
                assert row["a"] == "x"
                assert row["b"] == ""
                assert row["c"] == "z"


class TestExportDailyCSVs:
    """Full CSV export against in-memory data."""

    def _seed_data(self, repo: Repository) -> None:
        """Insert sample data for all 3 tables."""
        repo.create_or_ignore(
            "gold_prices",
            {
                "source": "vang.today",
                "product_name": "SJL1L10",
                "buy_price": 85500000,
                "sell_price": 88000000,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )
        repo.create_or_ignore(
            "world_gold_prices",
            {
                "source": "xaus.com",
                "spot_usd_oz": 4061.7,
                "per_gram_usd": 130.59,
                "per_kg_usd": 130590.0,
                "currency": "USD",
                "unit": "troy_oz",
                "recorded_at": "2026-07-24T14:50:09.811Z",
            },
        )
        repo.create_or_ignore(
            "exchange_rates",
            {
                "base_currency": "USD",
                "target_currency": "VND",
                "rate": 24350.0,
                "recorded_at": "2026-07-24T00:00:00Z",
            },
        )

    def test_exports_three_files(self, repo: Repository) -> None:
        """Three CSV files created with data rows."""
        self._seed_data(repo)
        files = export_daily_csvs(repo, "2026-07-24")
        assert len(files) == 3

        # Verify file names
        names = [f.name for f in files]
        assert "gold_prices_2026-07-24.csv" in names
        assert "world_gold_prices_2026-07-24.csv" in names
        assert "exchange_rates_2026-07-24.csv" in names

        # Verify no id column in any file
        for filepath in files:
            with open(filepath, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                assert "id" not in (reader.fieldnames or [])

        # Cleanup
        for filepath in files:
            filepath.unlink()

    def test_exports_empty_tables(self, repo: Repository) -> None:
        """Empty tables produce header-only files."""
        files = export_daily_csvs(repo, "2026-07-24")
        for filepath in files:
            with open(filepath, newline="", encoding="utf-8-sig") as f:
                lines = f.readlines()
            assert len(lines) == 1  # header only
            filepath.unlink()
