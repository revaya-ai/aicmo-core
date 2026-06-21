import json

import db
from db import Status
from engine.ads import winners


def _analyzed(follows, impressions=4000):
    """Create a post sitting at 'analyzed' with the given follows."""
    pid = db.create_post("lumen-skin", f"seed-{follows}")
    metrics = {"likes": 100, "comments": 10, "shares": 5,
               "follows": follows, "impressions": impressions}
    db.advance(pid, Status.ANALYZED, metrics_json=json.dumps(metrics))
    return pid


def test_ranks_by_follows_desc(fresh_db):
    _analyzed(10)
    _analyzed(80)
    _analyzed(40)
    ranked = winners.leaderboard(top_n=3)
    order = [p["_follows"] for p in ranked]
    assert order == [80, 40, 10]          # highest follows first
    assert [p["_rank"] for p in ranked] == [1, 2, 3]


def test_top_n_are_winners(fresh_db):
    for f in (90, 70, 50, 30, 10):
        _analyzed(f)
    ranked = winners.leaderboard(top_n=3)
    winning = [p["_follows"] for p in ranked if p["_winner"]]
    assert winning == [90, 70, 50]        # exactly the top 3 by follows


def test_review_promotes_only_top_n(fresh_db):
    for f in (90, 70, 50, 30, 10):
        _analyzed(f)
    winners.review_and_recommend(top_n=3)
    recommended = db.list_by_status(Status.AD_RECOMMENDED)
    still_analyzed = db.list_by_status(Status.ANALYZED)
    assert len(recommended) == 3          # top 3 promoted to ads
    assert len(still_analyzed) == 2        # the rest rest
    # The recommended ones carry a budget + a Jamie-style rationale.
    for p in recommended:
        assert p["ad_budget"] and p["ad_budget"] > 0
        assert "follows" in (p["human_note"] or "")


def test_zero_follows_never_wins(fresh_db):
    _analyzed(0)
    _analyzed(0)
    ranked = winners.leaderboard(top_n=3)
    assert all(p["_winner"] is False for p in ranked)   # no follows = not a winner
