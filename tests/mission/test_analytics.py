import json

import db
from db import Status
from engine.mission import analytics


def test_metrics_shape_and_determinism(fresh_db):
    post_id = db.create_post("lumen-skin", "seed")
    db.advance(post_id, Status.PUBLISHED)

    analytics.run(post_id)

    post = db.get_post(post_id)
    assert post["status"] == Status.ANALYZED
    m = json.loads(post["metrics_json"])
    for key in ("likes", "comments", "shares", "follows", "impressions"):
        assert isinstance(m[key], int) and m[key] >= 0
    # Engagement should be a believable fraction of impressions.
    assert m["likes"] < m["impressions"]


def test_metrics_vary_by_post(fresh_db):
    a = db.create_post("lumen-skin", "seed-a")
    b = db.create_post("lumen-skin", "seed-b")
    db.advance(a, Status.PUBLISHED)
    db.advance(b, Status.PUBLISHED)
    analytics.run(a)
    analytics.run(b)
    assert db.get_post(a)["metrics_json"] != db.get_post(b)["metrics_json"]
