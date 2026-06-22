"""Provider abstraction for all LLM calls.

One interface, two providers (Gemini primary, Groq fallback), each able to hold
MULTIPLE free-tier keys. Every call runs at temperature 0 and asks for JSON.

Why multiple keys: Gemini's free tier allows only ~20 requests/day PER KEY. That
is a hard Google limit, not a bug -- no code makes one free key exceed it. So we
pool keys: set ``GEMINI_API_KEYS`` (comma-separated) and we rotate through them,
giving N x 20/day while keeping Gemini primary. Add more free keys to scale.

Reliability + determinism:
  * a HARD per-call timeout, so a single call can never hang for minutes;
  * a CIRCUIT BREAKER: the instant a key returns a quota/429 error it is skipped
    for the rest of the run (no wasted retries on a capped key);
  * VISIBLE logging on every attempt / skip / fallback / cache hit;
  * an on-disk CACHE (llm/cache.py): a repeated prompt returns the exact saved
    response -- instant, free, deterministic, and using zero quota.

Both providers use plain JSON mode with the schema embedded in the prompt (not
Gemini's native response_schema, which 400s on our extra="forbid" contracts).
Our own Pydantic validation is the enforcement we trust.
"""

import json
import os
import time
from enum import Enum

from dotenv import load_dotenv

from . import cache

load_dotenv()


class Provider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"


DEFAULT_MODEL = {
    Provider.GEMINI: "gemini-2.5-flash",
    Provider.GROQ: "llama-3.3-70b-versatile",
}

CALL_TIMEOUT_S = 45   # hard ceiling per LLM call -- no single call hangs longer
MAX_ATTEMPTS = 2      # transient-error retries per key before moving on
BACKOFF_S = 3         # short, visible wait between transient retries

# Circuit breaker: keys that returned a quota/429 error during THIS process.
# Skipped for the rest of the run so we don't waste attempts on a capped key.
# Resets naturally on the next process (quota may have refreshed by then).
_exhausted_keys: set[str] = set()


class LLMError(RuntimeError):
    """Raised when an LLM provider call fails."""


def reset_circuit_breaker() -> None:
    """Forget which keys are exhausted (used by tests and long-lived servers)."""
    _exhausted_keys.clear()


def _keys(provider: Provider) -> list[str]:
    """Ordered, de-duplicated list of keys for a provider.

    Prefers the plural ``*_API_KEYS`` (comma-separated); falls back to the single
    ``*_API_KEY`` so older setups keep working.
    """
    if provider is Provider.GEMINI:
        raw = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or ""
    else:
        raw = os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_KEY") or ""
    seen, keys = set(), []
    for key in (part.strip() for part in raw.split(",")):
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _is_quota_error(error: Exception) -> bool:
    """True for 'you're rate-limited / out of quota' errors (skip the key), as
    opposed to transient errors like 503 'overloaded' (which we retry)."""
    text = str(error).lower()
    return any(s in text for s in ("429", "resource_exhausted", "rate limit", "quota", "exceeded"))


def complete_json(
    prompt: str,
    *,
    provider: Provider = Provider.GEMINI,
    model: str | None = None,
    temperature: float = 0.0,
    response_schema: type | None = None,
    timeout: float = CALL_TIMEOUT_S,
    api_key: str | None = None,
) -> str:
    """Send ``prompt`` to a provider and return the raw JSON text of the reply.

    ``api_key`` overrides the env key (used by the rotation in generate_model).
    The schema must be inside ``prompt``; ``response_schema`` is accepted for
    backward compatibility but intentionally not used (see module docstring).
    """
    model = model or DEFAULT_MODEL[provider]
    if provider is Provider.GEMINI:
        return _gemini_json(prompt, model, temperature, timeout, api_key)
    if provider is Provider.GROQ:
        return _groq_json(prompt, model, temperature, timeout, api_key)
    raise LLMError(f"Unknown provider: {provider}")


