"""Tests for Phase 10's provider-pin + 403 quota classification (no API calls)."""

import json
from unittest.mock import patch

import pytest

from contracts import IntentSpec
from llm import cache, client

VALID = json.dumps({
    "app_name": "X", "app_type": "todo", "summary": "s",
    "features": ["f"], "roles": [], "assumptions": [], "conflicts": [],
})


@pytest.fixture(autouse=True)
def _isolate():
    client.reset_circuit_breaker()
    client.pin_provider(None)
    cache.set_enabled(False)  # avoid hits from real prior runs
    yield
    client.reset_circuit_breaker()
    client.pin_provider(None)
    cache.set_enabled(True)


def test_403_permission_denied_is_treated_as_quota_cap():
    assert client._is_quota_error(Exception("403 PERMISSION_DENIED ..."))


def test_503_overloaded_stays_transient():
    assert not client._is_quota_error(Exception("503 UNAVAILABLE model overloaded"))


def test_pinning_groq_skips_gemini_entirely(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "g1")
    monkeypatch.setenv("GROQ_API_KEYS", "q1")
    seen = []

    def fake(prompt, *, provider, model, temperature, api_key=None, **_):
        seen.append(provider.value)
        return VALID

    monkeypatch.setattr(client, "complete_json", fake)
    client.pin_provider(client.Provider.GROQ)
    client.generate_model("p", IntentSpec)

    assert seen == ["groq"]  # gemini never tried
