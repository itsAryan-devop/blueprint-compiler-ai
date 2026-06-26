"""Run the evaluation dataset and collect per-prompt metrics.

For each case we record:
  * outcome          -- compiled / clarified / failed
  * matched_expected -- did the outcome match what we declared expected?
  * latency_s        -- wall-clock seconds
  * repair_actions   -- how many fixes the repair engine applied
  * regen_actions    -- of those, how many needed an LLM (vs deterministic)
  * issues_before    -- cross-layer issues before repair (signal of upstream quality)
  * issues_after     -- cross-layer issues after repair (target: 0)
  * assumptions      -- how many assumptions the system recorded
  * failure_type     -- short label when something went wrong, else ""

The cache makes a repeat run nearly free (and byte-deterministic), so the runner
is safe to re-execute.
"""

import concurrent.futures
import time
from dataclasses import asdict, dataclass

from eval.dataset import ALL_CASES, Case
from llm import reset_circuit_breaker
from pipeline import compile_app
from repair import repair_blueprint
from validation import validate_blueprint

# Per-case wall-clock cap. With ~140 quota across all keys, a single case
# exhausting every key on every stage retry can pin the whole eval for tens of
# minutes. Bounding each case keeps the eval finishable even when quota is bad.
#
# IMPORTANT: each case uses its OWN ephemeral executor. Python cannot kill a
# running thread, so a timed-out case's compile_app keeps running. With a shared
# pool the next case's submit would queue behind the runaway and itself time out
# (we saw this with E01 -- 120s "failure" with zero actual work). Per-case pools
# isolate the leak: the runaway thread fades on its own, the next case starts
# immediately on a fresh thread.
CASE_TIMEOUT_S = 120


@dataclass
class CaseResult:
    id: str
    label: str
    expected: str
    outcome: str           # compiled | clarified | failed
    matched_expected: bool
    latency_s: float
    repair_actions: int = 0
    regen_actions: int = 0
    issues_before: int = 0
    issues_after: int = 0
    assumptions: int = 0
    failure_type: str = ""


def _outcome_matches(expected: str, outcome: str, assumptions: int) -> bool:
    if expected == "clarifies":
        return outcome == "clarified"
    if expected == "compiles":
        return outcome == "compiled"
    if expected == "assumes":
        return outcome == "compiled" and assumptions > 0
    return False


def run_one(case: Case) -> CaseResult:
    t0 = time.perf_counter()
    # Ephemeral, single-shot pool per case -- see note at the top of the file.
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"case-{case.id}")
    future = pool.submit(compile_app, case.request)
    try:
        cr = future.result(timeout=CASE_TIMEOUT_S)
    except concurrent.futures.TimeoutError:
        future.cancel()
        pool.shutdown(wait=False)  # let the runaway thread fade in the background
        return CaseResult(
            id=case.id, label=case.label, expected=case.expected,
            outcome="failed", matched_expected=False,
            latency_s=time.perf_counter() - t0,
            failure_type=f"case_timeout_{CASE_TIMEOUT_S}s",
        )
    except Exception as error:
        pool.shutdown(wait=False)
        return CaseResult(
            id=case.id, label=case.label, expected=case.expected,
            outcome="failed", matched_expected=False,
            latency_s=time.perf_counter() - t0,
            failure_type=type(error).__name__,
        )
    pool.shutdown(wait=False)

    if cr.needs_clarification:
        return CaseResult(
            id=case.id, label=case.label, expected=case.expected,
            outcome="clarified",
            matched_expected=_outcome_matches(case.expected, "clarified", 0),
            latency_s=time.perf_counter() - t0,
        )

    blueprint = cr.blueprint
    before = validate_blueprint(blueprint)
    repair_result = repair_blueprint(blueprint)
    blueprint = repair_result.blueprint
    after = repair_result.remaining
    assumptions = len(blueprint.assumptions)
    return CaseResult(
        id=case.id, label=case.label, expected=case.expected,
        outcome="compiled",
        matched_expected=_outcome_matches(case.expected, "compiled", assumptions),
        latency_s=time.perf_counter() - t0,
        repair_actions=len(repair_result.log.actions),
        regen_actions=sum(1 for a in repair_result.log.actions if a.tier.value == "targeted_regen"),
        issues_before=len(before.errors),
        issues_after=len(after.errors),
        assumptions=assumptions,
    )


def run_eval(cases: list[Case] | None = None) -> list[CaseResult]:
    cases = list(cases) if cases is not None else list(ALL_CASES)
    results: list[CaseResult] = []
    for case in cases:
        # Each case is independent: clear any keys the previous case marked as
        # capped (e.g. Groq per-minute limits that recover in seconds), so one
        # poisoned key does not silently fail the rest of the eval.
        reset_circuit_breaker()
        print(f"  > {case.id} {case.label} ...", flush=True)
        results.append(run_one(case))
    return results


def to_table(results: list[CaseResult]) -> str:
    headers = ["id", "expected", "outcome", "ok", "lat(s)", "iss b/a", "rep", "regen", "asm"]
    rows: list[list[str]] = [headers]
    for r in results:
        rows.append([
            r.id, r.expected, r.outcome,
            "yes" if r.matched_expected else "NO",
            f"{r.latency_s:.1f}",
            f"{r.issues_before}/{r.issues_after}",
            str(r.repair_actions), str(r.regen_actions), str(r.assumptions),
        ])
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    line = lambda row: "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
    sep = "  ".join("-" * widths[i] for i in range(len(headers)))
    return "\n".join([line(rows[0]), sep] + [line(row) for row in rows[1:]])


def summary(results: list[CaseResult]) -> dict:
    n = len(results)
    if not n:
        return {}
    ok = sum(1 for r in results if r.matched_expected)
    latencies = sorted(r.latency_s for r in results)
    return {
        "total": n,
        "success_rate": ok / n,
        "compiled": sum(1 for r in results if r.outcome == "compiled"),
        "clarified": sum(1 for r in results if r.outcome == "clarified"),
        "failed": sum(1 for r in results if r.outcome == "failed"),
        "avg_latency_s": sum(latencies) / n,
        "p50_latency_s": latencies[n // 2],
        "p95_latency_s": latencies[min(n - 1, int(n * 0.95))],
        "total_repair_actions": sum(r.repair_actions for r in results),
        "total_regen_actions": sum(r.regen_actions for r in results),
        "deterministic_fix_share": (
            (sum(r.repair_actions - r.regen_actions for r in results)
             / max(1, sum(r.repair_actions for r in results)))
        ),
        "total_assumptions_recorded": sum(r.assumptions for r in results),
    }


def results_as_dicts(results: list[CaseResult]) -> list[dict]:
    return [asdict(r) for r in results]
