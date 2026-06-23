"""Stage 1 -- Intent extraction.  English request -> IntentSpec.

Uses only its own small schema. This stage does not invent architecture; it just
captures a faithful, structured reading of what the user asked for.

If Phase 8's input analyzer surfaced pre-pipeline assumptions (e.g. for a vague
or conflicting prompt), they are passed in and the LLM is explicitly told to
include them in IntentSpec.assumptions so they flow into the final blueprint.
"""

from contracts import IntentSpec
from pipeline._prompting import run_stage, schema_text


def extract_intent(request: str, prior_assumptions: list[str] | None = None) -> IntentSpec:
    prior_block = ""
    if prior_assumptions:
        prior_block = (
            "\nPRE-PIPELINE ASSUMPTIONS (deterministic input analysis): include "
            "these VERBATIM in IntentSpec.assumptions in addition to any others "
            "you record:\n"
            + "\n".join(f"- {a}" for a in prior_assumptions)
            + "\n"
        )
    prompt = (
        "You are the INTENT-EXTRACTION stage of a compiler that turns an app "
        "request into a structured specification.\n\n"
        "Read the request and capture ONLY what the user asked for: a short app "
        "name, the app type, a one-line summary, the list of features, and the "
        "user roles. If the request was vague, record the assumptions you made; "
        "if it was self-contradictory, record the conflicts and how you resolved "
        "them. Do NOT invent architecture yet (no tables, endpoints, or pages).\n"
        + prior_block
        + f"\nReturn JSON matching this schema:\n{schema_text(IntentSpec)}\n\n"
        + f"USER REQUEST:\n{request}"
    )
    intent = run_stage("intent", prompt, IntentSpec)
    if prior_assumptions:
        # Guarantee they survive even if the model trimmed them.
        existing = set(intent.assumptions)
        for a in prior_assumptions:
            if a not in existing:
                intent.assumptions.append(a)
    return intent
