"""TDD tests for Task 5: captured-sweep + cron_cycle orchestrator.

Hermetic isolation:
  - DB_PATH → tmp_path
  - NOTION_TOKEN removed → stub board mode
  - ANTHROPIC_API_KEY removed → offline fallbacks in ai_cmo_generate + brand_qc
  - notion_provision.STATE_PATH → tmp_path
  - notion_sync.OUT_DIR → tmp_path
  - render.run monkeypatched → sets image_path to None (no playwright, no disk writes)
"""

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db
from engine import cycle
from engine.dashboard import notion_provision, notion_sync
from engine.studio import render


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    # Keys
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # DB isolation
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))

    # Notion stub paths
    monkeypatch.setattr(notion_provision, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(notion_sync, "OUT_DIR", str(tmp_path / "out"))

    # render.run: monkeypatch to a no-op that sets image_path=None (no playwright)
    # brand_qc.run sees no image_path and no ANTHROPIC_API_KEY → needs_revision
    # BUT: we need qc_review path. So we patch render to set a fake (missing) path
    # and let brand_qc's no-API-key stub path produce qc_review directly.
    def _stub_render(post_id, auto_approve=False):
        # Set image_path to a non-existent path so brand_qc's guard fires,
        # BUT brand_qc checks for ANTHROPIC_API_KEY *first* only when image exists.
        # Safest: set image_path to empty string → brand_qc stub path → qc_review.
        # brand_qc: if not img or not img.exists() → needs_revision
        #           elif not ANTHROPIC_API_KEY → qc_review (stub pass)
        # We need ANTHROPIC_API_KEY absent AND image present but we can't create PNG.
        # Solution: leave image_path unset (None); brand_qc fallthrough is needs_revision.
        # Override: patch brand_qc.run too so it always advances to qc_review.
        pass  # handled by brand_qc patch below

    from engine.studio import brand_qc

    def _stub_brand_qc(post_id, auto_approve=False):
        from db import Status, advance
        advance(post_id, Status.QC_REVIEW, qc_score=90, qc_notes="STUB: test patch")

    monkeypatch.setattr(render, "run", _stub_render)
    monkeypatch.setattr(brand_qc, "run", _stub_brand_qc)

    db.init_db()
    return tmp_path


def test_sweep_moves_captured_to_qc_review(isolated):
    db.create_post("lumen-skin", "idea one")
    db.create_post("lumen-skin", "idea two")

    n = cycle.sweep("lumen-skin")

    assert n == 2
    qr_posts = db.list_by_status(db.Status.QC_REVIEW)
    assert len(qr_posts) == 2
    assert all(p["client"] == "lumen-skin" for p in qr_posts)
    assert {p["status"] for p in qr_posts} == {"qc_review"}


def test_no_script_ever_sets_approved(isolated):
    db.create_post("lumen-skin", "idea")

    result = cycle.cron_cycle("lumen-skin")

    # No human set Approved in the stub board → zero approved rows
    assert db.list_by_status(db.Status.APPROVED) == []
    # cron_cycle ran with zero driven (no human approvals)
    assert result["driven"] == 0


def test_sweep_returns_zero_when_no_captured(isolated):
    # No captured rows for this client
    n = cycle.sweep("lumen-skin")
    assert n == 0


def test_sweep_only_processes_target_client(isolated):
    db.create_post("lumen-skin", "lumen idea")
    db.create_post("other-client", "other idea")

    n = cycle.sweep("lumen-skin")

    assert n == 1
    # other-client's post stays captured
    assert len(db.list_by_status(db.Status.CAPTURED)) == 1
    assert db.list_by_status(db.Status.CAPTURED)[0]["client"] == "other-client"


def test_cron_cycle_returns_swept_count(isolated):
    db.create_post("lumen-skin", "idea one")
    db.create_post("lumen-skin", "idea two")

    result = cycle.cron_cycle("lumen-skin")

    assert result["swept"] == 2
    assert isinstance(result["driven"], int)


def test_sweep_idempotent_on_already_swept(isolated):
    """Posts already at qc_review must not be re-swept."""
    db.create_post("lumen-skin", "idea one")
    cycle.sweep("lumen-skin")  # first sweep
    n2 = cycle.sweep("lumen-skin")  # second sweep, nothing captured
    assert n2 == 0
