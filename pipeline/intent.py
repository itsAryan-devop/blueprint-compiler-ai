"""Stage 1 -- Intent extraction.  English request -> IntentSpec.

Uses only its own small schema. This stage does not invent architecture; it just
captures a faithful, structured reading of what the user asked for.
"""

from contracts import IntentSpec
from pipeline._prompting import run_stage, schema_text


def extract_intent(request: str) -> IntentSpec:
    prompt = (
        "You are the INTENT-EXTRACTION stage of a compiler that turns an app "
        "request into a structured specification.\n\n"
        "Read the request and capture ONLY what the user asked for: a short app "
        "name, the app type, a one-line summary, the list of features, and the "
        "user roles. If the request was vague, record the assumptions you made; "
        "if it was self-contradictory, record the conflicts and how you resolved "
        "them. Do NOT invent architecture yet (no tables, endpoints, or pages).\n\n"
        f"Return JSON matching this schema:\n{schema_text(IntentSpec)}\n\n"
        f"USER REQUEST:\n{request}"
    )
    return run_stage("intent", prompt, IntentSpec)
