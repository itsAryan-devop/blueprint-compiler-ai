"""Phase 8 -- failure handling for messy user prompts (no LLM).

Deterministic, code-only checks run BEFORE generation:
  * empty / too-short                -> ask a clarifying question (do not call AI)
  * vague (no concrete entities)     -> proceed with explicit assumptions
  * conflicting / self-contradictory -> proceed with a documented resolution
  * underspecified (e.g. no roles)   -> proceed with a sensible default + note

The point: vague / conflicting / underspecified prompts must NOT crash and must
NOT silently guess. They either get a clarifying question, or they get a
documented assumption that flows all the way into AppBlueprint.assumptions.
"""

from enum import Enum

from pydantic import BaseModel, Field

MIN_CHARS = 8
VAGUE_PHRASES = (
    "make me an app", "build an app", "build a app", "make an app", "create an app",
    "make app", "build something", "an app", "the app", "any app", "idk",
)
# Cheap "do we see real nouns describing a domain?" signal.
DOMAIN_HINTS = (
    "crm", "todo", "task", "shop", "store", "blog", "chat", "wiki", "calendar",
    "note", "habit", "expense", "invoice", "booking", "library", "forum",
    "dashboard", "tracker", "manager", "portal", "list", "feed", "inventory",
    "ticket", "issue", "project", "contact", "user", "customer", "product",
    "order", "payment", "post", "comment", "event", "appointment",
)
# Negation -> capability pairs that often contradict each other.
NEGATION_PAIRS = (
    (("no login", "without login", "no auth", "without auth"),
     ("role", "admin", "user account", "permission", "premium", "paid plan", "login required")),
    (("no database", "no storage"),
     ("save", "store", "history", "record", "list of")),
    (("no payments", "free only", "free forever"),
     ("premium", "paid", "subscription", "payment")),
)


class Severity(str, Enum):
    OK = "ok"                     # nothing to flag
    UNDERSPECIFIED = "minor"      # proceed with a small documented assumption
    VAGUE = "vague"               # proceed with several explicit assumptions
    CONFLICTING = "conflicting"   # proceed with a documented resolution
    EMPTY = "empty"               # ask a clarifying question, do not call the AI


class InputDiagnosis(BaseModel):
    severity: Severity
    reasons: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    clarifying_question: str | None = None


def _has_domain_hint(text: str) -> bool:
    return any(hint in text for hint in DOMAIN_HINTS)


def _conflicts(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for negs, caps in NEGATION_PAIRS:
        if any(n in text for n in negs):
            for cap in caps:
                if cap in text:
                    found.append((next(n for n in negs if n in text), cap))
                    break
    return found


def analyze_request(request: str) -> InputDiagnosis:
    """Look at the raw prompt and decide how the pipeline should handle it."""
    text = (request or "").strip().lower()

    if len(text) < MIN_CHARS:
        return InputDiagnosis(
            severity=Severity.EMPTY,
            reasons=["Prompt is empty or too short to compile an app from."],
            clarifying_question=(
                "Could you describe the app you want? A one-line description plus "
                "the main features and user roles is enough -- e.g. 'CRM with login, "
                "contacts, and an admin-only analytics page'."
            ),
        )

    conflict_pairs = _conflicts(text)
    if conflict_pairs:
        reasons, assumptions = [], []
        for neg, cap in conflict_pairs:
            reasons.append(f"Request says '{neg}' but also mentions '{cap}'.")
            if "login" in neg or "auth" in neg:
                assumptions.append(
                    f"Request was contradictory ('{neg}' vs '{cap}'). Resolved: "
                    f"enable a minimal login because '{cap}' requires it."
                )
            elif "database" in neg or "storage" in neg:
                assumptions.append(
                    f"Request was contradictory ('{neg}' vs '{cap}'). Resolved: "
                    f"use a small database because '{cap}' implies persistence."
                )
            elif "payments" in neg or "free" in neg:
                assumptions.append(
                    f"Request was contradictory ('{neg}' vs '{cap}'). Resolved: "
                    f"keep the app free and drop the '{cap}' feature."
                )
        return InputDiagnosis(severity=Severity.CONFLICTING, reasons=reasons, assumptions=assumptions)

    # Flag VAGUE only when an explicit vague marker is present (e.g. "make me an
    # app"). Absence of a domain hint alone is too aggressive -- our keyword
    # whitelist will never cover every legitimate domain ("knowledge base",
    # "fleet maintenance", ...), and a short clear prompt should pass through
    # rather than be mislabelled vague.
    if any(p in text for p in VAGUE_PHRASES):
        return InputDiagnosis(
            severity=Severity.VAGUE,
            reasons=["Request is vague: no concrete app type or domain mentioned."],
            assumptions=[
                "Request was vague; assumed a generic task-manager app.",
                "Assumed standard email + password authentication.",
                "Assumed two roles: 'user' (default) and 'admin'.",
            ],
        )

    # Domain is clear; just nudge a couple of safe defaults so the pipeline
    # never has to silently guess.
    underspec = []
    if "role" not in text and "admin" not in text and "permission" not in text:
        underspec.append("No roles mentioned; assumed a single 'user' role.")
    if "login" not in text and "auth" not in text and "sign in" not in text and "sign up" not in text:
        underspec.append("Authentication not mentioned; assumed standard email + password login.")
    if underspec:
        return InputDiagnosis(severity=Severity.UNDERSPECIFIED, assumptions=underspec)
    return InputDiagnosis(severity=Severity.OK)
