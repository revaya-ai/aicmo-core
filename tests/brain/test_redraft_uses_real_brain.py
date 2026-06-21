"""Verify the re-draft loop routes through ai_cmo_generate, not the offline stub."""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db
from engine import feedback


def test_redraft_routes_through_ai_cmo_generate(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    db.init_db()
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.QC_REVIEW)
    import engine.brain.ai_cmo_generate as gen
    called = {"hit": False}
    orig = gen.run
    def spy(post_id, auto_approve=False):
        called["hit"] = True
        return orig(post_id, auto_approve)
    monkeypatch.setattr(gen, "run", spy)
    feedback.reject_and_redraft(pid, "make the hook sharper")
    assert called["hit"] is True
    assert db.get_post(pid)["status"] == "qc_review"
