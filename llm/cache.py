"""A tiny on-disk cache for LLM responses.

Determinism + cost: at temperature 0 the model is already stable, but a cache
makes a repeated prompt return the EXACT saved response -- instantly, with zero
API calls and zero rate-limit risk. The key is a hash of
(provider, model, temperature, prompt), so the same request always maps to the
same entry. This is the practical answer to free-tier rate limits.
"""

import hashlib
import json
import os
from pathlib import Path

CACHE_DIR = Path(os.getenv("LLM_CACHE_DIR", ".llm_cache"))
_enabled = os.getenv("LLM_CACHE", "1") != "0"


def set_enabled(flag: bool) -> None:
    """Turn caching on/off at runtime (used by the determinism demo)."""
    global _enabled
    _enabled = flag


def is_enabled() -> bool:
    return _enabled


def _path(provider: str, model: str, temperature: float, prompt: str) -> Path:
    raw = f"{provider}|{model}|{temperature}|{prompt}"
    return CACHE_DIR / (hashlib.sha256(raw.encode("utf-8")).hexdigest() + ".json")


def get(provider: str, model: str, temperature: float, prompt: str) -> str | None:
    if not _enabled:
        return None
    path = _path(provider, model, temperature, prompt)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    except Exception:
        return None  # unreadable entry -> treat as a miss


def put(provider: str, model: str, temperature: float, prompt: str, response: str) -> None:
    if not _enabled:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "provider": provider, "model": model, "temperature": temperature,
        "prompt": prompt, "response": response,
    }
    _path(provider, model, temperature, prompt).write_text(json.dumps(record), encoding="utf-8")


def clear() -> int:
    """Delete all cache entries. Returns how many were removed."""
    count = 0
    if CACHE_DIR.exists():
        for file in CACHE_DIR.glob("*.json"):
            file.unlink()
            count += 1
    return count
