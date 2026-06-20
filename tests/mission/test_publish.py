import db
from db import Status
from engine.mission import publish


def test_publish_sets_platform_url(fresh_db):
    post_id = db.create_post("lumen-skin", "seed", platform="linkedin")
    db.advance(post_id, Status.SCHEDULED)

    publish.run(post_id)

    post = db.get_post(post_id)
    assert post["status"] == Status.PUBLISHED
    assert post["published_url"].startswith("https://linkedin.com/")
    assert "example.test" not in post["published_url"]
