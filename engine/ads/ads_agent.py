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


def approve_spend(post_id: str, approved_by: str) -> None:
    raise NotImplementedError  # implemented in Task 6
