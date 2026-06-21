"""Pydantic contracts — the strict shapes every pipeline stage must produce.

Defining these *first* (contract-first design) is what lets us guarantee valid
JSON, required fields, and type safety before we ever trust the LLM's output.
"""
