"""Unit tests for multi-key rotation + the circuit breaker (no real API calls).

We monkeypatch ``complete_json`` so we can simulate capped vs working keys and
assert that generate_model rotates correctly. These run with zero quota.
"""

import json

import pytest

from contracts import IntentSpec
from llm import cache, client

VALID_INTENT = json.dumps(
    {
        "app_name": "X", "app_type": "todo", "summary": "s",
        "features": ["f1"], "roles": [], "assumptions": [], "conflicts": [],
    }
)


@pytest.fixture(autouse=True)
def _isolate():
    cache.set_enabled(False)
    client.reset_circuit_breaker()
    yield
    client.reset_circuit_breaker()
    cache.set_enabled(True)


def test_keys_parsing_splits_and_dedupes(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "a, b ,a,c")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client._keys(client.Provider.GEMINI) == ["a", "b", "c"]


def test_rotates_to_next_key_when_first_is_quota_capped(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "capped1,good2")
    monkeypatch.setenv("GROQ_API_KEYS", "groqkey")
    seen = []

    def fake(prompt, *, provider, model, temperature, api_key=None, **_):
        seen.append((provider.value, api_key))
        if api_key == "capped1":
            raise client.LLMError("429 RESOURCE_EXHAUSTED quota")
        return VALID_INTENT

    monkeypatch.setattr(client, "complete_json", fake)
    result = client.generate_model("p", IntentSpec)

    assert result.app_type == "todo"
    assert ("gemini", "capped1") in seen and ("gemini", "good2") in seen
    assert "capped1" in client._exhausted_keys
    assert all(provider != "groq" for provider, _ in seen)  # Groq never needed


def test_circuit_breaker_skips_capped_key_on_next_call(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "capped1,good2")
    monkeypatch.setenv("GROQ_API_KEYS", "groqkey")

    def fake(prompt, *, provider, model, temperature, api_key=None, **_):
        if api_key == "capped1":
            raise client.LLMError("429 RESOURCE_EXHAUSTED")
        return VALID_INTENT

    monkeypatch.setattr(client, "complete_json", fake)
    client.generate_model("p", IntentSpec)  # marks capped1 as exhausted

    seen = []

    def fake2(prompt, *, provider, model, temperature, api_key=None, **_):
        seen.append(api_key)
        if api_key == "capped1":
            raise client.LLMError("429")
        return VALID_INTENT

    monkeypatch.setattr(client, "complete_json", fake2)
    client.generate_model("p", IntentSpec)
    assert "capped1" not in seen  # never retried -- breaker skipped it


def test_falls_back_to_groq_when_all_gemini_keys_capped(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "g1,g2")
    monkeypatch.setenv("GROQ_API_KEYS", "groqkey")
    seen = []

    def fake(prompt, *, provider, model, temperature, api_key=None, **_):
        seen.append((provider.value, api_key))
        if provider.value == "gemini":
            raise client.LLMError("429 RESOURCE_EXHAUSTED")
        return VALID_INTENT

    monkeypatch.setattr(client, "complete_json", fake)
    result = client.generate_model("p", IntentSpec)

    assert result.app_type == "todo"
    assert ("groq", "groqkey") in seen
    assert "g1" in client._exhausted_keys and "g2" in client._exhausted_keys


def test_transient_error_is_retried_not_treated_as_quota(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "g1")
    monkeypatch.setenv("GROQ_API_KEYS", "groqkey")
    monkeypatch.setattr(client, "BACKOFF_S", 0)  # no real sleeping in tests
    attempts = {"n": 0}

    def fake(prompt, *, provider, model, temperature, api_key=None, **_):
        if provider.value == "gemini":
            attempts["n"] += 1
            raise client.LLMError("503 UNAVAILABLE model overloaded")
        return VALID_INTENT

    monkeypatch.setattr(client, "complete_json", fake)
    result = client.generate_model("p", IntentSpec)

    assert result.app_type == "todo"
    assert attempts["n"] == client.MAX_ATTEMPTS  # retried, not skipped on first hit
    assert "g1" not in client._exhausted_keys     # transient != quota
