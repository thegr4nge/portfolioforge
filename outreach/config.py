"""Load environment variables for outreach modules.

Call load_env() once at startup. Each getter returns None if the key is missing
so individual modules can decide whether to skip or abort.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_env() -> None:
    """Load .env from project root if python-dotenv is available."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]

        env_path = Path(__file__).parent.parent / ".env"
        load_dotenv(env_path)
    except ImportError:
        pass  # python-dotenv optional; fall back to shell environment


def require(key: str) -> str:
    """Return env var value or raise with a helpful message."""
    val = os.getenv(key)
    if not val:
        raise SystemExit(
            f"Missing environment variable: {key}\n"
            f"Copy .env.example to .env and fill in the value."
        )
    return val


def get(key: str) -> str | None:
    """Return env var value or None if not set."""
    return os.getenv(key) or None


# Convenience getters — return None if not configured

def apollo_key() -> str | None:
    return get("APOLLO_API_KEY")


def anthropic_key() -> str | None:
    return get("ANTHROPIC_API_KEY")


def exa_key() -> str | None:
    return get("EXA_API_KEY")


def reddit_credentials() -> dict[str, str] | None:
    client_id = get("REDDIT_CLIENT_ID")
    client_secret = get("REDDIT_CLIENT_SECRET")
    username = get("REDDIT_USERNAME")
    password = get("REDDIT_PASSWORD")
    if not all([client_id, client_secret, username, password]):
        return None
    return {
        "client_id": client_id,  # type: ignore[dict-item]
        "client_secret": client_secret,  # type: ignore[dict-item]
        "username": username,  # type: ignore[dict-item]
        "password": password,  # type: ignore[dict-item]
    }


def gmail_credentials() -> tuple[str, str] | None:
    user = get("GMAIL_USER")
    password = get("GMAIL_APP_PASSWORD")
    if not user or not password:
        return None
    return user, password
