# tests/guardrails/test_compliance.py
"""TDD tests for Task 5b: cosmetic-claims compliance gate."""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from engine.guardrails import compliance


def test_drug_claim_flagged():
    r = compliance.check("lumen-skin", "This serum cures acne and is clinically proven to heal scars.")
    assert r["passed"] is False
    assert any(k in " ".join(r["violations"]).lower() for k in ("cure", "heal", "clinically proven"))


def test_clean_copy_passes():
    r = compliance.check("lumen-skin", "A simple routine that helps your skin look calmer in four weeks.")
    assert r["passed"] is True


def test_no_ruleset_passes():
    assert compliance.check("client-with-no-rules", "anything goes")["passed"] is True
