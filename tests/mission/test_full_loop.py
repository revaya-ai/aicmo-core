import importlib

import db
from db import Status


def test_full_loop_reaches_ad_live(fresh_db, monkeypatch):
    # Force winner so the loop deterministically reaches ad_live.
    from engine.ads import ads_agent
    monkeypatch.setattr(ads_agent, "winner_score", lambda m: 90.0)

    import run
    importlib.reload(run)
    monkeypatch.setattr("sys.argv", ["run.py", "why competitors all sound the same"])
    run.main()

    rows = db.list_by_status(Status.AD_LIVE)
    assert len(rows) == 1
    post = rows[0]
    assert post["published_url"]
    assert post["metrics_json"]
    assert post["ad_status"].startswith("live:")
