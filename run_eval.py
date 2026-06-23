r"""
Phase 9 -- run the evaluation suite.

Run all 20 prompts (10 real + 10 edge cases):
    .\venv\Scripts\python.exe run_eval.py

Run a small subset (great for quota / fast verification):
    .\venv\Scripts\python.exe run_eval.py --subset 4

Cache-friendly: re-running is nearly free and produces identical numbers.
Metrics are also written to eval_metrics.json for the README / video.
"""

import argparse
import json
from pathlib import Path

from eval import ALL_CASES, results_as_dicts, run_eval, summary, to_table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", type=int, default=0,
                        help="Run only the first N cases (0 = all 20).")
    parser.add_argument("--out", default="eval_metrics.json",
                        help="Where to write the per-case + summary JSON.")
    args = parser.parse_args()

    cases = ALL_CASES if args.subset <= 0 else ALL_CASES[: args.subset]
    print("=" * 72)
    print(f"EVALUATION  --  {len(cases)} prompt(s)")
    print("=" * 72)

    results = run_eval(cases)

    print("\n--- PER-CASE TABLE ---")
    print(to_table(results))

    s = summary(results)
    print("\n--- SUMMARY ---")
    for key, value in s.items():
        if isinstance(value, float):
            print(f"  {key:<28} {value:.3f}")
        else:
            print(f"  {key:<28} {value}")

    Path(args.out).write_text(
        json.dumps({"summary": s, "cases": results_as_dicts(results)}, indent=2),
        encoding="utf-8",
    )
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
