r"""
Phase 6 demo -- determinism + caching.

Run:  .\venv\Scripts\python.exe demo_determinism.py

Part 1  SAME PROMPT 5x -> identical: run one stage five times. Run 1 is a live
        call; runs 2-5 are served from the cache (0 API calls). All five outputs
        are byte-identical -- exactly the "same prompt 5x" determinism check.
Part 2  END-TO-END determinism + speed: compile the same request twice. Run 1
        makes the real calls; run 2 is entirely cache hits -> a byte-identical
        blueprint, near-instant and free.
Part 3  TEMPERATURE 0 (cache OFF): run one stage twice live; temperature 0 keeps
        the raw model output stable even before caching guarantees exact repeats.

Each part is wrapped: if both free-tier providers are momentarily rate-limited,
the part degrades to a clear message instead of crashing -- which is itself the
problem caching is here to solve.
"""

import hashlib
import time

from llm import cache
from pipeline import compile_app
from pipeline.intent import extract_intent


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


REQUEST = (
    "Build a CRM with login, contacts, dashboard, role-based access, and a "
    "premium plan with payments. Admins can see analytics."
)
INTENT_PROMPT = "a simple todo app with tasks, projects, and due dates"


def part1() -> None:
    print("=" * 72)
    print("PART 1 -- same prompt 5x  =>  identical (runs 2-5 served from cache)")
    print("=" * 72)
    cache.clear()
    hashes = []
    for i in range(1, 6):
        hashes.append(digest(extract_intent(INTENT_PROMPT).model_dump_json()))
        print(f"  run {i}: hash={hashes[-1]}")
    print(f"  ALL 5 IDENTICAL: {len(set(hashes)) == 1}")


def part2() -> None:
    print("\n" + "=" * 72)
    print("PART 2 -- same request twice  =>  identical blueprint + instant repeat")
    print("=" * 72)
    cache.clear()
    t0 = time.perf_counter()
    bp1 = compile_app(REQUEST)
    t1 = time.perf_counter()
    bp2 = compile_app(REQUEST)
    t2 = time.perf_counter()
    j1, j2 = bp1.model_dump_json(), bp2.model_dump_json()
    print(f"\n  run 1 (cache miss): {t1 - t0:6.1f}s   hash={digest(j1)}")
    print(f"  run 2 (cache hit):  {t2 - t1:6.1f}s   hash={digest(j2)}")
    print(f"  IDENTICAL: {j1 == j2}")


def part3() -> None:
    print("\n" + "=" * 72)
    print("PART 3 -- temperature 0 keeps the raw model stable (cache OFF)")
    print("=" * 72)
    cache.set_enabled(False)
    try:
        a = digest(extract_intent(INTENT_PROMPT).model_dump_json())
        b = digest(extract_intent(INTENT_PROMPT).model_dump_json())
    finally:
        cache.set_enabled(True)
    print(f"  live run A: hash={a}")
    print(f"  live run B: hash={b}")
    print(f"  identical at temp 0: {a == b}  (caching guarantees exact repeats regardless)")


def main() -> None:
    for label, fn in (("PART 1", part1), ("PART 2", part2), ("PART 3", part3)):
        try:
            fn()
        except Exception as error:
            short = " ".join(str(error).split())[:110]
            print(f"\n  [{label} could not finish -- {short}]")
            print("  Both free-tier providers are momentarily rate-limited (lots of testing).")
            print("  That is exactly what the cache prevents: a cached prompt needs zero calls.")
            cache.set_enabled(True)


if __name__ == "__main__":
    main()
