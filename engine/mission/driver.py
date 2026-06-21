"""The shared downstream conveyor for Card 3.

Given a post that a human just approved (status == approved), run the remaining
mission stations in order until the next human stop. Both run.py (auto demo) and
the Flask board's Approve handler call this, so there is one pipeline, two doors.
"""

from db import get_post
from engine.mission import schedule, publish, analytics
from engine.ads import ads_agent


def drive(post_id: str, auto_approve: bool = False) -> str:
    """Walk approved -> scheduled -> published -> analyzed -> ad_* ; return final status."""
    schedule.run(post_id, auto_approve=auto_approve)
    publish.run(post_id, auto_approve=auto_approve)
    analytics.run(post_id, auto_approve=auto_approve)
    ads_agent.run(post_id, auto_approve=auto_approve)
    return get_post(post_id)["status"]
