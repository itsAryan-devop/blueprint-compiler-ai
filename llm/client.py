"""Provider abstraction for all LLM calls.

One interface, two providers (Gemini primary, Groq fallback). Every call runs at
temperature 0 and asks for JSON -- the two foundations of deterministic output.

Reliability + determinism:
  * a HARD per-call timeout, so a single call can never hang for minutes;
  * VISIBLE logging on every attempt / retry / fallback / cache hit, so a
    rate-limited run is printed activity instead of a silent freeze;
  * an on-disk CACHE (llm/cache.py): a repeated prompt returns the exact saved
    response -- instant, free, and perfectly deterministic.

Both providers use plain JSON mode with the target schema embedded in the prompt
(not Gemini's native response_schema): our contracts use extra="forbid", whose
JSON Schema carries additionalProperties, which Gemini's response_schema endpoint
rejects with a 400. Our own Pydantic validation is the enforcement we trust.
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


# Models confirmed working on our free-tier keys during Phase 0.
DEFAULT_MODEL = {
    Provider.GEMINI: "gemini-2.5-flash",
    # 70B follows "fill in the schema" instructions far more reliably than the 8B
    # when used as the structured-generation fallback.
    Provider.GROQ: "llama-3.3-70b-versatile",
}

CALL_TIMEOUT_S = 45   # hard ceiling per LLM call -- no single call hangs longer
MAX_ATTEMPTS = 2      # attempts per provider before falling back
BACKOFF_S = 3         # short, visible wait between attempts


class LLMError(RuntimeError):
    """Raised when an LLM provider call fails."""


def complete_json(
    prompt: str,
    *,
    provider: Provider = Provider.GEMINI,
    model: str | None = None,
    temperature: float = 0.0,
    response_schema: type | None = None,
    timeout: float = CALL_TIMEOUT_S,
) -> str:
    """Send ``prompt`` to a provider and return the raw JSON text of the reply.

    ``timeout`` is a hard ceiling (seconds) on the single network call. The schema
    must be described inside ``prompt``; ``response_schema`` is accepted for
    backward compatibility but is intentionally not used (see module docstring).
    """
    model = model or DEFAULT_MODEL[provider]
    if provider is Provider.GEMINI:
        return _gemini_json(prompt, model, temperature, timeout)
    if provider is Provider.GROQ:
        return _groq_json(prompt, model, temperature, timeout)
    raise LLMError(f"Unknown provider: {provider}")


def _gemini_json(prompt: str, model: str, temperature: float, timeout: float) -> str:
    from google import genai
    from google.genai import types

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY is not set in the environment / .env")

    http_options = types.HttpOptions(timeout=int(timeout * 1000)) if timeout else None
    client = genai.Client(api_key=key, http_options=http_options)

    config = types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature)
    try:
        response = client.models.generate_content(model=model, contents=prompt, config=config)
        return response.text
    except Exception as error:
        raise LLMError(f"Gemini call failed: {error}") from error


def _groq_json(prompt: str, model: str, temperature: float, timeout: float) -> str:
    from groq import Groq

    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise LLMError("GROQ_API_KEY is not set in the environment / .env")
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

    Order per provider (Gemini, then Groq): check the on-disk cache first (a hit
    is instant, free, and byte-identical -- this is our determinism guarantee for
    repeats); otherwise call live, up to MAX_ATTEMPTS, with a hard per-call
    timeout and a printed line for every attempt/retry/fallback. Only a response
    that parses AND validates is cached. A ValidationError is raised to the
    caller -- that is the repair engine's job, not something a retry should mask.
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
                pass  # unreadable/incompatible cache entry -> fall through to a live call

        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(f"          > {provider.value} (try {attempt}/{MAX_ATTEMPTS}, timeout {CALL_TIMEOUT_S}s) ...", flush=True)
            try:
                raw = complete_json(prompt, provider=provider, model=model, temperature=temperature)
                data = parse_json(raw)
            except (LLMError, json.JSONDecodeError) as error:
                short = " ".join(str(error).split())[:90]
                errors.append(f"{provider.value} #{attempt}: {short}")
                if attempt < MAX_ATTEMPTS:
                    nxt = f"retrying in {BACKOFF_S}s"
                else:
                    nxt = "falling back to Groq" if provider is Provider.GEMINI else "no providers left"
                print(f"          ! {provider.value} failed: {short} -- {nxt}", flush=True)
                if attempt < MAX_ATTEMPTS:
                    time.sleep(BACKOFF_S)
                continue
            if _is_schema_echo(data):
                errors.append(f"{provider.value} #{attempt}: echoed the schema, not an instance")
                print(f"          ! {provider.value} returned the schema, not an instance -- retrying", flush=True)
                continue
            model_obj = schema.model_validate(data)  # may raise -> not cached
            cache.put(provider.value, model, temperature, prompt, raw)
            return model_obj
    raise LLMError(
        f"All providers failed for {schema.__name__}: " + " | ".join(errors[-4:])
    )
