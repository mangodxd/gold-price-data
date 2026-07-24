from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Float, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class GoldPrice(Base):
    """Domestic gold price record from vang.today API."""

    __tablename__ = "gold_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="vang.today")
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    purity: Mapped[str | None] = mapped_column(Text, nullable=True)
    buy_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sell_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text,
        default=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    __table_args__ = (
        UniqueConstraint(
            "source", "product_name", "recorded_at", name="uq_gold_prices_source_product_recorded"
        ),
    )


class WorldGoldPrice(Base):
    """World gold (XAU/USD) spot price record from xaus.com API."""

    __tablename__ = "world_gold_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="xaus.com")
    spot_usd_oz: Mapped[float] = mapped_column(Float, nullable=False)
    per_gram_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    per_kg_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    unit: Mapped[str] = mapped_column(Text, nullable=False, default="oz")
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text,
        default=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    __table_args__ = (
        UniqueConstraint("source", "recorded_at", name="uq_world_gold_source_recorded"),
    )


class ExchangeRate(Base):
    """VND/USD exchange rate record from exchangerate.fun API."""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    target_currency: Mapped[str] = mapped_column(Text, nullable=False, default="VND")
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(
        Text,
        default=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    __table_args__ = (
        UniqueConstraint(
            "base_currency",
            "target_currency",
            "recorded_at",
            name="uq_exchange_rates_currencies_recorded",
        ),
    )


class GoldDailySummary(Base):
    """Per-product daily OHLC + StdDev for domestic gold."""

    __tablename__ = "gold_daily_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    opening_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    closing_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    highest_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lowest_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    average_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    stddev: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_ticks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(
        Text,
        default=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    __table_args__ = (
        UniqueConstraint("date", "product_name", name="uq_gold_daily_summary_date_product"),
    )


class WorldGoldDailySummary(Base):
    """Daily OHLC + StdDev for XAU/USD."""

    __tablename__ = "world_gold_daily_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, nullable=False)
    opening_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    highest_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    lowest_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    stddev: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_ticks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(
        Text,
        default=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    __table_args__ = (UniqueConstraint("date", name="uq_world_gold_daily_summary_date"),)


class ApiLog(Base):
    """Execution log entry for collector runs."""

    __tablename__ = "api_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collector_name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(
        Text,
        default=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def create_tables(engine):
    """Create all tables if they don't exist (idempotent).

    Args:
        engine: SQLAlchemy engine instance.
    """
    Base.metadata.create_all(engine)
