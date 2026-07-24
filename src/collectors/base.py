from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from src.exceptions import CollectorError, FetchError

logger = logging.getLogger(__name__)

BASE_DELAY = 1.0
BACKOFF_FACTOR = 2.0
MAX_RETRIES = 3


@dataclass
class CollectorResult:
    """Result from a collector run.

    Attributes:
        source: Source identifier (e.g. 'vang.today').
        collector_name: Collector name (e.g. 'domestic').
        success: Whether collection succeeded.
        status_code: HTTP status code.
        response_time_ms: Response time in milliseconds.
        data: Parsed and validated records.
        error_message: Error description if failed.
    """

    source: str
    collector_name: str
    success: bool
    status_code: int | None = None
    response_time_ms: int | None = None
    data: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None


class BaseCollector(ABC):
    """Abstract base for all gold price collectors.

    Subclasses must implement fetch(), parse(), and validate().
    The collect() template method orchestrates fetch -> parse -> validate
    with retry logic and timing.

    Attributes:
        source: API source identifier.
        endpoint: API endpoint URL.
        timeout: HTTP request timeout in seconds.
        max_retries: Number of retry attempts.
    """

    source: str = ""
    endpoint: str = ""
    timeout: int = 10
    max_retries: int = MAX_RETRIES
    collector_name: str = ""

    @abstractmethod
    def parse(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse raw API response into a list of record dicts.

        Args:
            raw: Raw JSON response.

        Returns:
            List of parsed record dicts.
        """

    @abstractmethod
    def validate(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate parsed records, filtering out invalid ones.

        Args:
            items: Parsed records from parse().

        Returns:
            List of valid record dicts.
        """

    async def _fetch_with_retry(self, client: httpx.AsyncClient) -> dict[str, Any]:
        """Fetch with exponential backoff retry.

        Args:
            client: Shared httpx async client.

        Returns:
            Raw JSON response.

        Raises:
            FetchError: After all retries exhausted.
        """
        last_error: Exception | None = None
        delay = BASE_DELAY

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(self.endpoint, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "%s attempt %d/%d timed out",
                    self.source,
                    attempt,
                    self.max_retries,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    last_error = e
                    logger.warning(
                        "%s attempt %d/%d got %d",
                        self.source,
                        attempt,
                        self.max_retries,
                        e.response.status_code,
                    )
                else:
                    raise FetchError(f"{self.source} returned {e.response.status_code}: {e}") from e
            except httpx.HTTPError as e:
                last_error = e
                logger.warning(
                    "%s attempt %d/%d failed: %s",
                    self.source,
                    attempt,
                    self.max_retries,
                    e,
                )

            if attempt < self.max_retries:
                await asyncio.sleep(delay)
                delay *= BACKOFF_FACTOR

        raise FetchError(f"{self.source} failed after {self.max_retries} retries") from last_error

    async def collect(self) -> CollectorResult:
        """Run the full collect pipeline: fetch -> parse -> validate.

        Returns:
            CollectorResult with status, timing, data, and errors.
        """
        start = datetime.now(UTC)
        status_code: int | None = None
        error_message: str | None = None
        data: list[dict[str, Any]] = []
        success = False

        try:
            async with httpx.AsyncClient() as client:
                raw = await self._fetch_with_retry(client)
                status_code = 200
                parsed = self.parse(raw)
                data = self.validate(parsed)
                if not data:
                    logger.warning("%s: all parsed items failed validation", self.source)
                success = True
        except FetchError as e:
            error_message = str(e)
            logger.error("%s fetch failed: %s", self.source, e)
        except CollectorError as e:
            error_message = str(e)
            logger.error("%s collector error: %s", self.source, e)
        except Exception as e:
            error_message = f"Unexpected error: {e}"
            logger.exception("%s unexpected error: %s", self.source, e)

        elapsed = datetime.now(UTC) - start
        response_time_ms = int(elapsed.total_seconds() * 1000)

        return CollectorResult(
            source=self.source,
            collector_name=self.collector_name,
            success=success,
            status_code=status_code,
            response_time_ms=response_time_ms,
            data=data,
            error_message=error_message,
        )
