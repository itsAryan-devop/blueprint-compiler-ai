"""Small shared helpers for the pipeline stages.

Two things every stage needs: the compact JSON Schema of its OWN contract to put
in the prompt, and one place that runs a stage (generate + validate) with tidy
progress logging.

The key Phase 3 idea lives here: each stage embeds only its own small schema --
one layer, never the whole blueprint -- which is what makes staged generation
cheaper, more reliable, and more deterministic than a single giant call.
"""

import json

from pydantic import ValidationError

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
    """Run one pipeline stage: send the prompt, validate the reply into ``schema``.

    The Phase 5 "targeted regen" principle applied at stage boundaries: if the
    LLM produces JSON that parses but violates the contract (e.g. an unknown
    enum value, a missing required field), re-ask ONCE with the exact errors
    appended -- "fix only this" -- before giving up. This stops the whole
    pipeline from crashing on a single repairable per-stage slip.
    """
    print(f"      - {label} ...", flush=True)
    try:
        result = generate_model(prompt, schema)
    except ValidationError as error:
        issues = "\n".join(
            f"- {'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}"
            for e in error.errors()
        )
        print(f"      - {label}: validation failed; requesting targeted fix ...", flush=True)
        fix_prompt = (
            prompt
            + "\n\nYOUR PREVIOUS OUTPUT FAILED CONTRACT VALIDATION. The schema's "
              "allowed values are strict (notably any enum fields). Fix ONLY these "
              "errors and return valid JSON:\n"
            + issues
        )
        try:
            result = generate_model(fix_prompt, schema)
            print(f"      - {label}: ok (after targeted repair)", flush=True)
            return result
        except Exception as repair_error:
            print(f"      - {label}: FAILED after repair ({type(repair_error).__name__}: {repair_error})")
            raise
    except Exception as error:
        print(f"      - {label}: FAILED ({type(error).__name__}: {error})")
        raise
    print(f"      - {label}: ok")
    return result
