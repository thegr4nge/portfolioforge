"""Pydantic data models for all database table row types.

Each model mirrors the column names of its corresponding SQLite table exactly.
Models are frozen (immutable) to prevent accidental mutation after construction.
Used by DatabaseWriter for upsert binding and by adapters for typed return values.
"""

from pydantic import BaseModel, ConfigDict


class OHLCVRecord(BaseModel):
    """Row model for the ohlcv table."""

    model_config = ConfigDict(frozen=True)

    security_id: int
    date: str  # ISO 8601: YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float
    adj_factor: float = 1.0
    quality_flags: int = 0


class DividendRecord(BaseModel):
    """Row model for the dividends table."""

    model_config = ConfigDict(frozen=True)

    security_id: int
    ex_date: str  # ISO 8601
    pay_date: str | None = None
    record_date: str | None = None
    declared_date: str | None = None
    amount: float
    currency: str = "USD"
    dividend_type: str = "CD"
    franking_credit_pct: float | None = None
    franking_credit_amount: float | None = None
    gross_amount: float | None = None


class SplitRecord(BaseModel):
    """Row model for the splits table."""

    model_config = ConfigDict(frozen=True)

    security_id: int
    ex_date: str  # ISO 8601
    split_from: float
    split_to: float


class FXRateRecord(BaseModel):
    """Row model for the fx_rates table."""

    model_config = ConfigDict(frozen=True)

    date: str  # ISO 8601
    from_ccy: str
    to_ccy: str = "USD"
    rate: float


class SecurityRecord(BaseModel):
    """Row model for the securities table."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    name: str | None = None
    exchange: str
    currency: str = "USD"
    sector: str | None = None
    industry: str | None = None
    is_active: int = 1
    listed_date: str | None = None
    delisted_date: str | None = None


class IngestionLogRecord(BaseModel):
    """Row model for the ingestion_log table."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    data_type: str
    from_date: str | None = None
    to_date: str | None = None
    records_written: int | None = None
    status: str
    error_message: str | None = None


class CoverageRecord(BaseModel):
    """Row model for the ingestion_coverage table."""

    model_config = ConfigDict(frozen=True)

    security_id: int
    data_type: str
    source: str
    from_date: str
    to_date: str
    records: int
