r"""
Phase 2 walking skeleton -- the first time we actually call the AI end-to-end.

Flow:  English request  ->  ONE LLM call (JSON mode, temperature 0)  ->  parse
       ->  validate against the AppBlueprint contract  ->  print.

This is deliberately a SINGLE call. The task forbids that as a *final* design --
we split it into four proper stages in Phase 3. The point now is only to prove
the whole pipe runs once: prompt in, validated blueprint out.

Run with:
    .\venv\Scripts\python.exe walking_skeleton.py
    .\venv\Scripts\python.exe walking_skeleton.py "Build a todo app with projects and due dates"
"""

import json
import sys

from pydantic import ValidationError

from contracts import AppBlueprint
from llm import LLMError, Provider, complete_json, parse_json

DEFAULT_REQUEST = (
    "Build a CRM with login, contacts, dashboard, role-based access, and a "
    "premium plan with payments. Admins can see analytics."
)


def build_prompt(user_request: str) -> str:
    """Wrap the user's request with the target JSON Schema + strict instructions."""
    schema = json.dumps(AppBlueprint.model_json_schema())
    return (
        "You are a deterministic compiler that converts an app request into a "
        "strict application blueprint expressed as JSON.\n\n"
        f"APP REQUEST:\n{user_request}\n\n"
        "Produce a single JSON object that conforms EXACTLY to this JSON Schema:\n"
        f"{schema}\n\n"
        "Rules:\n"
        "- Output ONLY the JSON object, nothing else.\n"
        "- Include every required field; do NOT add any field not in the schema.\n"
        "- Use only the allowed enum values.\n"
        "- Keep the layers consistent: every UI field should map to an API field, "
        "every API field to a database column, and every role referenced in "
        "business logic must exist in the auth schema."
    )


def generate(user_request: str) -> tuple[str, Provider]:
    """Try Gemini first, fall back to Groq. Return (raw_json_text, provider_used)."""
    prompt = build_prompt(user_request)
    last_error: Exception | None = None
    for provider in (Provider.GEMINI, Provider.GROQ):
        schema = AppBlueprint if provider is Provider.GEMINI else None
        try:
            print(f"[{provider.value}] generating...")
            raw = complete_json(prompt, provider=provider, response_schema=schema)
            return raw, provider
        except LLMError as error:
            last_error = error
            print(f"[{provider.value}] failed: {error}\n -> trying next provider")
    raise LLMError(f"All providers failed. Last error: {last_error}")


def main() -> None:
    user_request = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REQUEST
    print("=" * 72)
    print("WALKING SKELETON  --  English request -> one LLM call -> blueprint")
    print("=" * 72)
    print(f"Request: {user_request}\n")

    raw, provider = generate(user_request)

    print(f"\n--- RAW JSON returned by {provider.value} ---")
    data = parse_json(raw)
    print(json.dumps(data, indent=2))

    print("\n--- VALIDATION against the AppBlueprint contract ---")
    blueprint = None
    try:
        blueprint = AppBlueprint.model_validate(data)
    except ValidationError as error:
        issues = error.errors()
        print(f"Contract REJECTED the output: {len(issues)} issue(s) found.")
        for issue in issues:
            location = ".".join(str(part) for part in issue["loc"])
            print(f"  - {location}: {issue['msg']}")

    if blueprint is not None:
        print(f"Contract ACCEPTED the output. Blueprint for '{blueprint.app_name}':")
        print(
            f"  pages={len(blueprint.ui.pages)}  "
            f"endpoints={len(blueprint.api.endpoints)}  "
            f"tables={len(blueprint.database.tables)}  "
            f"roles={len(blueprint.auth.roles)}  "
            f"rules={len(blueprint.business_logic.rules)}"
        )
        if blueprint.assumptions:
            print(f"  assumptions: {blueprint.assumptions}")

    print("\n" + "=" * 72)
    print("PHASE 2 RESULT  --  pipe ran end-to-end: English -> AI -> JSON -> contract")
    print("=" * 72)
    if blueprint is not None:
        print("Outcome: the AI's output is a fully VALID blueprint.")
    else:
        print(
            "Outcome: the contract safety-net CAUGHT the AI's imperfect output -- "
            "this is EXPECTED and is the whole point.\n"
            "A single naive call is exactly what the task forbids as a final design.\n"
            "Phase 3 splits this into four stages; Phases 4-5 validate and auto-repair.\n"
            "'Ugly is fine' for a walking skeleton -- the goal was to run the pipe once,\n"
            "and it ran."
        )
    print("=" * 72)


if __name__ == "__main__":
    main()
