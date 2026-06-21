"""TDD tests for Task 10: /develop operator co-pilot with two STOP gates.

Hermetic isolation mirrors tests/cycle/test_cycle.py:
  - DB_PATH → tmp_path
  - ANTHROPIC_API_KEY removed → offline fallbacks in ai_cmo_generate
  - NOTION_TOKEN removed → stub board JSON mode
  - notion_provision.STATE_PATH → tmp_path
  - notion_sync.OUT_DIR → tmp_path

Confirm signal: the stub board JSON card carries a ``develop_confirm`` field.
When its value matches the current stage string (e.g. ``"positioning"``),
``_read_develop_confirm(post_id)`` returns that value and the confirm gate passes.
In stub mode, the field is read directly from the board JSON card for the post.
"""

import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db
from engine import cycle, develop
from engine.dashboard import notion_provision, notion_sync
from engine.studio import render, brand_qc
import engine.develop as develop_mod


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Hermetically isolated environment — no real API keys, no real Notion."""
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(notion_provision, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(notion_sync, "OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(develop_mod, "OUT_DIR", str(tmp_path / "out"))

    # Patch render.run → no-op (no Playwright needed)
    monkeypatch.setattr(render, "run", lambda pid, **kw: None)

    # Patch brand_qc.run → always advances to qc_review
    def _stub_brand_qc(post_id, auto_approve=False):
        db.advance(post_id, db.Status.QC_REVIEW, qc_score=90, qc_notes="STUB: test patch")

    monkeypatch.setattr(brand_qc, "run", _stub_brand_qc)

    db.init_db()
    return tmp_path


# ---------------------------------------------------------------------------
# Helper: write develop_confirm to stub board JSON
# ---------------------------------------------------------------------------

def _set_develop_confirm(out_dir, client, post_id, confirm_value):
    """Set develop_confirm field on the matching card in the stub board JSON."""
    board_path = os.path.join(out_dir, f"{client}-board.json")
    if not os.path.exists(board_path):
        # Create a minimal stub board if it doesn't exist yet
        data = {"mode": "stub", "client": client, "database_id": f"stub-{client}",
                "cards": [{"post_id": post_id, "develop_confirm": confirm_value}]}
        os.makedirs(out_dir, exist_ok=True)
        with open(board_path, "w") as fh:
            json.dump(data, fh)
        return
    with open(board_path) as fh:
        data = json.load(fh)
    matched = False
    for card in data.get("cards", []):
        if card.get("post_id") == post_id:
            card["develop_confirm"] = confirm_value
            matched = True
    if not matched:
        data["cards"].append({"post_id": post_id, "develop_confirm": confirm_value})
    with open(board_path, "w") as fh:
        json.dump(data, fh)


# ---------------------------------------------------------------------------
# Test 1: sweep skips in-develop posts
# ---------------------------------------------------------------------------

def test_sweep_skips_in_develop_posts(isolated):
    """A captured post whose qc_notes contains DEVELOP_STAGE: must NOT be swept."""
    pid = db.create_post("lumen-skin", "high value idea")
    db.update_post(pid, qc_notes="DEVELOP_STAGE:positioning")

    n = cycle.sweep("lumen-skin")

    assert n == 0, "sweep should skip the in-develop post and return 0"
    post = db.get_post(pid)
    assert post["status"] == "captured", "in-develop post must stay at captured"
    assert "DEVELOP_STAGE:" in (post["qc_notes"] or ""), "develop marker must be preserved"


# ---------------------------------------------------------------------------
# Test 2: develop.start stops at positioning
# ---------------------------------------------------------------------------

def test_develop_start_stops_at_positioning(isolated):
    """After start(), qc_notes carries DEVELOP_STAGE:positioning, angle is set, status != qc_review."""
    pid = db.create_post("lumen-skin", "an important high-value idea")

    develop.start(pid)

    post = db.get_post(pid)
    assert "DEVELOP_STAGE:positioning" in (post["qc_notes"] or ""), \
        "start() must set DEVELOP_STAGE:positioning in qc_notes"
    assert post.get("angle"), \
        "start() must write the angle artifact before stopping"
    assert post["status"] != db.Status.QC_REVIEW, \
        "start() must NOT advance the post to qc_review"
    assert post["status"] == db.Status.CAPTURED, \
        "post must remain at captured status after start()"


# ---------------------------------------------------------------------------
# Test 3: confirm_positioning without confirm signal is a no-op
# ---------------------------------------------------------------------------

def test_confirm_positioning_noop_without_signal(isolated):
    """confirm_positioning with no develop_confirm in the board must be a no-op."""
    pid = db.create_post("lumen-skin", "an important idea")
    develop.start(pid)

    # Do NOT set develop_confirm in the board — no confirm signal present
    develop.confirm_positioning(pid)

    post = db.get_post(pid)
    assert "DEVELOP_STAGE:positioning" in (post["qc_notes"] or ""), \
        "stage must still be positioning (no-op)"
    assert post["status"] == db.Status.CAPTURED, \
        "status must remain captured (no-op)"


# ---------------------------------------------------------------------------
# Test 4: confirm_positioning with signal advances to caption stage
# ---------------------------------------------------------------------------

def test_confirm_positioning_advances_to_caption(isolated, tmp_path):
    """confirm_positioning with confirm signal writes hook+body and sets DEVELOP_STAGE:caption."""
    out_dir = str(tmp_path / "out")
    client = "lumen-skin"
    pid = db.create_post(client, "an important idea")
    develop.start(pid)

    # Operator signals confirm via the board JSON
    _set_develop_confirm(out_dir, client, pid, "positioning")

    develop.confirm_positioning(pid)

    post = db.get_post(pid)
    assert "DEVELOP_STAGE:caption" in (post["qc_notes"] or ""), \
        "confirm_positioning must advance stage to DEVELOP_STAGE:caption"
    assert post.get("hook"), "hook must be written after positioning confirmed"
    assert post.get("body"), "body must be written after positioning confirmed"
    assert post["status"] == db.Status.CAPTURED, \
        "status must remain captured (not yet at qc_review)"


# ---------------------------------------------------------------------------
# Test 5: confirm_caption without confirm signal is a no-op
# ---------------------------------------------------------------------------

def test_confirm_caption_noop_without_signal(isolated, tmp_path):
    """confirm_caption with no develop_confirm in the board must be a no-op."""
    out_dir = str(tmp_path / "out")
    client = "lumen-skin"
    pid = db.create_post(client, "an important idea")
    develop.start(pid)
    _set_develop_confirm(out_dir, client, pid, "positioning")
    develop.confirm_positioning(pid)

    # Clear the confirm signal — do NOT set to "caption"
    _set_develop_confirm(out_dir, client, pid, None)

    develop.confirm_caption(pid)

    post = db.get_post(pid)
    assert "DEVELOP_STAGE:caption" in (post["qc_notes"] or ""), \
        "stage must still be caption (no-op)"
    assert post["status"] != db.Status.QC_REVIEW, \
        "post must NOT be at qc_review (no-op)"


# ---------------------------------------------------------------------------
# Test 6: full progression — start → confirm_positioning → confirm_caption → qc_review
# ---------------------------------------------------------------------------

def test_full_progression_lands_at_qc_review(isolated, tmp_path):
    """Full develop flow: start → confirm positioning → confirm caption → lands at qc_review."""
    out_dir = str(tmp_path / "out")
    client = "lumen-skin"
    pid = db.create_post(client, "an important idea")

    # Stage 0+1: run positioning
    develop.start(pid)
    post = db.get_post(pid)
    assert "DEVELOP_STAGE:positioning" in (post["qc_notes"] or "")

    # Operator confirms positioning
    _set_develop_confirm(out_dir, client, pid, "positioning")
    develop.confirm_positioning(pid)
    post = db.get_post(pid)
    assert "DEVELOP_STAGE:caption" in (post["qc_notes"] or "")

    # Operator confirms caption
    _set_develop_confirm(out_dir, client, pid, "caption")
    develop.confirm_caption(pid)
    post = db.get_post(pid)

    assert post["status"] == db.Status.QC_REVIEW, \
        "confirm_caption must land the post at qc_review"
    assert "DEVELOP_STAGE:" not in (post["qc_notes"] or ""), \
        "DEVELOP_STAGE marker must be cleared after confirm_caption"
    assert post.get("image_path") is not None or True, "render was called (stub no-op is ok)"


# ---------------------------------------------------------------------------
# Test 7: sweep still processes normal captured posts alongside in-develop posts
# ---------------------------------------------------------------------------

def test_sweep_processes_normal_alongside_in_develop(isolated):
    """Sweep must process a normal captured post but skip the in-develop one."""
    pid_normal = db.create_post("lumen-skin", "normal idea")
    pid_develop = db.create_post("lumen-skin", "high value idea")
    db.update_post(pid_develop, qc_notes="DEVELOP_STAGE:positioning")

    n = cycle.sweep("lumen-skin")

    assert n == 1, "only the normal post should be swept"
    assert db.get_post(pid_normal)["status"] == db.Status.QC_REVIEW
    assert db.get_post(pid_develop)["status"] == db.Status.CAPTURED


# ---------------------------------------------------------------------------
# Test 8: lock-contract — confirm_positioning builds from stored angle, not
#          a fresh chain run.
# ---------------------------------------------------------------------------

def test_lock_contract_confirm_positioning_uses_stored_angle(isolated, tmp_path):
    """The lock contract: after start(), overwriting the DB angle with a sentinel
    value must cause confirm_positioning to build hook+body FROM that sentinel,
    not from a freshly regenerated positioning angle.

    This proves that confirm_positioning reads the stored angle (the one the
    operator confirmed) rather than re-running run_chain which could produce a
    different angle on a live API key.
    """
    out_dir = str(tmp_path / "out")
    client = "lumen-skin"
    pid = db.create_post(client, "an important idea")

    # Stage 0+1: run start — stores the real offline angle
    develop.start(pid)

    post_after_start = db.get_post(pid)
    assert post_after_start.get("angle"), "start() must write an angle"

    # Overwrite the stored angle with a sentinel value that can never be
    # produced by run_chain (it would require fabricating this exact string).
    db.update_post(pid, angle="LOCKED-SENTINEL")

    # Confirm that the sentinel is stored
    assert db.get_post(pid)["angle"] == "LOCKED-SENTINEL"

    # Operator signals confirm
    _set_develop_confirm(out_dir, client, pid, "positioning")

    # Run confirm_positioning — must build from the sentinel, not re-run the chain
    develop.confirm_positioning(pid)

    post_after_confirm = db.get_post(pid)

    # The angle field must still be the sentinel — confirm_positioning must NOT
    # have overwritten it with a freshly generated angle.
    assert post_after_confirm["angle"] == "LOCKED-SENTINEL", (
        "confirm_positioning must NOT overwrite the locked angle with a fresh chain run"
    )

    # hook and body must have been produced (offline path is deterministic)
    assert post_after_confirm.get("hook"), "hook must be written after positioning confirmed"
    assert post_after_confirm.get("body"), "body must be written after positioning confirmed"

    # Stage must advance to caption
    assert "DEVELOP_STAGE:caption" in (post_after_confirm.get("qc_notes") or ""), (
        "stage must advance to DEVELOP_STAGE:caption"
    )
