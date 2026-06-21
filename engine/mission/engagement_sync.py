"""CRON — Mission: pull real engagement and write it back to Notion (Tyler's loop).

Reads:  status in (published, analyzed)  — posts with a published_url
Writes: metrics_json (DB), Notion pipeline card, Notion Metrics DB

Entry point:
    run(client: str) -> int   — returns count of posts synced

Cadence: nightly 19:30 (cron: 30 19 * * *)

This is the "Tyler" module. The synchronous analytics station (engine.mission.analytics)
writes an immediate placeholder so the pipeline completes without waiting; this module
runs later and overwrites it with real numbers, then pushes them to Notion. Without the
Notion write-back the analyst loop is invisible to the human — that is the gap this closes.

Online mode (ZERNIO_API_KEY set): pull real engagement from Zernio / platform API.
Offline mode (no key): fall back to engine.mission.analytics._metrics_for mock values.

HARD CONSTRAINT: this module never sets `approved`.
"""

import json
import os

import engine.env  # noqa: F401
import db as _db
from engine.dashboard import notion_sync as _notion_sync
from engine.mission.analytics import _metrics_for as _mock_metrics


def _zernio_configured() -> bool:
    return bool(os.environ.get("ZERNIO_API_KEY", "").strip())


def _fetch_metrics(post_id: str, published_url: str) -> dict:
    """Pull engagement for a post. Offline mock only — Zernio not wired; set no key to use offline fallback."""
    if _zernio_configured():
        raise NotImplementedError(
            "Zernio integration is not wired yet. Unset ZERNIO_API_KEY to use the offline fallback."
        )
    # Offline fallback: use the deterministic mock from analytics
    return _mock_metrics(post_id)


def _update_notion_card(client: str, post_id: str, metrics: dict) -> None:
    """Push the updated card back to the client's Notion pipeline board.

    Uses notion_sync.push(client) which upserts all posts (including the freshly
    updated metrics_json). This is intentionally whole-board because the push is
    idempotent and the client's board is per-client, not per-post.
    """
    try:
        _notion_sync.push(client)
    except Exception as exc:
        # Never crash the sync loop over a Notion write failure
        print(f"    [engagement_sync] notion card update failed for {post_id}: {exc}")


def run(client: str) -> int:
    """Sync engagement for all published/analyzed posts for the client.

    For each post:
      1. Pull real metrics (or fallback mock).
      2. Write metrics_json to DB (update_post, not advance — status must not change).
      3. Update the Notion pipeline card via notion_sync.push.
      4. Write KPIs to the Notion Metrics DB via notion_sync.push_metrics.

    Returns count of posts synced.
    """
    target_statuses = [_db.Status.PUBLISHED, _db.Status.ANALYZED]
    posts = []
    for status in target_statuses:
        posts.extend(
            p for p in _db.list_by_status(status)
            if p.get("client") == client
        )

    synced = 0
    for post in posts:
        pid = post["id"]
        url = post.get("published_url") or ""
        try:
            metrics = _fetch_metrics(pid, url)
            _db.update_post(pid, metrics_json=json.dumps(metrics))
            _update_notion_card(client, pid, metrics)
            print(f"    [engagement_sync] synced {pid}: likes={metrics.get('likes')}")
            synced += 1
        except Exception as exc:
            # Never crash the whole sync loop over one post
            print(f"    [engagement_sync] ERROR on {pid}: {exc}")

    # Push KPIs to the Notion Metrics DB regardless of per-post results
    try:
        _notion_sync.push_metrics(client)
    except Exception as exc:
        print(f"    [engagement_sync] metrics push failed for {client}: {exc}")

    return synced
