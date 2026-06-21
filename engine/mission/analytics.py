"""STATION 3 — Mission: pull analytics on a published post.

Reads:  status == published   (uses published_url)
Writes: status == analyzed    (sets metrics_json)

Signature: run(post_id: str, auto_approve: bool = False) -> None

The real version polls the platform API for engagement after some hours and
stores it as JSON. The stub writes mock likes / comments / follows so the Ads
station has something to decide on.
"""

import hashlib
import json

from db import Status, advance, get_post


def _seed_int(post_id: str, salt: str, mod: int) -> int:
    h = hashlib.sha256(f"{post_id}:{salt}".encode()).hexdigest()
    return int(h, 16) % mod


def _metrics_for(post_id: str) -> dict:
    # Impressions 2000-8000, with believable downstream ratios.
    impressions = 2000 + _seed_int(post_id, "imp", 6001)
    engage_rate = 2 + _seed_int(post_id, "eng", 5)  # 2-6% engagement
    likes = impressions * engage_rate // 100
    comments = max(1, likes // (5 + _seed_int(post_id, "cmt", 4)))
    shares = max(0, likes // (10 + _seed_int(post_id, "shr", 6)))
    follows = max(0, likes // (8 + _seed_int(post_id, "fol", 8)))
    return {
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "follows": follows,
        "impressions": impressions,
    }


def run(post_id: str, auto_approve: bool = False) -> None:
    metrics = _metrics_for(post_id)
    advance(post_id, Status.ANALYZED, metrics_json=json.dumps(metrics))
