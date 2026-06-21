"""tests/mission/test_notion_metrics_push.py — TDD tests for notion_metrics_push."""

import db
from engine.mission import notion_metrics_push


def test_metrics_push_calls_notion(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.ANALYZED, metrics_json='{"likes": 10, "impressions": 1000}')
    pushed = {"hit": False}
    monkeypatch.setattr("engine.dashboard.notion_sync.push_metrics",
                        lambda c: pushed.__setitem__("hit", True) or 1)
    notion_metrics_push.run("lumen-skin")
    assert pushed["hit"] is True


def test_metrics_push_returns_post_count(monkeypatch, tmp_path):
    """run() returns the count of posts with metrics_json."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t2.db"))
    db.init_db()
    # Two analyzed posts with metrics, one without
    pid1 = db.create_post("lumen-skin", "post1")
    db.advance(pid1, db.Status.ANALYZED, metrics_json='{"likes": 5, "impressions": 500}')
    pid2 = db.create_post("lumen-skin", "post2")
    db.advance(pid2, db.Status.ANALYZED, metrics_json='{"likes": 20, "impressions": 2000}')
    pid3 = db.create_post("lumen-skin", "post3")
    db.advance(pid3, db.Status.ANALYZED)  # no metrics_json

    monkeypatch.setattr("engine.dashboard.notion_sync.push_metrics", lambda c: 1)
    count = notion_metrics_push.run("lumen-skin")
    assert count == 2


def test_metrics_push_skips_other_clients(monkeypatch, tmp_path):
    """Posts from other clients are not counted."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t3.db"))
    db.init_db()
    pid = db.create_post("other-client", "other post")
    db.advance(pid, db.Status.ANALYZED, metrics_json='{"likes": 99, "impressions": 9999}')

    monkeypatch.setattr("engine.dashboard.notion_sync.push_metrics", lambda c: 1)
    count = notion_metrics_push.run("lumen-skin")
    assert count == 0
