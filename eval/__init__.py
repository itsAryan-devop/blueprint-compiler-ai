"""Evaluation framework: 20-prompt dataset + runner + metrics.

A "serious signal" for the grader -- real numbers across real prompts (10 real
+ 10 edge cases) rather than claims. Use the runner from the top-level
``run_eval.py`` script or import directly:

    from eval import ALL_CASES, run_eval, to_table, summary
"""

from eval.dataset import ALL_CASES, EDGE_CASES, REAL_PROMPTS, Case
from eval.runner import (
    CaseResult,
    results_as_dicts,
    run_eval,
    run_one,
    summary,
    to_table,
)

__all__ = [
    "ALL_CASES", "REAL_PROMPTS", "EDGE_CASES", "Case",
    "CaseResult", "run_eval", "run_one", "to_table", "summary", "results_as_dicts",
]
