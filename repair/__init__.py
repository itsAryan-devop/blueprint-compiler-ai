"""The repair engine (the core of the project).

Tiered, never brute-force:
  1. deterministic auto-fix   (no LLM)
  2. targeted regeneration    (re-ask the LLM for ONLY the broken part)
  3. structured failure       (give up honestly after a hard retry cap)
"""
