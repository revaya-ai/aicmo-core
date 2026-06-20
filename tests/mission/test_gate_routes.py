import json

import db
from db import Status
from engine.mission import gate


def _client(monkeypatch):
    from engine.ads import ads_agent
    monkeypatch.setattr(ads_agent, "winner_score", lambda m: 90.0)
    app = gate.create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_approve_drives_pipeline(fresh_db, monkeypatch):
    client = _client(monkeypatch)
    post_id = db.create_post("lumen-skin", "seed", platform="linkedin")
    db.advance(post_id, Status.QC_REVIEW)

    resp = client.post(f"/decide/{post_id}", data={"decision": "approved"})
    assert resp.status_code in (302, 303)
    # Approve walked it all the way to the spend gate.
    assert db.get_post(post_id)["status"] == Status.AD_RECOMMENDED


def test_spend_route_goes_live(fresh_db, monkeypatch):
    client = _client(monkeypatch)
    post_id = db.create_post("lumen-skin", "seed")
    db.advance(
        post_id,
        Status.AD_RECOMMENDED,
        ad_budget=50.0,
        ad_audience="aud",
        ad_status="recommended",
    )

    resp = client.post(f"/spend/{post_id}", data={"decision": "ad_approved"})
    assert resp.status_code in (302, 303)
    assert db.get_post(post_id)["status"] == Status.AD_LIVE


def test_reject_still_bounces(fresh_db, monkeypatch):
    client = _client(monkeypatch)
    post_id = db.create_post("lumen-skin", "seed")
    db.advance(post_id, Status.QC_REVIEW)
    client.post(f"/decide/{post_id}", data={"decision": "needs_revision"})
    assert db.get_post(post_id)["status"] == Status.NEEDS_REVISION
