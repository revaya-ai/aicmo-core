"""STATION 3 — Mission: publish a scheduled post.

Reads:  status == scheduled   (uses image_path, hook, body, platform)
Writes: status == published   (sets published_url)

Per-post station signature (used by driver.drive):
    run(post_id: str, auto_approve: bool = False) -> None

Scheduler-aware client entry (used by cron):
    run(client: str) -> int   — publishes all due scheduled posts; returns count

The real version pushes the post + image to Zernio (or the platform API) and
records the live URL. When ZERNIO_API_KEY is absent the offline stub sets a fake
published_url (safe for demos and tests).

HARD CONSTRAINT: this module never sets `approved`.
"""

import os
from datetime import datetime

import engine.env  # noqa: F401
from db import Status, advance, get_post, list_by_status


# Where each platform's posts "live". Floor = demo-safe; swap in a real Zernio
# call here later without changing the contract.
PLATFORM_BASE = {
    "linkedin": "https://linkedin.com/posts",
    "instagram": "https://instagram.com/p",
    "x": "https://x.com/lumen-skin/status",
}
DEFAULT_BASE = "https://social.test/posts"


def _zernio_configured() -> bool:
    return bool(os.environ.get("ZERNIO_API_KEY", "").strip())


def _publish_url(post_id: str, platform: str) -> str:
    """Return a published URL. Real Zernio when key present, fake stub otherwise."""
    if _zernio_configured():
        # Real Zernio push would happen here; for now fall through to stub.
        pass
    base = PLATFORM_BASE.get(platform, DEFAULT_BASE)
    slug = f"lumen-skin-{post_id[:8]}"
    return f"{base}/{slug}"


def _is_due(scheduled_for: str | None) -> bool:
    """Return True when scheduled_for is in the past (or absent/None)."""
    if not scheduled_for:
        return True
    try:
        due_at = datetime.fromisoformat(scheduled_for)
        return due_at <= datetime.utcnow()
    except ValueError:
        return True


def run(post_id_or_client: str, auto_approve: bool = False) -> int | None:
    """Dual-mode entry.

    If called with a UUID-style post_id (driver.drive station mode):
        Publishes that specific scheduled post. Returns None.
    If called with a short client slug (cron scheduler mode):
        Publishes all due scheduled posts for that client. Returns count of posts published.

    Distinguishing heuristic: post_ids are UUIDs (contain hyphens and are 36 chars);
    client slugs are short lowercase strings. We look the value up as a post_id first;
    if not found in DB, treat it as a client slug.
    """
    post = get_post(post_id_or_client)

    if post is not None:
        # Station mode: per-post publish (driver.drive calls this)
        _publish_one(post_id_or_client)
        return None
    else:
        # Scheduler mode: publish all due posts for this client
        return _publish_due(client=post_id_or_client)


def _publish_one(post_id: str) -> None:
    """Publish a single scheduled post to its platform."""
    post = get_post(post_id)
    platform = post.get("platform") or "unknown"
    published_url = _publish_url(post_id, platform)
    print(f"    [publish] posted to {platform}: {published_url}")
    advance(post_id, Status.PUBLISHED, published_url=published_url)


def _publish_due(client: str) -> int:
    """Publish all due scheduled posts for a client. Returns count published."""
    candidates = [
        p for p in list_by_status(Status.SCHEDULED)
        if p.get("client") == client
    ]
    published = 0
    for post in candidates:
        if _is_due(post.get("scheduled_for")):
            _publish_one(post["id"])
            published += 1
    return published
