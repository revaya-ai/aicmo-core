# Card 3 — Mission Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Carry an approved post through schedule → publish → analyze → ad recommendation → ad live, with two human gates on one Flask board, using demo-safe smart stubs.

**Architecture:** A shared `drive(post_id)` function runs the downstream mission stations in order until it reaches the next human stop. Both `run.py` (auto demo) and the Flask board's Approve handler call it. The ads agent scores winners with a real formula, writes a Claude-authored rationale (templated fallback), and only spends after a human approves on the board.

**Tech Stack:** Python 3 standard library, Flask (board), `anthropic` SDK (optional, for ad rationale), pytest (tests).

## Global Constraints

- `db.py` is the FROZEN contract — never edit it. Only use its public helpers: `Status`, `get_post`, `update_post`, `advance`, `list_by_status`, `create_post`, `init_db`.
- Every station keeps the exact signature `run(post_id: str, auto_approve: bool = False) -> None`.
- No live API keys required anywhere. Missing `ANTHROPIC_API_KEY` (or missing `anthropic` package) must degrade gracefully, never raise.
- Only touch `engine/mission/`, `engine/ads/`, `run.py`, and `tests/`.
- Stub stations must keep the contract's JSON metric shape: `likes, comments, shares, follows, impressions`.
- Tests use a temp DB by monkeypatching `db.DB_PATH`; never touch `data/aicmo.db`.
- Each station reads its input status and writes its output status via `advance(...)`.

---

### Task 1: Test harness with isolated temp DB

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Produces: a pytest fixture `fresh_db` that points `db.DB_PATH` at a temp file, calls `db.init_db()`, and yields. Used by every later test.

- [ ] **Step 1: Create the empty package marker**

Create `tests/__init__.py` with no content (empty file).

- [ ] **Step 2: Write the fixture**

Create `tests/conftest.py`:

```python
import os
import sys

import pytest

# Make repo root importable so `import db` works from tests/.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db


@pytest.fixture
def fresh_db(tmp_path):
    """Point the frozen db at a throwaway file for the duration of one test."""
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path / "test_aicmo.db")
    db.init_db()
    try:
        yield db
    finally:
        db.DB_PATH = original
```

- [ ] **Step 3: Sanity-check the fixture**

Create a temporary check inside `tests/conftest.py`? No — instead verify by writing a one-off test in Task 2. For now confirm pytest is installed:

Run: `python -m pytest --version`
Expected: prints a pytest version (e.g. `pytest 8.x`). If missing: `pip install pytest`.

- [ ] **Step 4: Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: temp-db fixture for Card 3 stations"
```

---

### Task 2: schedule.py — believable next slot

**Files:**
- Modify: `engine/mission/schedule.py`
- Test: `tests/test_schedule.py`

**Interfaces:**
- Consumes: `fresh_db` fixture; a post at status `approved`.
- Produces: post at status `scheduled` with `scheduled_for` set to a future ISO timestamp.

- [ ] **Step 1: Write the failing test**

Create `tests/test_schedule.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schedule.py -v`
Expected: FAIL (stub schedules "now + 1 hour" which passes the future check, so this may PASS already). If it PASSES, that is fine — the stub already satisfies the contract; proceed to strengthen it in Step 3 for the per-platform slot. Add this stricter assertion to the test first and re-run to see it FAIL:

```python
def test_linkedin_slot_is_weekday_morning(fresh_db):
    post_id = db.create_post("lumen-skin", "seed", platform="linkedin")
    db.advance(post_id, Status.APPROVED)
    schedule.run(post_id)
    slot = datetime.fromisoformat(db.get_post(post_id)["scheduled_for"])
    assert slot.hour == 9
    assert slot.weekday() < 5  # Mon-Fri
```

Run again: `python -m pytest tests/test_schedule.py::test_linkedin_slot_is_weekday_morning -v`
Expected: FAIL (stub returns now+1h, wrong hour).

- [ ] **Step 3: Implement the real slot picker**

Replace the body of `engine/mission/schedule.py` (keep the module docstring) with:

```python
from datetime import datetime, timedelta

from db import Status, get_post, advance

# Best-time-to-post heuristic per platform: (hour, weekday_only).
BEST_TIME = {
    "linkedin": (9, True),    # 9am on a weekday
    "instagram": (11, False), # 11am any day
    "x": (8, True),
}
DEFAULT_SLOT = (10, False)


