from datetime import datetime

import db
from db import Status
from engine.mission import schedule


def test_schedule_sets_future_slot(fresh_db):
    post_id = db.create_post("lumen-skin", "seed", platform="linkedin")
    db.advance(post_id, Status.APPROVED)

    schedule.run(post_id)

    post = db.get_post(post_id)
    assert post["status"] == Status.SCHEDULED
    slot = datetime.fromisoformat(post["scheduled_for"])
    assert slot > datetime.utcnow()


def test_linkedin_slot_is_weekday_morning(fresh_db):
    post_id = db.create_post("lumen-skin", "seed", platform="linkedin")
    db.advance(post_id, Status.APPROVED)
    schedule.run(post_id)
    slot = datetime.fromisoformat(db.get_post(post_id)["scheduled_for"])
    assert slot.hour == 9
    assert slot.weekday() < 5  # Mon-Fri
