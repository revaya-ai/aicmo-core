"""Tests for engine/schedule_cadence.py — batch cadence scheduler.

Uses a tmp db (fresh_db fixture from tests/conftest.py + our local sys.path setup),
injects a fixed `now` so slot assignments are deterministic.
"""

import os
import sys
import pytest
from datetime import datetime

# Ensure repo root is on sys.path (this file lives in tests/, one level below root).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db
from db import Status


# ---------------------------------------------------------------------------
# Shared fixture: redirect db to a tmp file, init schema.
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_db(tmp_path):
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path / "test_aicmo.db")
    db.init_db()
    try:
        yield db
    finally:
        db.DB_PATH = original


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_two_posts_get_noncolliding_slots(fresh_db):
    """Two eligible posts must receive different, future scheduled_for values."""
    from engine import schedule_cadence

    # Fixed anchor: Monday 2025-01-06 at 08:00 UTC (before any active slot).
    now = datetime(2025, 1, 6, 8, 0, 0)

    post_a = db.create_post("lumen-skin", "seed-a")
    post_b = db.create_post("lumen-skin", "seed-b")
    # Advance both to APPROVED (no scheduled_for set).
    db.advance(post_a, Status.APPROVED)
    db.advance(post_b, Status.APPROVED)

    results = schedule_cadence.schedule("lumen-skin", now=now)

    # Both posts returned.
    assert len(results) == 2

    ids = [r[0] for r in results]
    slots = [r[1] for r in results]

    # Both appear in the result.
    assert set(ids) == {post_a, post_b}

    # Slots are non-colliding strings.
    assert slots[0] != slots[1]

    # Both slots are >= now.
    for slot_str in slots:
        slot_dt = datetime.fromisoformat(slot_str)
        assert slot_dt >= now, f"slot {slot_str} is before now={now}"

    # The db rows actually have scheduled_for written.
    for post_id, slot_str in results:
        post = db.get_post(post_id)
        assert post["scheduled_for"] == slot_str


def test_no_eligible_posts_returns_empty(fresh_db):
    """With an empty db (or no unscheduled eligible posts) the function returns []."""
    from engine import schedule_cadence

    now = datetime(2025, 1, 6, 8, 0, 0)
    result = schedule_cadence.schedule("lumen-skin", now=now)
    assert result == []


def test_does_not_touch_status(fresh_db):
    """Scheduling must only write scheduled_for; status must remain unchanged."""
    from engine import schedule_cadence

    now = datetime(2025, 1, 6, 8, 0, 0)

    post_id = db.create_post("lumen-skin", "seed-c")
    db.advance(post_id, Status.APPROVED)

    schedule_cadence.schedule("lumen-skin", now=now)

    post = db.get_post(post_id)
    # Status must still be APPROVED — the cadence scheduler never touches status.
    assert post["status"] == Status.APPROVED
    # Must not have accidentally promoted to anything else.
    assert post["status"] != Status.SCHEDULED
    assert post["status"] != "ad_approved"
