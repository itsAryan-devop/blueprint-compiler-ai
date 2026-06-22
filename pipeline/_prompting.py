"""Small shared helpers for the pipeline stages.

Two things every stage needs: the compact JSON Schema of its OWN contract to put
in the prompt, and one place that runs a stage (generate + validate) with tidy
progress logging.

The key Phase 3 idea lives here: each stage embeds only its own small schema --
one layer, never the whole blueprint -- which is what makes staged generation
cheaper, more reliable, and more deterministic than a single giant call.
"""

import json

from llm import generate_model


def schema_text(model_class) -> str:
    """Compact JSON Schema for a single contract, plus an explicit instruction to
    return an INSTANCE (not the schema).

    The schema lets the Groq fallback (which has no native structured-output mode)
    know the exact target shape; the instruction stops weaker models from echoing
    the schema back instead of filling it in.
    """
    schema = json.dumps(model_class.model_json_schema())
    return (
        f"{schema}\n\n"
        "Return a concrete JSON object filled with REAL values for this specific "
        "app. Do NOT return the schema itself, and do NOT include schema keywords "
        "like '$defs', 'properties', 'title', or 'type' at the top level."
    )


def run_stage(label: str, prompt: str, schema):
    """Run one pipeline stage: send the prompt, validate the reply into ``schema``."""
    print(f"      - {label} ...", flush=True)
    try:
        result = generate_model(prompt, schema)
    except Exception as error:
        print(f"      - {label}: FAILED ({type(error).__name__}: {error})")
        raise
    print(f"      - {label}: ok")
    return result
