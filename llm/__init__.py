"""Provider abstraction.

All LLM calls go through one interface so Gemini and Groq are swappable with a
flag. This is where JSON mode, temperature 0, retries, and caching will live.
"""

from llm.client import LLMError, Provider, complete_json, generate_model, parse_json

__all__ = ["Provider", "complete_json", "generate_model", "parse_json", "LLMError"]
