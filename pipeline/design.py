"""Stage 2 -- System design.  IntentSpec -> SystemDesign.

Turns the "what" (intent) into the "how" (architecture): entities and fields,
relationships, roles and permissions, user flows, and high-level business rules.
"""

from contracts import IntentSpec, SystemDesign
from pipeline._prompting import run_stage, schema_text


def design_system(intent: IntentSpec) -> SystemDesign:
    prompt = (
        "You are the SYSTEM-DESIGN stage. Given the structured intent, design the "
        "app's architecture: the data entities and their fields, how the entities "
        "relate, the roles and their permissions, the key user flows, and the "
        "high-level business rules.\n\n"
        "Naming: entity names in PascalCase singular (e.g. 'Contact'); field "
        "names in snake_case. Give every entity an 'id' field.\n\n"
        f"Return JSON matching this schema:\n{schema_text(SystemDesign)}\n\n"
        f"INTENT:\n{intent.model_dump_json(indent=2)}"
    )
    return run_stage("design", prompt, SystemDesign)
