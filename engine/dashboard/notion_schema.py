"""The Notion contract: the Content Pipeline + Metrics schemas, status maps, and
payload builders. Shared by notion_provision (creates DBs) and notion_sync
(push/pull). Mirrors Jen's board, mapped to our db.py posts record. Every field
the other builders (Studio / Mission / Ads) write exists here as a defined seam.
"""


import json


def _select(options):
    return {"select": {"options": [{"name": o} for o in options]}}


STATUS_OPTIONS = ["Captured", "In Review", "Scheduled", "Published", "Rejected"]

# Content Pipeline database = ORGANIC. Stages + the post + engagement metrics.
# Engagement (follows/likes/comments/shares) is produced by Mission's analytics
# (engine/mission/analytics.py -> metrics_json) — we connect to it, not rebuild it.
PIPELINE_PROPERTIES = {
    "Title": {"title": {}},
    "Post ID": {"rich_text": {}},
    "Client": {"select": {}},
    "Status": _select(STATUS_OPTIONS),
    "Pillar": {"select": {}},
    "Angle": {"rich_text": {}},
    "Hook": {"rich_text": {}},
    "Draft Caption": {"rich_text": {}},
    "Client Comment": {"rich_text": {}},                          # client writes; we read
    "Brand QC Score": {"number": {}},                             # Studio
    "Brand QC Verdict": _select(["pass", "borderline", "fail"]),  # Studio
    "Composite Image": {"files": {}},                             # Studio
    "Aspect Ratio": {"select": {}},                               # Studio
    "Platform": _select(["LinkedIn", "Instagram", "X"]),          # organic platform
    # organic engagement — connected from Mission analytics (metrics_json)
    "Follows": {"number": {}},
    "Likes": {"number": {}},
    "Comments": {"number": {}},
    "Shares": {"number": {}},
    "Impressions": {"number": {}},
    "Winner": {"checkbox": {}},                                   # promoted to a paid ad
    "Hashtags": {"rich_text": {}},
    "Scheduled For": {"date": {}},                                # Mission
    "Published URL": {"url": {}},                                 # Mission
}

# Paid Ads database = PAID (the NEW component). Only the promoted winners.
# Different fields from organic: spend, audience, CTR, ROAS — no engagement.
PAID_PROPERTIES = {
    "Ad Name": {"title": {}},
    "Source Post": {"rich_text": {}},        # the content Post ID it was promoted from
    "Platform": _select(["Meta ad", "Instagram", "Facebook"]),
    "Creative Type": _select(["UGC", "Product showcase", "Video", "Carousel"]),
    "Budget": {"number": {}},
    "Audience": {"rich_text": {}},
    "CTR": {"number": {}},
    "ROAS": {"number": {}},
    "Spend": {"number": {}},
    "Ad Status": _select(["Recommended", "Approved", "Live", "Declined"]),
}

# Dashboard Metrics database properties.
METRICS_PROPERTIES = {
    "KPI": {"title": {}},
    "Value": {"rich_text": {}},
    "Trend": {"rich_text": {}},
    "Source": {"select": {}},
    "Is Mock": {"checkbox": {}},
}

# SQLite status -> Notion Status (the STAGE the board groups by).
STATUS_SQLITE_TO_NOTION = {
    "captured": "Captured",
    "drafted": "Captured",
    "qc_review": "In Review",
    "needs_revision": "In Review",
    "approved": "Scheduled",
    "rejected": "Rejected",
    "scheduled": "Scheduled",
    "published": "Published",
    "analyzed": "Published",
    "ad_recommended": "Published",
    "ad_approved": "Published",
    "ad_live": "Published",
}

# The human gate read-back (content): the client moves a "For Review" card on the
# board. Forward (Scheduled/Published) = approve; Rejected = back to the Brain.
APPROVE_LABELS = {"Scheduled", "Published"}
SEND_BACK_LABELS = {"Rejected"}

# The second human gate read-back (ad spend), set on the "Ad Status" field.
AD_APPROVE_LABEL = "Approved"     # ad_recommended -> ad_approved
AD_DECLINE_LABEL = "Declined"     # ad_recommended -> drop the ad (back to analyzed)

# Pipeline status -> Ad Status label (what the board shows for the paid loop).
AD_STATUS_FROM_PIPELINE = {
    "ad_recommended": "Recommended",
    "ad_approved": "Approved",
    "ad_live": "Live",
}


def _metric(post, key):
    """Pull one engagement metric out of metrics_json (set by Mission's analytics)."""
    mj = post.get("metrics_json")
    if not mj:
        return None
    try:
        return json.loads(mj).get(key)
    except Exception:
        return None


def _follows(post):
    return _metric(post, "follows")


