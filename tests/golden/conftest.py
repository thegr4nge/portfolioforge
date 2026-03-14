"""pytest configuration for golden fixture tests.

The --regen-golden option is registered in the root conftest.py.
This file provides the regen_golden fixture for tests in this directory
and for tests/test_golden.py.

Run with --regen-golden to regenerate JSON fixtures from current engine output.
Normal run (no flag) compares engine output to stored fixtures.
"""
import pytest


@pytest.fixture
def regen_golden(request: pytest.FixtureRequest) -> bool:
    """True when --regen-golden flag is passed; False for normal comparison."""
    return bool(request.config.getoption("--regen-golden"))
