"""Tests for ai_cmo_generate: offline fallback and phase-key ordering."""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db
from engine.brain import ai_cmo_generate


def test_offline_fallback_produces_draft(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    pid = db.create_post("lumen-skin", "why niacinamide is overhyped")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ai_cmo_generate.run(pid)
    post = db.get_post(pid)
    assert post["status"] == "drafted"
    assert post["angle"] and post["hook"] and post["body"] and post["pillar"]


def test_phases_lock_in_order(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    pid = db.create_post("lumen-skin", "simple routines win")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    artifacts = ai_cmo_generate.run_chain(pid)  # returns the locked artifacts dict
    assert list(artifacts) == ["voc", "intake", "topic", "angle", "hook", "story"]
