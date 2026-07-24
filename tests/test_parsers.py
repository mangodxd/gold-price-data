from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.exceptions import ValidationError
from src.parsers.domestic import (
    infer_category,
    parse_item,
    parse_response,
    parse_timestamp,
    validate_item,
)
from src.parsers.fx import parse_response as fx_parse
from src.parsers.world import parse_response as world_parse

UTC_2024_11_24 = datetime(2024, 11, 24, 13, 59, 49, tzinfo=UTC)

# New API format: prices is a dict keyed by type_code
# with top-level timestamp instead of per-item update_time
SAMPLE_VALID_ITEM = {
    "name": "SJC 1L 10L",
    "buy": 85500000,
    "sell": 88000000,
    "change_buy": 100000,
    "change_sell": 100000,
    "currency": "VND",
}

SAMPLE_RESPONSE = {
    "success": True,
    "timestamp": 1732456789,
    "prices": {
        "SJL1L10": SAMPLE_VALID_ITEM,
        "SJ9999": {
            "name": "SJC Ring",
            "buy": 85000000,
            "sell": 87500000,
            "change_buy": 0,
            "change_sell": 50000,
            "currency": "VND",
        },
    },
}

# ---------- Domestic Gold Parser Tests ----------


class TestInferCategory:
    """Category inference from type code."""

    def test_sjc_ring(self) -> None:
        """SJ9999 should be VANG NHAN."""
        assert infer_category("SJ9999") == "VÀNG NHẪN"

    def test_sjc_mieng(self) -> None:
        """SJL1L10 should be VANG MIENG."""
        assert infer_category("SJL1L10") == "VÀNG MIẾNG"

    def test_doji_hanoi(self) -> None:
        """DOHNL should be VANG MIENG."""
        assert infer_category("DOHNL") == "VÀNG MIẾNG"

    def test_doji_jewelry(self) -> None:
        """DOJINHTV should be VANG TRANG SUC."""
        assert infer_category("DOJINHTV") == "VÀNG TRANG SỨC"

    def test_pnj_24k(self) -> None:
        """PQHN24NTT should be VANG NHAN."""
        assert infer_category("PQHN24NTT") == "VÀNG NHẪN"

    def test_unknown_prefix(self) -> None:
        """Unknown prefix should return None."""
        assert infer_category("ZZ1234") is None


class TestValidateItem:
    """Item validation rules."""

    def test_valid_item(self) -> None:
        """Valid item passes validation."""
        assert validate_item("SJL1L10", SAMPLE_VALID_ITEM) is True

    def test_excluded_xauusd(self) -> None:
        """XAUUSD should be rejected."""
        assert validate_item("XAUUSD", SAMPLE_VALID_ITEM) is False

    def test_buy_price_zero(self) -> None:
        """Zero buy price should be rejected."""
        item = dict(SAMPLE_VALID_ITEM)
        item["buy"] = 0
        assert validate_item("SJL1L10", item) is False

    def test_sell_price_negative(self) -> None:
        """Negative sell price should be rejected."""
        item = dict(SAMPLE_VALID_ITEM)
        item["sell"] = -1
        assert validate_item("SJL1L10", item) is False

    def test_sell_less_than_buy(self) -> None:
        """Sell < buy should be rejected."""
        item = dict(SAMPLE_VALID_ITEM)
        item["sell"] = 10000
        item["buy"] = 20000
        assert validate_item("SJL1L10", item) is False


class TestParseTimestamp:
    """Unix timestamp to ISO 8601 conversion."""

    def test_valid_timestamp(self) -> None:
        """Valid Unix timestamp converts to ISO 8601."""
        expected = UTC_2024_11_24.isoformat()
        assert parse_timestamp(1732456789) == expected


class TestParseItem:
    """Single item parsing."""

    TIMESTAMP = 1732456789

    def test_parse_valid_item(self) -> None:
        """Valid item produces correct record dict."""
        result = parse_item("SJL1L10", SAMPLE_VALID_ITEM, self.TIMESTAMP)
        assert result is not None
        assert result["source"] == "vang.today"
        assert result["product_name"] == "SJL1L10"
        assert result["buy_price"] == 85500000
        assert result["sell_price"] == 88000000
        assert result["category"] == "VÀNG MIẾNG"
        assert result["purity"] is None

    def test_parse_invalid_item(self) -> None:
        """Invalid item returns None."""
        item = dict(SAMPLE_VALID_ITEM)
        item["buy"] = 0
        assert parse_item("SJL1L10", item, self.TIMESTAMP) is None


