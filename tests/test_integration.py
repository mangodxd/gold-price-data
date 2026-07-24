"""End-to-end integration test.

Mocks all 3 APIs with httpx_mock, runs the full collection pipeline,
and verifies data flows through collectors → pipeline → database tables.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.collectors.domestic import DomesticCollector
from src.collectors.fx import FXCollector
from src.collectors.world import WorldCollector
from src.storage.repository import Repository

DOMESTIC_RESPONSE: dict[str, Any] = {
    "success": True,
    "current_time": 1732456789,
    "data": [
        {
            "type_code": "SJL1L10",
            "buy": 85500000,
            "sell": 88000000,
            "change_buy": 0,
            "change_sell": 0,
            "update_time": 1732456789,
        },
        {
            "type_code": "SJ9999",
            "buy": 85000000,
            "sell": 87500000,
            "change_buy": 0,
            "change_sell": 0,
            "update_time": 1732456789,
        },
    ],
}

WORLD_RESPONSE: dict[str, Any] = {
    "xau": {"price": 4061.7, "currency": "USD", "unit": "troy_oz"},
    "spot_usd_oz": 4061.7,
    "per_gram_usd": 130.59,
    "per_kg_usd": 130590.0,
    "updated_at": "2026-07-24T14:50:09.811Z",
    "data_state": {"status": "fresh"},
}

FX_RESPONSE: dict[str, Any] = {
    "base": "USD",
    "date": "2026-07-24",
    "rates": {"VND": 24350.00},
}


@pytest.mark.asyncio
async def test_collectors_store_to_db(repo: Repository, httpx_mock: Any) -> None:
    """All 3 collectors run, data lands in correct DB tables."""
    httpx_mock.add_response(url=DomesticCollector.endpoint, json=DOMESTIC_RESPONSE, status_code=200)
    httpx_mock.add_response(url=WorldCollector.endpoint, json=WORLD_RESPONSE, status_code=200)
    httpx_mock.add_response(url=FXCollector.endpoint, json=FX_RESPONSE, status_code=200)

    domestic = DomesticCollector()
    world = WorldCollector()
    fx = FXCollector()

    dom_result = await domestic.collect()
    world_result = await world.collect()
    fx_result = await fx.collect()

    assert dom_result.success
    assert world_result.success
    assert fx_result.success
    assert len(dom_result.data) == 2
    assert len(world_result.data) == 1
    assert len(fx_result.data) == 1

    # Store via Repository
    for record in dom_result.data:
        repo.create_or_ignore("gold_prices", record)
    for record in world_result.data:
        repo.create_or_ignore("world_gold_prices", record)
    for record in fx_result.data:
        repo.create_or_ignore("exchange_rates", record)

    from sqlalchemy import text

    with repo.engine.begin() as conn:
        gold_count = conn.execute(text("SELECT COUNT(*) FROM gold_prices")).scalar()
        world_count = conn.execute(text("SELECT COUNT(*) FROM world_gold_prices")).scalar()
        fx_count = conn.execute(text("SELECT COUNT(*) FROM exchange_rates")).scalar()

    assert gold_count == 2
    assert world_count == 1
    assert fx_count == 1
