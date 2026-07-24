from __future__ import annotations

from typing import Any

from src.collectors.base import BaseCollector
from src.parsers.domestic import parse_response


class DomesticCollector(BaseCollector):
    """Collects domestic Vietnamese gold prices from vang.today API.

    Fetches gold price data for 11 domestic brands across SJC, DOJI,
    Bao Tin, PNJ, VN Gold, and Viettin enterprises. Excludes XAUUSD
    (handled by WorldCollector).
    """

    source: str = "vang.today"
    endpoint: str = "https://www.vang.today/api/prices"
    collector_name: str = "domestic"
    timeout: int = 10
    max_retries: int = 3

    def parse(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse vang.today API response into gold price records.

        Args:
            raw: Raw JSON response.

        Returns:
            List of parsed record dicts.
        """
        return parse_response(raw)
