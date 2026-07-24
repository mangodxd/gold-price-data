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

UTC_2024_11_24 = datetime(2024, 11, 24, 13, 59, 49, tzinfo=UTC)

SAMPLE_VALID_ITEM = {
    "type_code": "SJL1L10",
    "buy": 85500000,
    "sell": 88000000,
    "change_buy": 100000,
    "change_sell": 100000,
    "update_time": 1732456789,
}

SAMPLE_RESPONSE = {
    "success": True,
    "current_time": 1732456789,
    "data": [
        SAMPLE_VALID_ITEM,
        {
            "type_code": "SJ9999",
            "buy": 85000000,
            "sell": 87500000,
            "change_buy": 0,
            "change_sell": 50000,
            "update_time": 1732456789,
        },
    ],
}


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
        assert validate_item(SAMPLE_VALID_ITEM) is True

    def test_excluded_xauusd(self) -> None:
        """XAUUSD should be rejected."""
        item = dict(SAMPLE_VALID_ITEM)
        item["type_code"] = "XAUUSD"
        assert validate_item(item) is False

    def test_buy_price_zero(self) -> None:
        """Zero buy price should be rejected."""
        item = dict(SAMPLE_VALID_ITEM)
        item["buy"] = 0
        assert validate_item(item) is False

    def test_sell_price_negative(self) -> None:
        """Negative sell price should be rejected."""
        item = dict(SAMPLE_VALID_ITEM)
        item["sell"] = -1
        assert validate_item(item) is False

    def test_sell_less_than_buy(self) -> None:
        """Sell < buy should be rejected."""
        item = dict(SAMPLE_VALID_ITEM)
        item["sell"] = 10000
        item["buy"] = 20000
        assert validate_item(item) is False

    def test_invalid_timestamp(self) -> None:
        """Missing update_time should be rejected."""
        item = dict(SAMPLE_VALID_ITEM)
        item.pop("update_time")
        assert validate_item(item) is False


class TestParseTimestamp:
    """Unix timestamp to ISO 8601 conversion."""

    def test_valid_timestamp(self) -> None:
        """Valid Unix timestamp converts to ISO 8601."""
        expected = UTC_2024_11_24.isoformat()
        assert parse_timestamp(1732456789) == expected


class TestParseItem:
    """Single item parsing."""

    def test_parse_valid_item(self) -> None:
        """Valid item produces correct record dict."""
        result = parse_item(SAMPLE_VALID_ITEM)
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
        assert parse_item(item) is None


class TestParseResponse:
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

    def test_empty_data(self) -> None:
        """Empty data array returns empty list."""
        resp = dict(SAMPLE_RESPONSE)
        resp["data"] = []
        assert parse_response(resp) == []

    def test_missing_data_key(self) -> None:
        """Missing data key returns empty list."""
        resp = dict(SAMPLE_RESPONSE)
        resp.pop("data")
        assert parse_response(resp) == []

    def test_all_items_fail_validation(self) -> None:
        """When all items invalid, return empty list."""
        resp = dict(SAMPLE_RESPONSE)
        resp["data"] = [
            {"type_code": "XAUUSD", "buy": 85000, "sell": 86000, "update_time": 1732456789},
        ]
        assert parse_response(resp) == []

    def test_partial_failure(self) -> None:
        """Invalid items are skipped, valid ones returned."""
        resp = dict(SAMPLE_RESPONSE)
        resp["data"] = [
            SAMPLE_VALID_ITEM,
            {"type_code": "BAD", "buy": 0, "sell": 0, "update_time": 0},
        ]
        records = parse_response(resp)
        assert len(records) == 1
        assert records[0]["product_name"] == "SJL1L10"
