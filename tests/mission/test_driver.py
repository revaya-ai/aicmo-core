import db
from db import Status
from engine.mission import driver


def test_drive_winner_to_recommended(fresh_db, monkeypatch):
    # Force a winner regardless of generated metrics.
    from engine.ads import ads_agent
    monkeypatch.setattr(ads_agent, "winner_score", lambda m: 90.0)

    post_id = db.create_post("lumen-skin", "seed", platform="linkedin")
    db.advance(post_id, Status.APPROVED)

    final = driver.drive(post_id)
    assert final == Status.AD_RECOMMENDED
    assert db.get_post(post_id)["status"] == Status.AD_RECOMMENDED


def test_drive_auto_to_live(fresh_db, monkeypatch):
    from engine.ads import ads_agent
    monkeypatch.setattr(ads_agent, "winner_score", lambda m: 90.0)

    post_id = db.create_post("lumen-skin", "seed", platform="linkedin")
    db.advance(post_id, Status.APPROVED)

    final = driver.drive(post_id, auto_approve=True)
    assert final == Status.AD_LIVE


def test_drive_loser_stops_at_analyzed(fresh_db, monkeypatch):
    from engine.ads import ads_agent
    monkeypatch.setattr(ads_agent, "winner_score", lambda m: 1.0)

    post_id = db.create_post("lumen-skin", "seed", platform="linkedin")
    db.advance(post_id, Status.APPROVED)

    final = driver.drive(post_id)
    assert final == Status.ANALYZED
