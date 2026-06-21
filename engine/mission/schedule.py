"""STATION 3 — Mission: schedule an approved post.

Reads:  status == approved
Writes: status == scheduled   (sets scheduled_for, an ISO timestamp)

Signature: run(post_id: str, auto_approve: bool = False) -> None

The real version picks an optimal slot from the content calendar / posting
cadence. The stub just schedules it for "now + 1 hour".
"""

from datetime import datetime, timedelta

from db import Status, get_post, advance

# Best-time-to-post heuristic per platform: (hour, weekday_only).
BEST_TIME = {
    "linkedin": (9, True),    # 9am on a weekday
    "instagram": (11, False), # 11am any day
    "x": (8, True),
}
DEFAULT_SLOT = (10, False)


def _next_slot(platform: str, now: datetime) -> datetime:
    hour, weekday_only = BEST_TIME.get(platform, DEFAULT_SLOT)
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    if weekday_only:
        while candidate.weekday() >= 5:  # Sat=5, Sun=6
            candidate += timedelta(days=1)
    return candidate


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)
    slot = _next_slot(post["platform"], datetime.utcnow())
    advance(post_id, Status.SCHEDULED, scheduled_for=slot.isoformat())
