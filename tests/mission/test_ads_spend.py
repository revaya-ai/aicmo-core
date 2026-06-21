import db
from db import Status
from engine.ads import ads_agent


def _recommended_post():
    post_id = db.create_post("lumen-skin", "seed")
    db.advance(
        post_id,
        Status.AD_RECOMMENDED,
        ad_budget=50.0,
        ad_audience="test audience",
        ad_status="recommended",
    )
    return post_id


def test_approve_spend_goes_live(fresh_db):
    post_id = _recommended_post()
    ads_agent.approve_spend(post_id, approved_by="laura@jidokaai.com")
    post = db.get_post(post_id)
    assert post["status"] == Status.AD_LIVE
    assert post["ad_spend_approved_by"] == "laura@jidokaai.com"
    assert post["ad_status"].startswith("live:")


def test_auto_approve_runs_full_chain(fresh_db):
    import json
    post_id = db.create_post("lumen-skin", "seed")
    db.advance(
        post_id,
        Status.ANALYZED,
        metrics_json=json.dumps(
            {"likes": 400, "comments": 60, "shares": 40, "follows": 60, "impressions": 5000}
        ),
    )
    ads_agent.run(post_id, auto_approve=True)
    assert db.get_post(post_id)["status"] == Status.AD_LIVE
