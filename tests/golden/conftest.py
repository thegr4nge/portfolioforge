"""pytest configuration for golden fixture tests.

Run with --regen-golden to regenerate JSON fixtures from current engine output.
Normal run (no flag) compares engine output to stored fixtures.
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
