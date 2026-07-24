from __future__ import annotations

from typing import Any

from src.collectors.base import BaseCollector
from src.parsers.world import parse_response


class WorldCollector(BaseCollector):
    """Collects XAU/USD spot price from xaus.com API.

    Stores spot price in USD per troy ounce with derived
    per-gram and per-kilogram values.
    """

    source: str = "xaus.com"
    endpoint: str = "https://xaus.com/api/v1/spot?compact=1"
    collector_name: str = "world"
    timeout: int = 10
    max_retries: int = 3

    def parse(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse xaus.com API response into world gold record.

        Args:
            raw: Raw JSON response.

        Returns:
            List with one record dict.
        """
        return parse_response(raw)
