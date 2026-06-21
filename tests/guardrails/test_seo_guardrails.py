# tests/guardrails/test_seo_guardrails.py
from engine.guardrails.seo_guardrails import score, BANNED


def test_banned_list_has_21():
    assert len(BANNED) == 21


def test_em_dash_fails():
    r = score("This is clean copy. It converts well.—really.")
    assert "no_dashes" in r["failures"]


def test_clean_copy_passes():
    r = score("I cut his reporting time by 12 hours a week. Here is how. "
              "One change. Three steps. It worked in 30 days.")
    assert r["passed"] is True
    assert r["score"] >= 8


def test_banned_phrase_fails():
    r = score("Let me help you leverage our seamless, world-class synergy.")
    assert r["passed"] is False