def _next_slot(platform: str, now: datetime) -> datetime:
    hour, weekday_only = BEST_TIME.get(platform, DEFAULT_SLOT)
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    if weekday_only:
        while candidate.weekday() >= 5:  # Sat=5, Sun=6
            candidate += timedelta(days=1)
    return candidate


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)
    slot = _next_slot(post["platform"], datetime.utcnow())
    advance(post_id, Status.SCHEDULED, scheduled_for=slot.isoformat())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_schedule.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add engine/mission/schedule.py tests/test_schedule.py
git commit -m "feat(mission): per-platform scheduling slot"
```

---

### Task 3: publish.py — realistic published_url

**Files:**
- Modify: `engine/mission/publish.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: post at status `scheduled`.
- Produces: post at status `published` with a platform-shaped `published_url`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_publish.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_publish.py -v`
Expected: FAIL (stub URL is `https://example.test/...`).

- [ ] **Step 3: Implement believable publish**

Replace the body of `engine/mission/publish.py` (keep the docstring) with:

```python
from db import Status, get_post, advance

# Where each platform's posts "live". Floor = demo-safe; swap in a real Zernio
# call here later without changing the contract.
PLATFORM_BASE = {
    "linkedin": "https://linkedin.com/posts",
    "instagram": "https://instagram.com/p",
    "x": "https://x.com/lumen-skin/status",
}
DEFAULT_BASE = "https://social.test/posts"


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)
    platform = post["platform"]
    base = PLATFORM_BASE.get(platform, DEFAULT_BASE)
    slug = f"lumen-skin-{post_id[:8]}"
    published_url = f"{base}/{slug}"

    print(f"    [publish] posted to {platform}: {published_url}")
    advance(post_id, Status.PUBLISHED, published_url=published_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_publish.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/mission/publish.py tests/test_publish.py
git commit -m "feat(mission): platform-shaped publish url"
```

---

### Task 4: analytics.py — varied, deterministic metrics

**Files:**
- Modify: `engine/mission/analytics.py`
- Test: `tests/test_analytics.py`

**Interfaces:**
- Consumes: post at status `published`.
- Produces: post at status `analyzed` with `metrics_json` holding keys `likes, comments, shares, follows, impressions` (all ints).

- [ ] **Step 1: Write the failing test**

Create `tests/test_analytics.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_analytics.py -v`
Expected: FAIL on `test_metrics_vary_by_post` (stub returns identical hardcoded metrics).

- [ ] **Step 3: Implement deterministic-but-varied metrics**

Replace the body of `engine/mission/analytics.py` (keep the docstring) with:

```python
import hashlib
import json

from db import Status, get_post, advance


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_analytics.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add engine/mission/analytics.py tests/test_analytics.py
git commit -m "feat(mission): varied deterministic analytics"
```

---

### Task 5: ads_agent — winner score + recommendation (with Claude rationale + fallback)

**Files:**
- Modify: `engine/ads/ads_agent.py`
- Test: `tests/test_ads_recommend.py`

**Interfaces:**
- Consumes: post at status `analyzed` with `metrics_json`.
- Produces:
  - `winner_score(metrics: dict) -> float` (0–100).
  - `build_rationale(post: dict, metrics: dict, score: float, budget: float, audience: str) -> str` — tries Claude, falls back to a template; never raises.
  - `run(post_id, auto_approve=False)` advances winners to `ad_recommended` (sets `ad_target_post_id`, `ad_budget`, `ad_audience`, `ad_status="recommended"`, and stores the rationale in `ad_status`? No — store rationale in `human_note`). See Step 3 for the exact field mapping.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ads_recommend.py`:

```python
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


def test_typical_generated_posts_fire(fresh_db):
    # Calibration guard: with the real analytics generator (2-6% engagement),
    # the MAJORITY of realistic posts must clear WINNER_THRESHOLD, or the ad
    # path never fires in a live demo. Statistical (post ids are random uuids),
    # so assert majority rather than every single post.
    from engine.mission import analytics

    fired = 0
    total = 12
    for i in range(total):
        post_id = db.create_post("lumen-skin", f"seed-{i}")
        db.advance(post_id, Status.PUBLISHED)
        analytics.run(post_id)          # real generated metrics
        ads_agent.run(post_id)
        if db.get_post(post_id)["status"] == Status.AD_RECOMMENDED:
            fired += 1
    assert fired > total / 2, f"only {fired}/{total} typical posts fired"


