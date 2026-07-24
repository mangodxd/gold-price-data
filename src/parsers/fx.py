from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_response(raw: dict[str, Any]) -> bool:
    """Validate FX rate API response structure.

    Args:
        raw: Raw JSON response from exchangerate.fun.

    Returns:
        True if valid, False otherwise.
    """
    rates = raw.get("rates")
    if not isinstance(rates, dict):
        logger.warning("Missing or invalid 'rates' object")
        return False

    vnd_rate = rates.get("VND")
    if not isinstance(vnd_rate, (int, float)) or vnd_rate <= 0:
        logger.warning("Invalid or missing rates.VND: %s", vnd_rate)
        return False

    base = raw.get("base")
    if base != "USD":
        logger.warning("Unexpected base currency: %s", base)

    return True


def parse_response(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse exchangerate.fun API response into FX rate record.

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

    record = {
        "base_currency": raw.get("base", "USD"),
        "target_currency": "VND",
        "rate": float(raw["rates"]["VND"]),
        "recorded_at": datetime.now(UTC).isoformat(),
    }

    return [record]
