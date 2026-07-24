from __future__ import annotations

import logging
from typing import Any

from src.exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_response(raw: dict[str, Any]) -> bool:
    """Validate world gold API response structure.

    Args:
        raw: Raw JSON response from xaus.com.

    Returns:
        True if valid, False otherwise.
    """
    spot = raw.get("spot_usd_oz")
    if not isinstance(spot, (int, float)) or spot <= 0:
        logger.warning("Invalid spot_usd_oz: %s", spot)
        return False

    data_state = raw.get("data_state")
    if not isinstance(data_state, dict):
        logger.warning("Missing or invalid data_state")
        return False

    status = data_state.get("status")
    if status != "fresh":
        logger.warning("Data state not fresh: %s", status)
        return False

    updated_at = raw.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        logger.warning("Missing or invalid updated_at: %s", updated_at)
        return False

    return True


def parse_response(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse xaus.com API response into world gold record.

    Args:
        raw: Raw JSON response dict.

    Returns:
        List with one record dict, or empty list if invalid.

    Raises:
        ValidationError: If response structure is fundamentally broken.
    """
    if not isinstance(raw, dict):
        raise ValidationError(f"Expected dict, got {type(raw).__name__}")

    if not validate_response(raw):
        return []

    xau = raw.get("xau", {})
    currency = xau.get("currency", "USD") if isinstance(xau, dict) else "USD"
    unit = xau.get("unit", "troy_oz") if isinstance(xau, dict) else "troy_oz"

    record = {
        "source": "xaus.com",
        "spot_usd_oz": float(raw["spot_usd_oz"]),
        "per_gram_usd": float(raw["per_gram_usd"]) if raw.get("per_gram_usd") is not None else None,
        "per_kg_usd": float(raw["per_kg_usd"]) if raw.get("per_kg_usd") is not None else None,
        "currency": currency,
        "unit": unit,
        "recorded_at": raw["updated_at"],
    }

    return [record]