def test_demo_force_winner_env(fresh_db, monkeypatch):
    # Even a genuine loser must fire when the demo override is set.
    monkeypatch.setenv("DEMO_FORCE_WINNER", "1")
    post_id = _analyzed_post(
        {"likes": 1, "comments": 0, "shares": 0, "follows": 0, "impressions": 9000}
    )
    ads_agent.run(post_id)
    assert db.get_post(post_id)["status"] == Status.AD_RECOMMENDED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ads_recommend.py -v`
Expected: FAIL (`winner_score` and `build_rationale` not defined; current run uses `follows > 10`).

- [ ] **Step 3: Implement scoring + recommendation**

Replace `engine/ads/ads_agent.py` entirely (keep a short docstring at top) with:

```python
"""STATION 4 — Ads (recommend-only): winning post -> paid ad proposal.

Reads:  status == analyzed   (uses metrics_json)
Writes: status == ad_recommended (winner) with budget/audience/rationale.
        Then, after a HUMAN spend gate (Task 6): ad_approved -> ad_live.

Never spends on its own. Claude writes the rationale when a key is present;
otherwise a templated rationale is used. The ad-platform push is a demo-safe
stub. signature: run(post_id, auto_approve=False) -> None
"""

import json
import os

from db import Status, get_post, advance, update_post

# Calibrated against the analytics generator (2-6% engagement -> scores ~16-57,
# median ~35). 30 fires ~60% of typical posts; the genuine-loser test scores
# ~0.4 and stays correctly below it. Do NOT raise this without re-checking the
# distribution, or the ad path stops firing in live demos.
WINNER_THRESHOLD = 30.0       # 0-100 winner_score cutoff
ADS_MODEL = "claude-sonnet-4-6"
DEFAULT_AUDIENCE = "Women 25-45, skincare-curious, US/CA"


def _force_winner(post: dict) -> bool:
    """Demo override: guarantee the ad path fires on stage regardless of metrics.

    Triggered by DEMO_FORCE_WINNER=1 or the magic word 'demowin' in the seed.
    """
    if os.environ.get("DEMO_FORCE_WINNER") == "1":
        return True
    return "demowin" in (post.get("seed_idea") or "").lower()


def winner_score(metrics: dict) -> float:
    """0-100 score from engagement rate and follows-per-impression."""
    impressions = max(1, metrics.get("impressions", 0))
    engagement = (
        metrics.get("likes", 0)
        + metrics.get("comments", 0)
        + metrics.get("shares", 0)
    )
    eng_rate = engagement / impressions           # ~0.00-0.15
    follow_rate = metrics.get("follows", 0) / impressions
    # Weight engagement 70%, follow-rate 30%; normalize to 0-100.
    raw = (eng_rate * 0.7 + follow_rate * 0.3) * 1000
    return round(min(100.0, raw), 1)


def _budget_for(score: float) -> float:
    """Bigger winners get a bigger proposed daily budget."""
    if score >= 80:
        return 150.0
    if score >= 70:
        return 100.0
    return 50.0


def _template_rationale(post, metrics, score, budget, audience) -> str:
    return (
        f"Winner score {score}/100 (engagement rate "
        f"{(metrics.get('likes',0)+metrics.get('comments',0)+metrics.get('shares',0))/max(1,metrics.get('impressions',1)):.1%}, "
        f"{metrics.get('follows',0)} new follows). "
        f"Recommend ${budget:.0f}/day targeting {audience}. "
        f"This post out-performed baseline, so paid amplification should extend reach efficiently."
    )


