"""Batch cadence scheduler — spread multiple posts across active posting slots.

This module is interactive, never auto. Call `schedule(client)` on demand to
assign non-colliding `scheduled_for` datetimes to all posts that need one.
It does NOT change any post's `status`. It only writes `scheduled_for`.

Status set chosen: APPROVED only.
  Rationale: APPROVED posts have passed human review and are ready to be
  placed on the calendar. SCHEDULED posts either already have a slot (from
  the single-post scheduler in engine/mission/schedule.py) or were placed
  there by a previous cadence run — either way they don't need a new one.
  This keeps the two schedulers complementary, not overlapping.

Collision avoidance:
  We walk a rotating cursor through ACTIVE_SLOTS day by day. Each slot is
  claimed exactly once per day. The cursor advances to the next slot (and
  next day if the current day is exhausted) until every post has a unique
  future datetime. Already-claimed slots are tracked in a set.
"""

import engine.env  # noqa: F401 — side-effect: loads .env

from datetime import datetime, timedelta
from typing import Optional

import db
from db import Status

# ---------------------------------------------------------------------------
# Module-level active posting slots (timezone-naive local-time placeholders).
# Replace these with the audience's real peak-engagement hours derived from
# analytics. Times are HH:MM strings; sorted ascending within each day.
# ---------------------------------------------------------------------------
ACTIVE_SLOTS = ["09:00", "12:00", "17:00"]


def _slot_iter(now: datetime):
    """Yield (datetime, slot_str) for each active slot from `now` onward.

    Walks ACTIVE_SLOTS within each day. Skips any slot whose datetime is
    in the past relative to `now`. Infinite generator — caller stops when done.
    """
    current_day = now.date()
    while True:
        for slot_str in ACTIVE_SLOTS:
            hour, minute = (int(p) for p in slot_str.split(":"))
            candidate = datetime(
                current_day.year,
                current_day.month,
                current_day.day,
                hour,
                minute,
                0,
            )
            if candidate >= now:
                yield candidate, slot_str
        current_day += timedelta(days=1)


def schedule(client: str, now: Optional[datetime] = None) -> list:
    """Assign non-colliding scheduled_for datetimes to all eligible posts.

    Eligible posts: status == APPROVED with no scheduled_for set (NULL or empty).
    Only writes `scheduled_for` via db.update_post. Never changes status.

    Args:
        client:  The client slug (e.g. "lumen-skin"). Used to filter posts.
        now:     Anchor datetime for slot generation. Accepts any datetime so
                 tests are fully deterministic. Defaults to datetime.utcnow()
                 when not supplied (do not call with no injection point in tests).

    Returns:
        List of (post_id, scheduled_for_iso_str) tuples in assignment order.
    """
    if now is None:
        now = datetime.utcnow()

    # Gather eligible posts: APPROVED, this client, no scheduled_for yet.
    candidates = [
        p
        for p in db.list_by_status(Status.APPROVED)
        if p["client"] == client and not p.get("scheduled_for")
    ]

    if not candidates:
        return []

    assigned: list = []
    claimed: set = set()  # ISO strings already taken in this run

    slot_gen = _slot_iter(now)

    for post in candidates:
        # Advance the generator until we find a slot not yet claimed.
        while True:
            slot_dt, _ = next(slot_gen)
            slot_iso = slot_dt.isoformat()
            if slot_iso not in claimed:
                claimed.add(slot_iso)
                break

        db.update_post(post["id"], scheduled_for=slot_iso)
        assigned.append((post["id"], slot_iso))

    return assigned
