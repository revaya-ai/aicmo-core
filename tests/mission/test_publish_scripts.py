"""Task 7 — publish scheduler, publish_check, and engagement_sync tests.

TDD: these tests are written first (RED), then the modules are implemented (GREEN).
"""

import json
import os

import pytest

import db
from engine.dashboard import notion_sync
from engine.mission import engagement_sync, publish, publish_check


@pytest.fixture
def offline_tmp(tmp_path, monkeypatch):
    """Isolated DB + no Notion/Zernio keys + isolated notion OUT_DIR."""
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("ZERNIO_API_KEY", raising=False)
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(notion_sync, "OUT_DIR", str(tmp_path / "out"))
    db.init_db()
    return tmp_path


# ---------------------------------------------------------------------------
# publish.run(client) — scheduler mode
# ---------------------------------------------------------------------------


def test_due_scheduled_post_publishes(offline_tmp, monkeypatch):
    """A scheduled post with a past scheduled_for becomes published after publish.run(client)."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.SCHEDULED, scheduled_for="2000-01-01T00:00:00")  # past = due
    publish.run("lumen-skin")
    assert db.get_post(pid)["status"] == "published"


def test_due_post_gets_published_url(offline_tmp, monkeypatch):
    """A due scheduled post must have a published_url after publish.run(client)."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.SCHEDULED, scheduled_for="2000-01-01T00:00:00")
    publish.run("lumen-skin")
    post = db.get_post(pid)
    assert post["published_url"]


def test_future_scheduled_post_not_published(offline_tmp, monkeypatch):
    """A scheduled post with a future scheduled_for must NOT be published by publish.run(client)."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.SCHEDULED, scheduled_for="2099-01-01T00:00:00")  # future
    publish.run("lumen-skin")
    assert db.get_post(pid)["status"] == "scheduled"


def test_station_signature_still_works(offline_tmp, monkeypatch):
    """publish.run(post_id, auto_approve) per-post station signature still functions."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.SCHEDULED, scheduled_for="2000-01-01T00:00:00")
    # call with positional post_id — driver.drive uses this form
    publish.run(pid, auto_approve=False)
    assert db.get_post(pid)["status"] == "published"


# ---------------------------------------------------------------------------
# publish_check.run(client)
# ---------------------------------------------------------------------------


def test_publish_check_live_url_no_error(offline_tmp, monkeypatch):
    """publish_check on a live URL (offline fallback = treat as live) leaves qc_notes clean."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.PUBLISHED, published_url="https://social.test/p/1")
    publish_check.run("lumen-skin")
    post = db.get_post(pid)
    notes = post["qc_notes"] or ""
    assert "publish_error" not in notes


def test_publish_check_missing_url_flags_error(offline_tmp, monkeypatch):
    """publish_check with no published_url must write publish_error to qc_notes."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.PUBLISHED, published_url=None)
    publish_check.run("lumen-skin")
    post = db.get_post(pid)
    assert "publish_error" in (post["qc_notes"] or "")


# ---------------------------------------------------------------------------
# engagement_sync.run(client) — Notion write-back
# ---------------------------------------------------------------------------


def test_engagement_sync_writes_metrics_and_notion(offline_tmp, monkeypatch):
    """After engagement_sync.run: metrics_json is set AND notion push_metrics is called."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.PUBLISHED, published_url="https://social.test/p/1")
    pushed = {"hit": False}
    monkeypatch.setattr(
        "engine.dashboard.notion_sync.push_metrics",
        lambda c: pushed.__setitem__("hit", True) or 0,
    )
    engagement_sync.run("lumen-skin")
    assert db.get_post(pid)["metrics_json"]   # real (or fallback) metrics stored
    assert pushed["hit"] is True               # engagement pushed back to Notion


def test_engagement_sync_also_covers_analyzed_posts(offline_tmp, monkeypatch):
    """engagement_sync should refresh metrics for analyzed posts too (not just published)."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.PUBLISHED, published_url="https://social.test/p/1")
    db.advance(pid, db.Status.ANALYZED, metrics_json='{"likes":1}')
    pushed = {"count": 0}
    monkeypatch.setattr(
        "engine.dashboard.notion_sync.push_metrics",
        lambda c: pushed.__setitem__("count", pushed["count"] + 1) or 0,
    )
    engagement_sync.run("lumen-skin")
    assert db.get_post(pid)["metrics_json"]
    assert pushed["count"] >= 1


def test_engagement_sync_does_not_set_approved(offline_tmp, monkeypatch):
    """HARD CONSTRAINT: engagement_sync must never set status to approved."""
    monkeypatch.setattr(db, "DB_PATH", str(offline_tmp / "t.db"))
    pid = db.create_post("lumen-skin", "seed")
    db.advance(pid, db.Status.PUBLISHED, published_url="https://social.test/p/1")
    monkeypatch.setattr(
        "engine.dashboard.notion_sync.push_metrics",
        lambda c: 0,
    )
    engagement_sync.run("lumen-skin")
    post = db.get_post(pid)
    assert post["status"] != db.Status.APPROVED
