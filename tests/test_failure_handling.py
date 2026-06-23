"""Phase 8 unit tests for the input analyzer (no API calls)."""

from pipeline import analyze_request
from pipeline.input_analysis import Severity


def test_empty_prompt_yields_clarifying_question():
    d = analyze_request("")
    assert d.severity == Severity.EMPTY
    assert d.clarifying_question and "describe the app" in d.clarifying_question.lower()
    assert not d.assumptions  # do NOT silently guess


def test_too_short_prompt_yields_clarifying_question():
    d = analyze_request("app")
    assert d.severity == Severity.EMPTY


def test_vague_prompt_documents_assumptions():
    d = analyze_request("Make me an app.")
    assert d.severity == Severity.VAGUE
    assert len(d.assumptions) >= 2
    assert any("auth" in a.lower() or "login" in a.lower() for a in d.assumptions)


def test_no_login_but_roles_is_conflicting():
    d = analyze_request("Build a notes app with no login but role-based access for admins.")
    assert d.severity == Severity.CONFLICTING
    assert any("contradictory" in a.lower() for a in d.assumptions)
    assert any("login" in a.lower() for a in d.assumptions)


def test_no_database_but_save_is_conflicting():
    d = analyze_request("A blog with no database but it should save all the posts.")
    assert d.severity == Severity.CONFLICTING
    assert any("database" in a.lower() or "persistence" in a.lower() for a in d.assumptions)


def test_clear_prompt_with_login_and_roles_is_ok():
    d = analyze_request(
        "Build a CRM with login, contacts, dashboard, role-based access for admins, "
        "premium plan with payments, and analytics."
    )
    assert d.severity == Severity.OK


def test_underspecified_clear_domain_gets_safe_defaults():
    d = analyze_request("A todo app with projects and tasks.")
    assert d.severity == Severity.UNDERSPECIFIED
    assert d.assumptions  # safe defaults, not a hard failure


def test_legitimate_prompt_without_whitelisted_word_is_not_vague():
    # Regression: previously any prompt missing a word from our small DOMAIN_HINTS
    # whitelist was flagged VAGUE. A legitimate prompt should pass through to
    # underspecified-or-better instead.
    d = analyze_request("Build a knowledge base for our internal engineering teams.")
    assert d.severity != Severity.VAGUE
