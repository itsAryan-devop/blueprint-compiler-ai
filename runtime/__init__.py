"""Execution layer.

Turns a validated config into something that actually runs: real SQLite tables
and live FastAPI routes, with auth enforced. If a config cannot execute, the run
is a failure — emitting JSON is not enough.
"""