def build_rationale(post, metrics, score, budget, audience) -> str:
    """Claude-authored rationale; templated fallback. Never raises."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _template_rationale(post, metrics, score, budget, audience)
    try:
        import anthropic

        client = anthropic.Anthropic()
        prompt = (
            "You are an ads strategist for a skincare brand. In 2-3 sentences, "
            "explain why this post is worth promoting and who to target. Be concrete.\n\n"
            f"Hook: {post.get('hook')}\n"
            f"Metrics: {json.dumps(metrics)}\n"
            f"Winner score: {score}/100\n"
            f"Proposed budget: ${budget:.0f}/day; audience: {audience}\n"
        )
        msg = client.messages.create(
            model=ADS_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return text.strip() or _template_rationale(post, metrics, score, budget, audience)
    except Exception as exc:  # demo-safe: never let ads break the loop
        print(f"    [ads] Claude rationale unavailable ({exc}); using template.")
        return _template_rationale(post, metrics, score, budget, audience)


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)
    metrics = json.loads(post.get("metrics_json") or "{}")
    score = winner_score(metrics)
    forced = _force_winner(post)

    if not forced and score < WINNER_THRESHOLD:
        print(f"    [ads] score {score} < {WINNER_THRESHOLD}: not a winner.")
        return
    if forced:
        print(f"    [ads] DEMO override: forcing winner (score was {score}).")

    budget = _budget_for(score)
    audience = DEFAULT_AUDIENCE
    rationale = build_rationale(post, metrics, score, budget, audience)

    advance(
        post_id,
        Status.AD_RECOMMENDED,
        ad_target_post_id=post_id,
        ad_budget=budget,
        ad_audience=audience,
        ad_status="recommended",
        human_note=rationale,
    )
    print(f"    [ads] score {score}: recommended ${budget:.0f}/day -> {audience}")

    if not auto_approve:
        print("    [ads] awaiting human spend approval. Stopping at ad_recommended.")
        return

    approve_spend(post_id, approved_by="AUTO (demo loop)")
```

Note: `approve_spend` is implemented in Task 6. This task's tests do not call it (they use the default `auto_approve=False`), so the tests pass before Task 6 exists *only if the name resolves* — to avoid a NameError, add a minimal placeholder now at the bottom of the file and replace it in Task 6:

```python
def approve_spend(post_id: str, approved_by: str) -> None:
    raise NotImplementedError  # implemented in Task 6
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ads_recommend.py -v`
Expected: PASS (all five, including the calibration guard and the force-winner override). The winner tests use default `auto_approve=False`, so `approve_spend` is never called.

- [ ] **Step 5: Commit**

```bash
git add engine/ads/ads_agent.py tests/test_ads_recommend.py
git commit -m "feat(ads): real winner score + Claude rationale with fallback"
```

---

### Task 6: ads_agent — spend approval → ad_live pusher

**Files:**
- Modify: `engine/ads/ads_agent.py`
- Test: `tests/test_ads_spend.py`

**Interfaces:**
- Consumes: post at status `ad_recommended`.
- Produces: `approve_spend(post_id: str, approved_by: str) -> None` — advances to `ad_approved` (sets `ad_spend_approved_by`), runs the stub pusher, advances to `ad_live` (sets `ad_status="live:<campaign-id>"`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_ads_spend.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ads_spend.py -v`
Expected: FAIL (`approve_spend` raises `NotImplementedError`).

- [ ] **Step 3: Replace the placeholder with the real pusher**

In `engine/ads/ads_agent.py`, replace the placeholder:

```python
def approve_spend(post_id: str, approved_by: str) -> None:
    raise NotImplementedError  # implemented in Task 6
```

with:

```python
def _campaign_id(post_id: str) -> str:
    # Demo-safe stub id. Swap for a real Meta/LinkedIn campaign id later.
    return f"fake-campaign-{post_id[:8]}"


def approve_spend(post_id: str, approved_by: str) -> None:
    """Human (or auto demo) approved the spend: go live via the stub pusher."""
    advance(post_id, Status.AD_APPROVED, ad_spend_approved_by=approved_by)
    campaign = _campaign_id(post_id)
    # TODO(stretch): create the real campaign via Meta/LinkedIn Ads API here.
    update_post(post_id, ad_status=f"live:{campaign}")
    advance(post_id, Status.AD_LIVE)
    print(f"    [ads] STUB campaign live: {campaign} (approved by {approved_by})")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ads_spend.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add engine/ads/ads_agent.py tests/test_ads_spend.py
git commit -m "feat(ads): spend approval pusher to ad_live"
```

---

### Task 7: driver.py — the shared downstream conveyor

**Files:**
- Create: `engine/mission/driver.py`
- Test: `tests/test_driver.py`

**Interfaces:**
- Consumes: a post at status `approved`; the station modules from Tasks 2–6.
- Produces: `drive(post_id: str, auto_approve: bool = False) -> str` — runs schedule → publish → analytics → ads_agent in order and returns the post's final status. With `auto_approve=False` it halts at `ad_recommended` (or `analyzed` for non-winners); with `auto_approve=True` it runs through to `ad_live`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_driver.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_driver.py -v`
Expected: FAIL (`engine.mission.driver` does not exist).

- [ ] **Step 3: Implement the driver**

Create `engine/mission/driver.py`:

```python
"""The shared downstream conveyor for Card 3.

