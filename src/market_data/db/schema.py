"""SQLite database schema and migration runner for market-data.

Uses PRAGMA user_version for migration tracking. Each migration is a complete
SQL script applied via executescript(). Migrations are idempotent — running
twice on the same DB produces no errors.
"""

import sqlite3

from loguru import logger

# Migrations list: each entry is a SQL script applied once in order.
# Migration index N corresponds to schema version N+1.
MIGRATIONS: list[str] = [
    # Migration 0 → version 1: create all tables
    """
    CREATE TABLE IF NOT EXISTS securities (
        id            INTEGER PRIMARY KEY,
        ticker        TEXT    NOT NULL UNIQUE,
        name          TEXT,
        exchange      TEXT    NOT NULL,
        sector        TEXT,
        industry      TEXT,
        currency      TEXT    NOT NULL DEFAULT 'USD',
        is_active     INTEGER NOT NULL DEFAULT 1,
        listed_date   TEXT,
        delisted_date TEXT,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS ohlcv (
        id            INTEGER PRIMARY KEY,
        security_id   INTEGER NOT NULL REFERENCES securities(id),
        date          TEXT    NOT NULL,
        open          REAL    NOT NULL,
        high          REAL    NOT NULL,
        low           REAL    NOT NULL,
        close         REAL    NOT NULL,
        volume        INTEGER NOT NULL,
        adj_close     REAL    NOT NULL,
        adj_factor    REAL    NOT NULL DEFAULT 1.0,
        quality_flags INTEGER NOT NULL DEFAULT 0,
        UNIQUE(security_id, date)
    );

    CREATE INDEX IF NOT EXISTS idx_ohlcv_security_date
        ON ohlcv(security_id, date);

    CREATE TABLE IF NOT EXISTS dividends (
        id                    INTEGER PRIMARY KEY,
        security_id           INTEGER NOT NULL REFERENCES securities(id),
        ex_date               TEXT    NOT NULL,
        pay_date              TEXT,
        record_date           TEXT,
        declared_date         TEXT,
        amount                REAL    NOT NULL,
        currency              TEXT    NOT NULL DEFAULT 'USD',
        dividend_type         TEXT    NOT NULL DEFAULT 'CD',
        franking_credit_pct   REAL    DEFAULT NULL,
        franking_credit_amount REAL   DEFAULT NULL,
        gross_amount          REAL    DEFAULT NULL,
        UNIQUE(security_id, ex_date, dividend_type)
    );

    CREATE TABLE IF NOT EXISTS splits (
        id          INTEGER PRIMARY KEY,
        security_id INTEGER NOT NULL REFERENCES securities(id),
        ex_date     TEXT    NOT NULL,
        split_from  REAL    NOT NULL,
        split_to    REAL    NOT NULL,
        UNIQUE(security_id, ex_date)
    );

    CREATE TABLE IF NOT EXISTS fx_rates (
        id       INTEGER PRIMARY KEY,
        date     TEXT    NOT NULL,
        from_ccy TEXT    NOT NULL,
        to_ccy   TEXT    NOT NULL DEFAULT 'USD',
        rate     REAL    NOT NULL,
        UNIQUE(date, from_ccy, to_ccy)
    );

    CREATE INDEX IF NOT EXISTS idx_fx_date
        ON fx_rates(date, from_ccy);

    CREATE TABLE IF NOT EXISTS ingestion_log (
        id              INTEGER PRIMARY KEY,
        ticker          TEXT    NOT NULL,
        data_type       TEXT    NOT NULL,
        fetched_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        from_date       TEXT,
        to_date         TEXT,
        records_written INTEGER,
        status          TEXT    NOT NULL,
        error_message   TEXT
    );

    CREATE TABLE IF NOT EXISTS ingestion_coverage (
        id          INTEGER PRIMARY KEY,
        security_id INTEGER NOT NULL REFERENCES securities(id),
        data_type   TEXT    NOT NULL,
        source      TEXT    NOT NULL,
        from_date   TEXT    NOT NULL,
        to_date     TEXT    NOT NULL,
        records     INTEGER NOT NULL,
        fetched_at  TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(security_id, data_type, source, from_date, to_date)
    );
    """,
]

CURRENT_SCHEMA_VERSION: int = len(MIGRATIONS)


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply any unapplied migrations to the given connection.

    Reads the current schema version from PRAGMA user_version, then applies
    each migration whose index >= current version. Each migration executes as
    a single executescript() call (auto-committed). After each migration the
    version pragma is incremented.

    Safe to call multiple times — already-applied migrations are skipped.

    Args:
        conn: An open SQLite connection. Foreign keys and WAL mode should be
              configured by the caller if needed.
    """
    current_version: int = conn.execute("PRAGMA user_version").fetchone()[0]
    total: int = len(MIGRATIONS)

    if current_version >= total:
        logger.debug(
            "Schema already at version {version} — no migrations to apply.",
            version=current_version,
        )
        return

    for i, sql in enumerate(MIGRATIONS[current_version:], start=current_version):
        migration_number = i + 1
        logger.info(
            "Applying migration {num} of {total}.",
            num=migration_number,
            total=total,
        )
        conn.executescript(sql)
        # executescript() commits — use a separate execute for the pragma.
        conn.execute(f"PRAGMA user_version = {migration_number}")

    logger.info(
        "Schema now at version {version}.",
        version=total,
    )


def get_connection(db_path: str = "data/market.db") -> sqlite3.Connection:
    """Open a SQLite connection, enable WAL + FK enforcement, and run migrations.

    Args:
        db_path: Path to the SQLite database file. Defaults to data/market.db.
                 Use ":memory:" for an in-memory database.

    Returns:
        A configured, migration-current SQLite connection.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn)
    return conn
