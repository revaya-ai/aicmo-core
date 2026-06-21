"""engine/mission/notion_metrics_push.py — Daily Notion metrics push.

Reads:  status in (published, analyzed)  — posts with metrics_json set
Writes: Notion Metrics DB via notion_sync.push_metrics(client)

Entry point:
    run(client: str) -> int   — returns count of posts whose metrics were aggregated

Cadence: daily 06:30 (com.aicmo.metrics-push.plist)

Constraint: writes ONLY to the Metrics DB; never touches post status; never sets approved.

Online mode (NOTION_TOKEN set): pushes aggregated KPIs to the client's Notion Metrics DB.
Offline mode (no token): writes the existing outputs/<client>-metrics.json stub path.

This is the Notion-write half of system-map Section 6. The GA4/GSC/DataForSEO
collectors and weekly Gemini briefs remain deferred.
"""

import engine.env  # noqa: F401 — must be first project import to load .env

import json
import os

import db
from db import Status
from engine.dashboard import notion_sync


_OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")


def _analyzed_posts(client: str) -> list[dict]:
    """Return all published + analyzed posts for the client that have metrics_json."""
    posts = []
    for status in (Status.PUBLISHED, Status.ANALYZED):
        for p in db.list_by_status(status):
            if p.get("client") == client and p.get("metrics_json"):
                posts.append(p)
    return posts


def _aggregate(posts: list[dict]) -> dict:
    """Aggregate per-post metrics into a simple KPI summary."""
    total_likes = 0
    total_impressions = 0
    total_comments = 0
    total_shares = 0
    count = 0

    for p in posts:
        try:
            m = json.loads(p["metrics_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        total_likes += m.get("likes", 0)
        total_impressions += m.get("impressions", 0)
        total_comments += m.get("comments", 0)
        total_shares += m.get("shares", 0)
        count += 1

    avg_engagement = (
        round((total_likes + total_comments + total_shares) / total_impressions, 4)
        if total_impressions > 0
        else 0.0
    )

    return {
        "posts_analyzed": count,
        "total_likes": total_likes,
        "total_impressions": total_impressions,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "avg_engagement_rate": avg_engagement,
    }


def run(client: str) -> int:
    """Aggregate metrics for the client and push to Notion Metrics DB.

    Returns the count of posts whose metrics were aggregated.
    """
    posts = _analyzed_posts(client)
    agg = _aggregate(posts)
    print(f"    [notion_metrics_push] client={client!r} posts={agg['posts_analyzed']} "
          f"likes={agg['total_likes']} impressions={agg['total_impressions']} "
          f"avg_er={agg['avg_engagement_rate']}")

    # Push to Notion (stub if NOTION_TOKEN absent)
    notion_sync.push_metrics(client)

    return agg["posts_analyzed"]