Given a post that a human just approved (status == approved), run the remaining
mission stations in order until the next human stop. Both run.py (auto demo) and
the Flask board's Approve handler call this, so there is one pipeline, two doors.
"""

from db import get_post
from engine.mission import schedule, publish, analytics
from engine.ads import ads_agent


def drive(post_id: str, auto_approve: bool = False) -> str:
    """Walk approved -> scheduled -> published -> analyzed -> ad_* ; return final status."""
    schedule.run(post_id, auto_approve=auto_approve)
    publish.run(post_id, auto_approve=auto_approve)
    analytics.run(post_id, auto_approve=auto_approve)
    ads_agent.run(post_id, auto_approve=auto_approve)
    return get_post(post_id)["status"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_driver.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add engine/mission/driver.py tests/test_driver.py
git commit -m "feat(mission): shared pipeline driver"
```

---

### Task 8: gate.py — wire Approve to the driver + add the spend gate

**Files:**
- Modify: `engine/mission/gate.py`
- Test: `tests/test_gate_routes.py`

**Interfaces:**
- Consumes: `create_app()` Flask factory; `driver.drive`; `ads_agent.approve_spend`.
- Produces: `/decide/<post_id>` Approve now calls `drive(...)`; new `/spend/<post_id>` route; index page lists both `qc_review` (Approvals) and `ad_recommended` (Spend approvals).

- [ ] **Step 1: Write the failing test**

Create `tests/test_gate_routes.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gate_routes.py -v`
Expected: FAIL (`test_approve_drives_pipeline` leaves status at `approved`; `/spend` route 404s).

- [ ] **Step 3a: Add a SPEND_CARD template constant**

In `engine/mission/gate.py`, after the existing `CARD = """..."""` definition, add:

```python
SPEND_CARD = """
<div class="card">
  <div class="meta">
    <span class="pillar">Ad recommended</span>
    <p class="hook">{hook}</p>
    <p class="body">{rationale}</p>
    <p class="qc">Budget: <b>${budget}</b> &middot; Audience: {audience}</p>
  </div>
  <form class="actions" method="post" action="/spend/{id}">
    <button class="approve" name="decision" value="ad_approved">Approve spend</button>
    <button class="reject"  name="decision" value="decline">Decline</button>
  </form>