def _gemini_json(prompt: str, model: str, temperature: float, timeout: float, api_key: str | None = None) -> str:
    from google import genai
    from google.genai import types

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise LLMError("No Gemini key set (GEMINI_API_KEYS / GEMINI_API_KEY)")

    http_options = types.HttpOptions(timeout=int(timeout * 1000)) if timeout else None
    client = genai.Client(api_key=key, http_options=http_options)

    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature)
    try:
        response = client.models.generate_content(model=model, contents=prompt, config=config)
        return response.text
    except Exception as error:
        raise LLMError(f"Gemini call failed: {error}") from error


def _groq_json(prompt: str, model: str, temperature: float, timeout: float, api_key: str | None = None) -> str:
    from groq import Groq

    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise LLMError("No Groq key set (GROQ_API_KEYS / GROQ_API_KEY)")
    client = Groq(api_key=key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            response_format={"type": "json_object"},
            timeout=timeout,
        )
        return response.choices[0].message.content
    except Exception as error:
        raise LLMError(f"Groq call failed: {error}") from error


def parse_json(text: str) -> dict:
    """Parse JSON text into a dict, tolerating stray prose or code fences."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _is_schema_echo(data) -> bool:
    """A weaker model sometimes returns the JSON Schema instead of an instance."""
    return isinstance(data, dict) and ("$defs" in data or "properties" in data)


def generate_model(prompt: str, schema, *, temperature: float = 0.0):
    """Generate JSON for ``prompt`` and validate it into ``schema``.

    For each provider (Gemini first, then Groq): check the cache (a hit is
    instant, free, deterministic); else rotate through that provider's keys. A
    quota-capped key is skipped immediately and remembered (circuit breaker);
    transient errors get a couple of retries. Only output that parses AND
    validates is cached. A ValidationError is raised to the caller -- that is the
    repair engine's job, not something a retry should mask.
    """
    errors: list[str] = []
    for provider in (Provider.GEMINI, Provider.GROQ):
        model = DEFAULT_MODEL[provider]

        cached = cache.get(provider.value, model, temperature, prompt)
        if cached is not None:
            try:
                data = parse_json(cached)
                if not _is_schema_echo(data):
                    print(f"          > {provider.value} (cache hit)", flush=True)
                    return schema.model_validate(data)
            except Exception:
                pass  # unreadable cache entry -> fall through to a live call

        keys = _keys(provider)
        if not keys:
            errors.append(f"{provider.value}: no API key configured")
            continue

        for key in keys:
            if key in _exhausted_keys:
                continue  # circuit breaker: this key already 429'd this run
            tag = f"{provider.value} key ...{key[-4:]}"
            for attempt in range(1, MAX_ATTEMPTS + 1):
                print(f"          > {tag} (try {attempt}/{MAX_ATTEMPTS}, timeout {CALL_TIMEOUT_S}s) ...", flush=True)
                try:
                    raw = complete_json(prompt, provider=provider, model=model,
                                        temperature=temperature, api_key=key)
                    data = parse_json(raw)
                except (LLMError, json.JSONDecodeError) as error:
                    short = " ".join(str(error).split())[:90]
                    errors.append(f"{tag} #{attempt}: {short}")
                    if _is_quota_error(error):
                        _exhausted_keys.add(key)
                        print(f"          ! {tag} quota-capped -- skipping this key for the rest of the run", flush=True)
                        break  # don't retry a capped key; move to the next key
                    if attempt < MAX_ATTEMPTS:
                        print(f"          ! {tag} failed: {short} -- retrying in {BACKOFF_S}s", flush=True)
                        time.sleep(BACKOFF_S)
                    else:
                        print(f"          ! {tag} failed: {short} -- next key/provider", flush=True)
                    continue
                if _is_schema_echo(data):
                    errors.append(f"{tag} #{attempt}: echoed the schema, not an instance")
                    print(f"          ! {tag} returned the schema, not an instance -- retrying", flush=True)
                    continue
                model_obj = schema.model_validate(data)  # may raise -> not cached
                cache.put(provider.value, model, temperature, prompt, raw)
                return model_obj
    raise LLMError(
        f"All providers/keys failed for {schema.__name__}: " + " | ".join(errors[-5:])
    )