_ENGAGEMENT = (("Follows", "follows"), ("Likes", "likes"), ("Comments", "comments"),
               ("Shares", "shares"), ("Impressions", "impressions"))


def _rt(text):
    return [{"type": "text", "text": {"content": (text or "")[:1900]}}]


def _is_url(s):
    return isinstance(s, str) and s.startswith(("http://", "https://"))


def card_for(post):
    """Offline board card (stub mode)."""
    return {
        "post_id": post["id"],
        "title": (post.get("hook") or post.get("seed_idea") or "Untitled")[:100],
        "status_label": STATUS_SQLITE_TO_NOTION.get(post["status"], post["status"]),
        "client": post.get("client"),
        "pillar": post.get("pillar"),
        "angle": post.get("angle"),
        "hook": post.get("hook"),
        "draft_caption": post.get("body"),
        "client_comment": post.get("human_note"),
        "brand_qc_score": post.get("qc_score"),
        "composite_image": post.get("image_path"),
        "platform": post.get("platform"),
        "published_url": post.get("published_url"),
        "follows": _follows(post),
        "winner": post["status"] in AD_STATUS_FROM_PIPELINE,
        "ad_status_label": AD_STATUS_FROM_PIPELINE.get(post["status"]),
        "ad_budget": post.get("ad_budget"),
        "ad_audience": post.get("ad_audience"),
    }


def properties_for(post):
    """Notion page properties payload (real mode)."""
    title = (post.get("hook") or post.get("seed_idea") or "Untitled")[:100]
    props = {
        "Title": {"title": _rt(title)},
        "Post ID": {"rich_text": _rt(post["id"])},
        "Status": {"select": {"name": STATUS_SQLITE_TO_NOTION.get(post["status"], post["status"])}},
        "Hook": {"rich_text": _rt(post.get("hook"))},
        "Draft Caption": {"rich_text": _rt(post.get("body"))},
        "Angle": {"rich_text": _rt(post.get("angle"))},
    }
    if post.get("client"):
        props["Client"] = {"select": {"name": post["client"]}}
    if post.get("pillar"):
        props["Pillar"] = {"select": {"name": post["pillar"]}}
    if post.get("human_note"):
        props["Client Comment"] = {"rich_text": _rt(post["human_note"])}
    if post.get("qc_score") is not None:
        props["Brand QC Score"] = {"number": post["qc_score"]}
    if post.get("platform"):
        props["Platform"] = {"select": {"name": _platform_label(post["platform"])}}
    if _is_url(post.get("image_path")):
        props["Composite Image"] = {
            "files": [{"type": "external", "name": "composite",
                       "external": {"url": post["image_path"]}}]
        }
    if _is_url(post.get("published_url")):
        props["Published URL"] = {"url": post["published_url"]}
    if post.get("scheduled_for"):
        props["Scheduled For"] = {"date": {"start": post["scheduled_for"]}}

    # Organic engagement — connected from Mission's analytics (metrics_json).
    for label, key in _ENGAGEMENT:
        v = _metric(post, key)
        if v is not None:
            props[label] = {"number": v}
    if post["status"] in AD_STATUS_FROM_PIPELINE:
        props["Winner"] = {"checkbox": True}  # this post was promoted to a paid ad
    return props


def paid_properties_for(post):
    """Paid Ads card payload — the promoted winner (the NEW component)."""
    title = (post.get("hook") or post.get("seed_idea") or "Untitled")[:100]
    props = {
        "Ad Name": {"title": _rt(title)},
        "Source Post": {"rich_text": _rt(post["id"])},
        "Ad Status": {"select": {"name": AD_STATUS_FROM_PIPELINE.get(post["status"], "Recommended")}},
    }
    if post.get("ad_budget") is not None:
        props["Budget"] = {"number": post["ad_budget"]}
    if post.get("ad_audience"):
        props["Audience"] = {"rich_text": _rt(post["ad_audience"])}
    for label, key in (("CTR", "ctr"), ("ROAS", "roas"), ("Spend", "spend")):
        v = _metric(post, key)
        if v is not None:
            props[label] = {"number": v}
    if post.get("platform"):
        props["Platform"] = {"select": {"name": _platform_label(post["platform"], paid=True)}}
    return props


def _platform_label(p, paid=False):
    if paid:
        return "Meta ad"  # promoted winners run on Meta (FB/IG) per Jamie's method
    return {"linkedin": "LinkedIn", "instagram": "Instagram", "x": "X"}.get((p or "").lower(), p)


def metric_properties(kpi_label, value, trend, source, is_mock):
    return {
        "KPI": {"title": _rt(kpi_label)},
        "Value": {"rich_text": _rt(value)},
        "Trend": {"rich_text": _rt(trend or "")},
        "Source": {"select": {"name": source}},
        "Is Mock": {"checkbox": bool(is_mock)},
    }
