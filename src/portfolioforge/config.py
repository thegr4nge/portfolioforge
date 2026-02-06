"""Application constants and defaults for PortfolioForge."""

from pathlib import Path

# Storage
DATA_DIR: Path = Path.home() / ".portfolioforge"
CACHE_DB_PATH: Path = DATA_DIR / "cache.db"

# Cache TTLs
CACHE_TTL_HOURS: int = 24
FX_CACHE_TTL_HOURS: int = 1

# Analysis defaults
DEFAULT_RISK_FREE_RATE: float = 0.04  # Approximate RBA cash rate
DEFAULT_PERIOD_YEARS: int = 10

# Benchmarks: display name -> ticker
DEFAULT_BENCHMARKS: dict[str, str] = {
    "S&P 500": "^GSPC",
    "ASX 200": "^AXJO",
    "MSCI World": "URTH",
}

# Rate limit mitigation
MAX_TICKERS_PER_FETCH: int = 20

# Market suffix -> currency mapping
SUPPORTED_MARKETS: dict[str, str] = {
    ".AX": "AUD",
    "": "USD",
    ".L": "GBP",
    ".PA": "EUR",
    ".DE": "EUR",
}

# External APIs
FRANKFURTER_BASE_URL: str = "https://api.frankfurter.dev/v1"
