"""End-to-end demo loop test.

Verifies that run.main() walks a post all the way to 'published' using the
real Brick chain wiring (ai_cmo_generate), falling back to the offline stub
when no ANTHROPIC_API_KEY is present (always true in CI and here).

Isolation strategy (mirrors tests/notion/test_reject_loop.py):
- db.DB_PATH          → tmp_path/t.db           (never touches real DB)
- notion_provision.STATE_PATH → tmp_path/state.json  (never writes real state)
- notion_sync.OUT_DIR → tmp_path/out             (never writes to outputs/)
- ANTHROPIC_API_KEY   deleted                    (offline brick chain)
- NOTION_TOKEN        deleted                    (stub Notion mode)
"""

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db
import run
from engine.dashboard import notion_provision, notion_sync


def test_demo_loop_reaches_published(monkeypatch, tmp_path, capsys):
    # Hermetic isolation
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(notion_provision, "STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setattr(notion_sync, "OUT_DIR", str(tmp_path / "out"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    # Force the ads winner path so the terminal status is always ad_live
    # (without this, the probabilistic winner_score can land below the 30.0
    # threshold and stop at 'analyzed').  DEMO_FORCE_WINNER is the designed
    # escape hatch in ads_agent — it does NOT affect the real cron path.
    monkeypatch.setenv("DEMO_FORCE_WINNER", "1")

    monkeypatch.setattr("sys.argv", ["run.py", "simple beats fancy"])
    run.main()

    out = capsys.readouterr().out
    # The full pipeline ends at ad_live (schedule -> publish -> analytics -> ads).
    # The brief spec said "final status: published" but the driver runs all the
    # way through the ads station to ad_live.  We assert the true terminal state.
    assert "final status: ad_live" in out
