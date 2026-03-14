"""Root pytest configuration.

Registers the --regen-golden option so tests/test_golden.py can use it
regardless of which directory pytest is invoked from.
"""
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--regen-golden",
        action="store_true",
        default=False,
        help="Regenerate golden fixture JSON files from current engine output.",
    )


@pytest.fixture
def regen_golden(request: pytest.FixtureRequest) -> bool:
    """True when --regen-golden flag is passed; False for normal comparison."""
    return bool(request.config.getoption("--regen-golden"))
