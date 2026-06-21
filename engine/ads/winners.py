"""Winner engine — Jamie's method.

Rank every measured (analyzed) post by FOLLOWS gained — not views, not generic
engagement — take the top N, and recommend ONLY those for paid ads. Everything
else rests at 'analyzed'.

Jamie (AAA, 06-17 transcript):
  "I am certainly not using views as a metric. Filter highest to lowest based on
   metric follows. You will see two to three standout posts. That's where you
   start. You turn them into ads."

The logic: if someone saw the post, went to the profile, and hit FOLLOW, the
message aligned with the ICP. That post has proven itself organically, so it's
worth paying to amplify. You're not burning money on unproven content.
"""

import json

from db import Status, list_by_status, advance
from engine.ads import ads_agent

DEFAULT_TOP_N = 3


def _metrics(post: dict) -> dict:
    return json.loads(post.get("metrics_json") or "{}")


def follows(metrics: dict) -> int:
    return int(metrics.get("follows", 0))


def follow_rate(metrics: dict) -> float:
    """Follows per person reached — the quality read alongside raw follows."""
    reach = max(1, metrics.get("impressions", 0))
    return follows(metrics) / reach


def budget_for_follows(n: int) -> float:
    """Proposed daily ad budget scales with proven follows."""
    if n >= 50:
        return 150.0
    if n >= 25:
        return 100.0
    return 50.0


def rank_posts(posts: list) -> list:
    """Return posts sorted by FOLLOWS (desc), each tagged with rank + follows."""
    enriched = []
    for p in posts:
        m = _metrics(p)
        enriched.append(
            {**p, "_follows": follows(m), "_follow_rate": follow_rate(m)}
        )
    # Rank by raw follows (Jamie's metric); break ties on follow rate.
    enriched.sort(key=lambda x: (x["_follows"], x["_follow_rate"]), reverse=True)
    for i, p in enumerate(enriched, start=1):
        p["_rank"] = i
    return enriched


def leaderboard(top_n: int = DEFAULT_TOP_N) -> list:
    """Every analyzed post, ranked by follows; the top_n flagged as winners."""
    ranked = rank_posts(list_by_status(Status.ANALYZED))
    for p in ranked:
        p["_winner"] = p["_rank"] <= top_n and p["_follows"] > 0
    return ranked


def _rationale(p: dict, budget: float, audience: str) -> str:
    return (
        f"Ranked #{p['_rank']} by follows ({p['_follows']} new follows, "
        f"{p['_follow_rate']:.1%} follow rate). People who saw this hit FOLLOW, "
        f"so the message aligned with the ICP — it has earned paid amplification "
        f"(Jamie's method: promote what already proved itself organically). "
        f"Recommend ${budget:.0f}/day targeting {audience}."
    )


def review_and_recommend(top_n: int = DEFAULT_TOP_N, auto_approve: bool = False) -> dict:
    """Rank all analyzed posts; promote the top_n (with real follows) to ad_recommended.

    Returns {"ranked": [...], "winners": [...]} for display.
    """
    ranked = leaderboard(top_n)
    winners = [p for p in ranked if p["_winner"]]

    for p in winners:
        m = _metrics(p)
        budget = budget_for_follows(p["_follows"])
        audience = ads_agent.DEFAULT_AUDIENCE
        rationale = _rationale(p, budget, audience)
        advance(
            p["id"],
            Status.AD_RECOMMENDED,
            ad_target_post_id=p["id"],
            ad_budget=budget,
            ad_audience=audience,
            ad_status="recommended",
            human_note=rationale,
        )
        if auto_approve:
            ads_agent.approve_spend(p["id"], approved_by="AUTO (demo loop)")

    return {"ranked": ranked, "winners": winners}


def leaderboard_text(top_n: int = DEFAULT_TOP_N) -> str:
    """A human-readable leaderboard for the terminal / demo."""
    ranked = leaderboard(top_n)
    if not ranked:
        return "No measured posts yet — nothing to rank."
    lines = ["", "  ORGANIC LEADERBOARD — ranked by follows (Jamie's method)", "  " + "-" * 58]
    for p in ranked:
        flag = "WINNER -> AD" if p["_winner"] else "rest"
        hook = (p.get("hook") or p.get("seed_idea") or "")[:34]
        lines.append(
            f"  #{p['_rank']}  {p['_follows']:>4} follows  ({p['_follow_rate']:.1%})  "
            f"{hook:<34}  {flag}"
        )
    lines.append("")
    return "\n".join(lines)
