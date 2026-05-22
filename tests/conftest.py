"""Shared pytest fixtures and environment hygiene.

⚠️ SECRETS-IN-LOGS DEFENSE (incident 2026-05-21) ⚠️

The `_RealKey` wrapper is load-bearing. It exists because pytest -v includes
fixture values in its verbose report, and the standing test-log rule then
tees that report to docs/test_runs/. A fixture that returns a raw secret
string will leak it into committed logs.

Both `_captured_real_key` and `real_anthropic_key` MUST return _RealKey,
not str. Consumers access the actual key via `.value`.

See the top of CLAUDE.md and ~/.claude/CLAUDE.md (NEVER Let Secrets Leak
Into Test Logs) for the full incident writeup and prevention rules.
"""

import os

import pytest


class _RealKey:
    """Holds a real secret; repr/str surface only '<REDACTED>'.

    pytest -v calls repr() on fixture return values when rendering its
    report. Any plain-string return is a leak vector. This wrapper makes
    the leak vector inert: the report shows <REDACTED>, real code calls
    `.value` to get the secret.
    """

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return "<REDACTED>"

    def __str__(self) -> str:
        return "<REDACTED>"


@pytest.fixture(scope="session")
def _captured_real_key() -> _RealKey:
    """Capture the real ANTHROPIC_API_KEY once at session start, before the
    function-scoped autouse scrub overwrites it. Wrapped in _RealKey so the
    raw value never reaches pytest -v's report.
    """
    return _RealKey(os.environ.get("ANTHROPIC_API_KEY", ""))


@pytest.fixture(autouse=True)
def scrub_anthropic_key(monkeypatch):
    """Ensure unit tests never accidentally hit the real Anthropic API."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key-for-unit-tests")


@pytest.fixture
def real_anthropic_key(_captured_real_key: _RealKey) -> _RealKey:
    """Provide the real ANTHROPIC_API_KEY for slow tests; skip if absent.

    Returns a `_RealKey`; consumers call `.value` to get the actual string.
    Returning the raw string here would defeat the redaction in
    `_captured_real_key`.
    """
    env_override = os.environ.get("TANDC_REAL_ANTHROPIC_API_KEY", "")
    key = env_override or _captured_real_key.value
    if not key or key.startswith("sk-test-"):
        pytest.skip("No real ANTHROPIC_API_KEY available for live test")
    return _RealKey(key)