class TestDomesticParseResponse:
    """Full response parsing."""

    def test_full_response(self) -> None:
        """Valid response returns parsed records."""
        records = parse_response(SAMPLE_RESPONSE)
        assert len(records) == 2
        assert records[0]["product_name"] == "SJL1L10"
        assert records[1]["product_name"] == "SJ9999"

    def test_success_false_raises(self) -> None:
        """Response with success=false should raise."""
        resp = dict(SAMPLE_RESPONSE)
        resp["success"] = False
        with pytest.raises(ValidationError):
            parse_response(resp)

    def test_empty_prices(self) -> None:
        """Empty prices dict returns empty list."""
        resp = dict(SAMPLE_RESPONSE)
        resp["prices"] = {}
        assert parse_response(resp) == []

    def test_missing_prices_key(self) -> None:
        """Missing prices key returns empty list."""
        resp = dict(SAMPLE_RESPONSE)
        resp.pop("prices")
        assert parse_response(resp) == []

    def test_all_items_fail_validation(self) -> None:
        """When all items invalid, return empty list."""
        resp = dict(SAMPLE_RESPONSE)
        resp["prices"] = {
            "XAUUSD": {"name": "World Gold", "buy": 85000, "sell": 86000, "currency": "USD"},
        }
        assert parse_response(resp) == []

    def test_partial_failure(self) -> None:
        """Invalid items are skipped, valid ones returned."""
        resp = dict(SAMPLE_RESPONSE)
        resp["prices"] = {
            "SJL1L10": SAMPLE_VALID_ITEM,
            "BAD": {"name": "Bad Item", "buy": 0, "sell": 0, "currency": "VND"},
        }
        records = parse_response(resp)
        assert len(records) == 1
        assert records[0]["product_name"] == "SJL1L10"


# ---------- World Gold Parser Tests ----------

WORLD_SAMPLE = {
    "xau": {"price": 4061.7, "currency": "USD", "unit": "troy_oz"},
    "spot_usd_oz": 4061.7,
    "per_gram_usd": 130.59,
    "per_kg_usd": 130590.0,
    "updated_at": "2026-07-24T14:50:09.811Z",
    "data_state": {"status": "fresh"},
}


class TestWorldParser:
    """World gold (xaus.com) parser tests."""

    def test_valid_response(self) -> None:
        """Valid response returns one record."""
        records = world_parse(WORLD_SAMPLE)
        assert len(records) == 1
        assert records[0]["source"] == "xaus.com"
        assert records[0]["spot_usd_oz"] == 4061.7
        assert records[0]["per_gram_usd"] == 130.59
        assert records[0]["currency"] == "USD"
        assert records[0]["unit"] == "troy_oz"

    def test_stale_data_skipped(self) -> None:
        """Stale data_state returns empty list."""
        resp = dict(WORLD_SAMPLE)
        resp["data_state"] = {"status": "stale"}
        assert world_parse(resp) == []

    def test_unavailable_data_skipped(self) -> None:
        """Unavailable data_state returns empty list."""
        resp = dict(WORLD_SAMPLE)
        resp["data_state"] = {"status": "unavailable"}
        assert world_parse(resp) == []

    def test_missing_data_state(self) -> None:
        """Missing data_state returns empty list."""
        resp = dict(WORLD_SAMPLE)
        resp.pop("data_state")
        assert world_parse(resp) == []

    def test_negative_spot_price(self) -> None:
        """Negative spot price returns empty list."""
        resp = dict(WORLD_SAMPLE)
        resp["spot_usd_oz"] = -1
        assert world_parse(resp) == []

    def test_missing_spot_usd_oz(self) -> None:
        """Missing spot_usd_oz returns empty list."""
        resp = dict(WORLD_SAMPLE)
        resp.pop("spot_usd_oz")
        assert world_parse(resp) == []

    def test_optional_per_kg_none(self) -> None:
        """per_kg_usd can be None."""
        resp = dict(WORLD_SAMPLE)
        resp["per_kg_usd"] = None
        records = world_parse(resp)
        assert records[0]["per_kg_usd"] is None

    def test_not_a_dict_raises(self) -> None:
        """Non-dict input raises ValidationError."""
        with pytest.raises(ValidationError):
            world_parse("not a dict")  # type: ignore[arg-type]


# ---------- FX Rate Parser Tests ----------

FX_SAMPLE = {
    "base": "USD",
    "date": "2026-07-24",
    "rates": {"VND": 24350.00},
}


class TestFXParser:
    """FX rate (exchangerate.fun) parser tests."""

    def test_valid_response(self) -> None:
        """Valid response returns one record."""
        records = fx_parse(FX_SAMPLE)
        assert len(records) == 1
        assert records[0]["base_currency"] == "USD"
        assert records[0]["target_currency"] == "VND"
        assert records[0]["rate"] == 24350.00

    def test_missing_vnd_rate(self) -> None:
        """Missing rates.VND returns empty list."""
        resp = dict(FX_SAMPLE)
        resp["rates"] = {}
        assert fx_parse(resp) == []

    def test_zero_rate(self) -> None:
        """Zero rate returns empty list."""
        resp = dict(FX_SAMPLE)
        resp["rates"] = {"VND": 0}
        assert fx_parse(resp) == []

    def test_negative_rate(self) -> None:
        """Negative rate returns empty list."""
        resp = dict(FX_SAMPLE)
        resp["rates"] = {"VND": -1}
        assert fx_parse(resp) == []

    def test_missing_rates_key(self) -> None:
        """Missing rates key returns empty list."""
        resp = dict(FX_SAMPLE)
        resp.pop("rates")
        assert fx_parse(resp) == []

    def test_not_a_dict_raises(self) -> None:
        """Non-dict input raises ValidationError."""
        with pytest.raises(ValidationError):
            fx_parse([])  # type: ignore[arg-type]
