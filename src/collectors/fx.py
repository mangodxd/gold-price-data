from __future__ import annotations

from typing import Any

from src.collectors.base import BaseCollector
from src.parsers.fx import parse_response


class FXCollector(BaseCollector):
    """Collects VND/USD exchange rate from exchangerate.fun API."""

    source: str = "exchangerate.fun"
    endpoint: str = "https://api.exchangerate.fun/latest?base=USD"
    collector_name: str = "fx"
    timeout: int = 10
    max_retries: int = 3

    def parse(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse exchangerate.fun API response into FX rate record.

        Args:
            raw: Raw JSON response.

        Returns:
            List with one record dict.
        """
        return parse_response(raw)
