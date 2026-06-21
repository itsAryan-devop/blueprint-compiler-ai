"""Provider abstraction for all LLM calls.

One interface, two providers (Gemini primary, Groq fallback). Every call runs at
temperature 0 and asks for JSON -- the two foundations of deterministic output.

This is intentionally minimal for the walking skeleton (Phase 2). Retries with
backoff, caching, and the cost-vs-quality switch arrive in later phases; the
point now is a single clean seam so the rest of the code never talks to a
provider SDK directly.
"""

import json
import os
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


class Provider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"


# Models confirmed working on our free-tier keys during Phase 0.
DEFAULT_MODEL = {
    Provider.GEMINI: "gemini-2.5-flash",
    Provider.GROQ: "llama-3.1-8b-instant",
}


class LLMError(RuntimeError):
    """Raised when an LLM provider call fails."""


def complete_json(
    prompt: str,
    *,
    provider: Provider = Provider.GEMINI,
    model: str | None = None,
    temperature: float = 0.0,
    response_schema: type | None = None,
) -> str:
    """Send ``prompt`` to a provider and return the raw JSON text of the reply.

    ``response_schema`` (a Pydantic model class) is used only by Gemini, for
    native constrained decoding; other providers ignore it and rely on the
    schema being described inside the prompt.
    """
    model = model or DEFAULT_MODEL[provider]
    if provider is Provider.GEMINI:
        return _gemini_json(prompt, model, temperature, response_schema)
    if provider is Provider.GROQ:
        return _groq_json(prompt, model, temperature)
    raise LLMError(f"Unknown provider: {provider}")


def _gemini_json(prompt: str, model: str, temperature: float, response_schema) -> str:
    from google import genai
    from google.genai import types

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY is not set in the environment / .env")
    client = genai.Client(api_key=key)

    base = {"response_mime_type": "application/json", "temperature": temperature}
    try:
        if response_schema is not None:
            config = types.GenerateContentConfig(**base, response_schema=response_schema)
        else:
            config = types.GenerateContentConfig(**base)
        response = client.models.generate_content(model=model, contents=prompt, config=config)
        return response.text
    except Exception as error:
        # Native structured output can reject very complex schemas. If so, retry
        # in plain JSON mode and let our own Pydantic validation do the enforcing.
        if response_schema is not None:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**base),
                )
                return response.text
            except Exception as retry_error:
                raise LLMError(f"Gemini call failed: {retry_error}") from retry_error
        raise LLMError(f"Gemini call failed: {error}") from error


def _groq_json(prompt: str, model: str, temperature: float) -> str:
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
