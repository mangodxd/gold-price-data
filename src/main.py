"""Gold Market Pipeline orchestrator.

Entry point for the data collection pipeline. Creates collectors,
runs them in parallel via asyncio.gather, persists results via
the Pipeline/Repository layer, and reports summary statistics.

Modes:
  collect    — run all 3 collectors, store results (default)
  analytics  — compute OHLC + StdDev, export CSVs
  export     — export daily CSVs only

Usage:
  python src/main.py                  # collect mode
  python src/main.py analytics        # analytics mode
  python src/main.py export           # export mode only
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from src.collectors.domestic import DomesticCollector
from src.collectors.fx import FXCollector
from src.collectors.world import WorldCollector
from src.storage.connection import create_db_engine
from src.storage.pipeline import Pipeline
from src.storage.repository import Repository

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Configure basic logging with ISO 8601 timestamps."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _make_collectors() -> list[Any]:
    """Create all collector instances.

    Returns:
        List of collector instances.
    """
    return [DomesticCollector(), WorldCollector(), FXCollector()]


async def _run_collectors(
    collectors: list[Any],
) -> list[Any]:
    """Run all collectors in parallel.

    Each collector runs independently — one failure doesn't
    affect others. Results are returned in the same order
    as the input collectors list.

    Args:
        collectors: List of collector instances.

    Returns:
        List of CollectorResult objects.
    """
    tasks = [c.collect() for c in collectors]
    return await asyncio.gather(*tasks)


def _print_summary(results: list[Any], storage_results: list[Any]) -> None:
    """Print a human-readable summary of the pipeline run.

    Args:
        results: List of CollectorResult objects.
        storage_results: List of StorageResult objects.
    """
    for coll_result, stor_result in zip(results, storage_results, strict=True):
        status = "OK" if coll_result.success else "FAIL"
        inserted = stor_result.records_inserted
        stale = stor_result.records_skipped_stale
        dup = stor_result.records_skipped_duplicate
        ms = coll_result.response_time_ms or 0
        logger.info(
            "%s [%s] %s: inserted=%d stale=%d dup=%d %dms",
            status,
            coll_result.collector_name,
            coll_result.source,
            inserted,
            stale,
            dup,
            ms,
        )


def run_collect() -> int:
    """Execute the collection pipeline.

    Creates collectors, runs them in parallel, stores results,
    and returns an exit code.

    Returns:
        0 if at least one collector succeeded, 1 if all failed.
    """
    _setup_logging()
    logger.info("Starting collection run at %s", datetime.now(UTC).isoformat())

    engine = create_db_engine()
    repo = Repository(engine=engine)
    pipeline = Pipeline(repo)
    collectors = _make_collectors()
    start = datetime.now(UTC)

    results = asyncio.run(_run_collectors(collectors))
    storage_results = pipeline.process_all(results)

    elapsed = (datetime.now(UTC) - start).total_seconds()
    _print_summary(results, storage_results)

    any_success = any(r.success for r in results)
    if any_success:
        logger.info(
            "Collection complete in %.2fs — %d/%d collectors succeeded",
            elapsed,
            sum(1 for r in results if r.success),
            len(results),
        )
        return 0
    logger.error("Collection complete in %.2fs — ALL collectors failed", elapsed)
    return 1


def run_analytics() -> int:
    """Execute the analytics pipeline (OHLC computation only).

    Delegates to src.analytics.ohlc.run_analytics() for OHLC
    computation. No CSV export — use run_export() for that.

    Returns:
        0 on success, 1 on failure.
    """
    _setup_logging()
    engine = create_db_engine()
    repo = Repository(engine=engine)

    from src.analytics.ohlc import run_analytics as _run_analytics_core

    _run_analytics_core(repo=repo)

    return 0


def run_export() -> int:
    """Export a single combined CSV snapshot of all 3 data tables.

    Returns:
        0 on success, 1 on failure.
    """
    _setup_logging()

    engine = create_db_engine()
    repo = Repository(engine=engine)

    from src.export.csv_writer import export_snapshot as _export_snapshot

    path = _export_snapshot(repo)
    logger.info("Exported snapshot: %s", path.name)
    return 0


def main() -> int:
    """Parse command-line argument and dispatch to the correct mode.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    mode = "collect"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    if mode == "analytics":
        return run_analytics()
    if mode == "export":
        return run_export()

    if mode != "collect":
        logger.warning("Unknown mode '%s' — falling back to collect", mode)

    return run_collect()


if __name__ == "__main__":
    sys.exit(main())
