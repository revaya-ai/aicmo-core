"""The reject / QC-fail loop: a sent-back post must actually re-draft and land
back in front of the human, not stall at 'captured'. (QA blocker, v2 merge.)"""

import json
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db
from engine.brain import generate as brain
from engine.dashboard import notion_provision, notion_sync
from engine.studio import brand_qc, render


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)  # stub mode
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(notion_provision, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(notion_sync, "OUT_DIR", str(tmp_path / "out"))
    db.init_db()
    return tmp_path


def _post_at_review():
    pid = db.create_post("lumen-skin", "why competitors all sound the same")
    brain.run(pid)
    render.run(pid)
    brand_qc.run(pid)
    assert db.get_post(pid)["status"] == "qc_review"
    return pid


def _reject_on_board(board_path, comment):
    data = json.load(open(board_path))
    for c in data["cards"]:
        if c["status_label"] == "In Review":
            c["status_label"] = "Rejected"
            c["client_comment"] = comment
    json.dump(data, open(board_path, "w"))


def test_reject_redrafts_and_returns_to_review(isolated):
    notion_provision.provision_client("lumen-skin")
    pid = _post_at_review()
    notion_sync.push("lumen-skin")

    board = os.path.join(notion_sync.OUT_DIR, "lumen-skin-board.json")
    _reject_on_board(board, "soften the competitor line")

    applied = notion_sync.pull_gate("lumen-skin")

    assert (pid, "rejected_and_redrafted") in applied
    post = db.get_post(pid)
    assert post["status"] == "qc_review"                  # came back, did not stall
    assert "soften the competitor line" in post["body"]   # comment folded into re-draft


def test_pull_is_idempotent_after_reject(isolated):
    notion_provision.provision_client("lumen-skin")
    pid = _post_at_review()
    notion_sync.push("lumen-skin")
    _reject_on_board(os.path.join(notion_sync.OUT_DIR, "lumen-skin-board.json"),
                     "tighten the hook")
    notion_sync.pull_gate("lumen-skin")            # first pass re-drafts + syncs back

    second = notion_sync.pull_gate("lumen-skin")   # nothing left to do
    assert second == []
    assert db.get_post(pid)["status"] == "qc_review"
