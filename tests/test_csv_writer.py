"""Tests for the CSV export module."""

from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from src.export.csv_writer import SNAPSHOT_COLUMNS, _write_csv, export_snapshot
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

            with open(filepath, "rb") as f:
                raw = f.read(3)
            assert raw == b"\xef\xbb\xbf"

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

            with open(filepath, "rb") as f:
                raw = f.read(3)
            assert raw == b"\xef\xbb\xbf"

            with open(filepath, newline="", encoding="utf-8-sig") as f:
                content = f.read()
            assert "col_a" in content
            assert content.count("\n") == 1  # header only

    def test_missing_columns_filled_with_empty(self) -> None:
        """Missing columns in a row are filled with empty string."""
        with TemporaryDirectory() as tmp:
            filepath = Path(tmp) / "partial.csv"
            columns = ["a", "b", "c"]
            rows = [{"a": "x", "c": "z"}]
            _write_csv(filepath, columns, rows)

            with open(filepath, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                row = next(reader)
                assert row["a"] == "x"
                assert row["b"] == ""
                assert row["c"] == "z"


class TestExportSnapshot:
    """Combined snapshot CSV export."""

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

    def test_snapshot_contains_all_tables(self, repo: Repository) -> None:
        """Snapshot includes rows from all 3 tables with correct table labels."""
        self._seed_data(repo)
        path = export_snapshot(repo, "2026-07-24")

        assert path.name.startswith("snapshot_")
        assert path.suffix == ".csv"

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == SNAPSHOT_COLUMNS
            rows = list(reader)

        assert len(rows) == 3  # 1 gold + 1 world + 1 fx

        tables = {r["table"] for r in rows}
        assert tables == {"gold", "world", "fx"}

        # Check gold row
        gold = [r for r in rows if r["table"] == "gold"][0]
        assert gold["type"] == "SJL1L10"
        assert gold["buy"] == "85500000"
        assert gold["sell"] == "88000000"

        # Check world row
        world = [r for r in rows if r["table"] == "world"][0]
        assert world["spot"] == "4061.7"
        assert world["currency"] == "USD"

        # Check fx row
        fx = [r for r in rows if r["table"] == "fx"][0]
        assert fx["rate"] == "24350.0"

        path.unlink()

    def test_snapshot_empty_day(self, repo: Repository) -> None:
        """Empty day produces header-only file."""
        path = export_snapshot(repo, "2026-07-24")
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 0
        path.unlink()
