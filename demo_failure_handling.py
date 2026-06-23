r"""
Phase 8 demo -- graceful failure on messy prompts (no LLM calls).

Each case prints the deterministic InputDiagnosis: the severity, the reasons,
the assumptions to be carried forward (which the pipeline later writes into
AppBlueprint.assumptions), and a clarifying question when the prompt is empty.
"""

from pipeline import analyze_request

CASES = [
    ("EMPTY",         ""),
    ("TOO SHORT",     "app"),
    ("VAGUE",         "Make me an app."),
    ("CONFLICTING",   "Build a notes app with no login but with role-based access for admins."),
    ("CONFLICTING 2", "A blog with no database, but it should save all the posts forever."),
    ("UNDERSPECIFIED", "A todo app with projects and tasks."),
    ("CLEAN",         "Build a CRM with login, contacts, dashboard, role-based access, "
                       "premium plan with payments, and an admin-only analytics page."),
]


def main() -> None:
    for label, request in CASES:
        print("=" * 72)
        print(f"{label}: {request!r}")
        print("=" * 72)
        d = analyze_request(request)
        print(f"  severity: {d.severity.value}")
        for r in d.reasons:
            print(f"    - reason: {r}")
        for a in d.assumptions:
            print(f"    + assume: {a}")
        if d.clarifying_question:
            print(f"    ? clarify: {d.clarifying_question}")
        if d.severity.value == "ok":
            print("    (clean prompt -- pipeline proceeds without injected assumptions)")
        print()


if __name__ == "__main__":
    main()