</div>"""
```

- [ ] **Step 3b: Render the spend section on the index page**

In `create_app()`'s `index()` function, after the existing `cards = "".join(built)` / empty-state logic that builds the `qc_review` cards, build a second block and append it. Replace the `return PAGE.format(...)` line with:

```python
        spend_rows = db.list_by_status(Status.AD_RECOMMENDED)
        spend_built = []
        for p in spend_rows:
            spend_built.append(
                SPEND_CARD.format(
                    hook=_esc(p.get("hook") or ""),
                    rationale=_esc(p.get("human_note") or ""),
                    budget=_esc(p.get("ad_budget")),
                    audience=_esc(p.get("ad_audience") or ""),
                    id=_esc(p["id"]),
                )
            )
        if spend_built:
            cards = cards + (
                '<h2 style="font-family:Fraunces,Georgia,serif;font-size:18px;'
                'margin:28px 0 12px;">Spend approvals</h2>' + "".join(spend_built)
            )
        return PAGE.format(count=count, cards=cards)
```

- [ ] **Step 3c: Make Approve drive the pipeline**

In the `decide()` route, replace:

```python
        db.advance(post_id, decision, human_note=labels[decision])
        return redirect("/")
```

with:

```python
        db.advance(post_id, decision, human_note=labels[decision])
        if decision == Status.APPROVED:
            from engine.mission import driver
            driver.drive(post_id)  # walk it to the spend gate
        return redirect("/")
```

- [ ] **Step 3d: Add the /spend route**

In `create_app()`, after the `decide()` route and before `return app`, add:

```python
    @app.route("/spend/<post_id>", methods=["POST"])
    def spend(post_id):
        decision = request.form["decision"]
        if decision == "ad_approved":
            from engine.ads import ads_agent
            ads_agent.approve_spend(post_id, approved_by="human via gate")
        elif decision == "decline":
            db.update_post(post_id, ad_status="declined")
        else:
            return "bad decision", 400
        return redirect("/")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_gate_routes.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add engine/mission/gate.py tests/test_gate_routes.py
git commit -m "feat(mission): approve drives pipeline + spend gate on board"
```

---

### Task 9: run.py — use the shared driver

**Files:**
- Modify: `run.py`
- Test: `tests/test_full_loop.py`

**Interfaces:**
- Consumes: `driver.drive`; existing brain/studio/gate stubs.
- Produces: an end-to-end auto run that reaches `ad_live`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_full_loop.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_full_loop.py -v`
Expected: PASS or FAIL depending on stub behavior — the current `run.py` already reaches `ad_live` via the stub. Confirm it PASSES; if it does, the test now guards the refactor in Step 3. Proceed to Step 3 and re-run to ensure it still passes after the refactor.

- [ ] **Step 3: Refactor run.py to call the driver**

In `run.py`, replace the `PIPELINE` list and the `for label, station in PIPELINE:` loop with an explicit sequence that uses the driver for the downstream half. Replace the block from `PIPELINE = [` through the end of the `for` loop with:

```python
from engine.mission import driver

PRE_GATE = [
    ("brain.generate", brain_generate),
    ("studio.render", studio_render),
    ("studio.brand_qc", studio_brand_qc),
    ("mission.gate", mission_gate),
]


def _run_pre_gate(post_id):
    for label, station in PRE_GATE:
        before = get_post(post_id)["status"]
        station.run(post_id, auto_approve=True)
        after = get_post(post_id)["status"]
        arrow = "(no transition)" if before == after else f"-> {after}"
        print(f"{before:<14} {arrow:<20} ({label})")
```

Then in `main()`, replace the old `for` loop with:

```python
    _run_pre_gate(post_id)
    print("-- human gate auto-approved; driving downstream --")
    final = driver.drive(post_id, auto_approve=True)
    print(f"final status: {final}")
```

Keep the existing import lines for the stations and `get_post`. Remove the now-unused `mission_schedule`, `mission_publish`, `mission_analytics`, `ads_agent` imports only if they are no longer referenced (the driver imports them itself), or leave them — unused imports are harmless. Prefer removing them for cleanliness.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_full_loop.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_full_loop.py
git commit -m "refactor: run.py drives downstream via shared driver"
```

---

### Task 10: Full suite + manual smoke + README note

**Files:**
- Modify: `README.md` (add a "Card 3 — Mission Control" section)
- Test: all of `tests/`

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS.

- [ ] **Step 2: Manual smoke — auto loop**

Run: `python run.py "why your competitors all sound the same"`
Expected: prints status transitions ending at `final status: ad_live` (winner) or `analyzed` (non-winner — re-run if you want to demo the ad path, or rely on the forced-winner tests).

- [ ] **Step 3: Manual smoke — the board (manual, not automated)**

Run: `python engine/mission/gate.py`
Open `http://localhost:5050`. With a post sitting at `qc_review` (create one via the pipeline up to the gate), click **Approve** and confirm a Spend-approval card appears; click **Approve spend** and confirm it disappears (now `ad_live`). Stop the server with Ctrl-C.

- [ ] **Step 4: Add README section**

Append to `README.md`:

```markdown
## Card 3 — Mission Control

- `engine/mission/gate.py` — the human board (two gates): content Approve/Revise/Reject and ad spend Approve/Decline. Run: `python engine/mission/gate.py` → http://localhost:5050
- `engine/mission/driver.py` — `drive(post_id)` runs schedule → publish → analytics → ads after approval; shared by the board and `run.py`.
- `engine/mission/{schedule,publish,analytics}.py` — demo-safe smart stubs (no API keys).
- `engine/ads/ads_agent.py` — winner score + Claude rationale (templated fallback) + stub ad pusher behind the spend gate.

Tests: `python -m pytest tests/ -v`
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: Card 3 Mission Control README section"
```

---

## Self-Review notes

- **Spec coverage:** driver (§Architecture) → Task 7; two-gate board → Task 8; schedule/publish/analytics smart stubs → Tasks 2–4; ads winner score + Claude rationale + fallback + defensive Brain/Studio calls → Task 5; spend gate → Tasks 6 & 8; run.py shared path → Task 9; tests (full loop, not-a-winner, gate routes) → Tasks 5/7/8/9; README/integration → Task 10. All covered.
- **Defensive Brain/Studio ad calls:** the spec calls for trying Brain's ad-copy / Studio's ad-creative if present. Those functions are not yet defined on any branch; Task 5 uses the post's own hook/body/image and does not import them, which satisfies "must work whether or not they land." A follow-up can graft them in at integration without schema changes. (Noted as the one deliberate simplification.)
- **Field mapping:** rationale is stored in `human_note` (a real, writable column) so the spend card can display it without touching `db.py`. `ad_status` carries `recommended` → `live:<id>` → `declined`.
- **Type consistency:** `winner_score(metrics)->float`, `build_rationale(post,metrics,score,budget,audience)->str`, `approve_spend(post_id,approved_by)->None`, `drive(post_id,auto_approve=False)->str` used consistently across Tasks 5–9.
