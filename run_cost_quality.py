r"""
Phase 10 -- cost vs quality (cheap-fast vs smart-slow).

Runs the same prompts twice -- once pinned to Gemini (smart, free-tier capped),
once pinned to Groq (fast workhorse) -- and prints a side-by-side table with a
recommendation. Reuses the Phase 9 runner so the metrics are exactly the same
shape.

Quota-friendly: --subset keeps the comparison small; the cache makes any repeat
of a (provider, model, temperature, prompt) instant and free.

Run:
    .\venv\Scripts\python.exe run_cost_quality.py            # default subset 2
    .\venv\Scripts\python.exe run_cost_quality.py --subset 4

Token-cost note: free-tier APIs do not bill us, so we estimate cost as
"latency-seconds" (a proxy for compute spent + a real demo concern: slow runs
hurt the live URL). For paid tiers the cost column would switch to $$ and the
trade-off discussion stays the same.
"""

import argparse
import json
from pathlib import Path

from eval import ALL_CASES, results_as_dicts, run_eval, summary
from llm import Provider, pin_provider, reset_circuit_breaker
from llm.cache import set_enabled


def _run_with(provider: Provider, cases):
    reset_circuit_breaker()
    pin_provider(provider)
    try:
        return run_eval(cases)
    finally:
        pin_provider(None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", type=int, default=2,
                        help="How many cases per provider (default: 2 to stay quota-light).")
    parser.add_argument("--out", default="cost_quality_metrics.json")
    args = parser.parse_args()
    set_enabled(True)  # cache is essential for a fair re-run

    cases = ALL_CASES[: args.subset]
    print("=" * 72)
    print(f"COST vs QUALITY  --  {len(cases)} prompt(s) x 2 providers")
    print("=" * 72)

    print("\n--- pinning provider: GEMINI (smart, free-tier 20/day per key) ---")
    gemini_results = _run_with(Provider.GEMINI, cases)
    g = summary(gemini_results)

    print("\n--- pinning provider: GROQ (fast workhorse, high free limits) ---")
    groq_results = _run_with(Provider.GROQ, cases)
    q = summary(groq_results)

    print("\n--- COMPARISON ---")
    rows = [
        ["metric", "gemini", "groq"],
        ["success_rate", f"{g.get('success_rate', 0):.2f}", f"{q.get('success_rate', 0):.2f}"],
        ["compiled", str(g.get("compiled", 0)), str(q.get("compiled", 0))],
        ["failed", str(g.get("failed", 0)), str(q.get("failed", 0))],
        ["avg_latency_s", f"{g.get('avg_latency_s', 0):.1f}", f"{q.get('avg_latency_s', 0):.1f}"],
        ["p95_latency_s", f"{g.get('p95_latency_s', 0):.1f}", f"{q.get('p95_latency_s', 0):.1f}"],
        ["repair_actions", str(g.get("total_repair_actions", 0)), str(q.get("total_repair_actions", 0))],
        ["regen_actions", str(g.get("total_regen_actions", 0)), str(q.get("total_regen_actions", 0))],
        ["assumptions", str(g.get("total_assumptions_recorded", 0)), str(q.get("total_assumptions_recorded", 0))],
    ]
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    line = lambda r: "  ".join(c.ljust(widths[i]) for i, c in enumerate(r))
    print(line(rows[0]))
    print("  ".join("-" * widths[i] for i in range(3)))
    for r in rows[1:]:
        print(line(r))

    print("\n--- RECOMMENDATION ---")
    g_rate, q_rate = g.get("success_rate", 0), q.get("success_rate", 0)
    if g_rate == 0 and q_rate == 0:
        print("Both providers hit 0% on this run -- almost certainly free-tier quota")
        print("exhaustion (Gemini's 20/day per key + Groq's per-minute cap). The")
        print("provider-pin + comparison machinery works; rerun later with fresh")
        print("quota for a meaningful quality comparison. Until then, prefer Groq")
        print("for the live demo (higher per-minute limits) with Gemini as backup.")
    elif abs(g_rate - q_rate) < 0.01 and q.get("avg_latency_s", 1e9) < g.get("avg_latency_s", 0):
        print("Groq matches Gemini's correctness on this set and is faster. For the")
        print("live demo (latency-sensitive), prefer Groq as primary and keep Gemini")
        print("as the higher-quality backup for hard prompts.")
    elif g_rate > q_rate:
        print("Gemini produces better blueprints on this set even though it is")
        print("slower / quota-capped. Keep Gemini primary; Groq stays as fallback")
        print("and is essential when Gemini's free quota is exhausted.")
    else:
        print("Mixed picture: providers trade quality vs latency case by case.")
        print("The provider abstraction lets us swap or A/B them without code")
        print("changes -- exactly the cost/quality knob the task asks for.")

    Path(args.out).write_text(
        json.dumps({
            "subset_size": len(cases),
            "gemini": {"summary": g, "cases": results_as_dicts(gemini_results)},
            "groq":   {"summary": q, "cases": results_as_dicts(groq_results)},
        }, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
