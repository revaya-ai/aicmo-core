import json

import db
from db import Status
from engine.ads import ads_agent


def _analyzed_post(metrics):
    post_id = db.create_post("lumen-skin", "seed")
    db.advance(post_id, Status.ANALYZED, metrics_json=json.dumps(metrics))
    return post_id


def test_winner_score_scales_with_engagement():
    low = ads_agent.winner_score(
        {"likes": 10, "comments": 1, "shares": 0, "follows": 1, "impressions": 5000}
    )
    high = ads_agent.winner_score(
        {"likes": 400, "comments": 60, "shares": 40, "follows": 60, "impressions": 5000}
    )
    assert high > low
    assert 0 <= low <= 100 and 0 <= high <= 100


def test_winner_is_recommended(fresh_db):
    post_id = _analyzed_post(
        {"likes": 400, "comments": 60, "shares": 40, "follows": 60, "impressions": 5000}
    )
    ads_agent.run(post_id)
    post = db.get_post(post_id)
    assert post["status"] == Status.AD_RECOMMENDED
    assert post["ad_budget"] and post["ad_budget"] > 0
    assert post["ad_audience"]
    assert post["ad_status"] == "recommended"
    assert post["human_note"]  # rationale stored for the spend gate


def test_loser_stays_analyzed(fresh_db):
    post_id = _analyzed_post(
        {"likes": 5, "comments": 0, "shares": 0, "follows": 0, "impressions": 9000}
    )
    ads_agent.run(post_id)
    assert db.get_post(post_id)["status"] == Status.ANALYZED


def test_typical_generated_post_clears_threshold(fresh_db):
    # Calibration guard: with the REAL analytics generator (2-6% engagement),
    # a typical post must clear WINNER_THRESHOLD, or the ad path never fires in
    # a live demo. Post ids are random uuids, so assert on the MEDIAN score over
    # a large sample (deterministic and non-flaky) rather than a pass/fail count
    # on a small sample (which has ~34% flake at n=12).
    import json
    import statistics
    from engine.mission import analytics

    scores = []
    for i in range(50):
        post_id = db.create_post("lumen-skin", f"seed-{i}")
        db.advance(post_id, Status.PUBLISHED)
        analytics.run(post_id)  # real generated metrics
        metrics = json.loads(db.get_post(post_id)["metrics_json"])
        scores.append(ads_agent.winner_score(metrics))

    median = statistics.median(scores)
    assert median >= ads_agent.WINNER_THRESHOLD, (
        f"median typical score {median} < threshold {ads_agent.WINNER_THRESHOLD}; "
        "the ad path would rarely fire live"
    )


def test_demo_force_winner_env(fresh_db, monkeypatch):
    # Even a genuine loser must fire when the demo override is set.
    monkeypatch.setenv("DEMO_FORCE_WINNER", "1")
    post_id = _analyzed_post(
        {"likes": 1, "comments": 0, "shares": 0, "follows": 0, "impressions": 9000}
    )
    ads_agent.run(post_id)
    assert db.get_post(post_id)["status"] == Status.AD_RECOMMENDED
