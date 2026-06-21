"""The Notion contract: the Content Pipeline + Metrics schemas, status maps, and
payload builders. Shared by notion_provision (creates DBs) and notion_sync
(push/pull). Mirrors Jen's board, mapped to our db.py posts record. Every field
the other builders (Studio / Mission / Ads) write exists here as a defined seam.
"""


import json


def _select(options):
    return {"select": {"options": [{"name": o} for o in options]}}


STATUS_OPTIONS = ["Captured", "For Review", "Scheduled", "Published", "Rejected"]

# Content Pipeline database properties.
PIPELINE_PROPERTIES = {
    "Title": {"title": {}},
    "Post ID": {"rich_text": {}},
    "Client": {"select": {}},
    "Status": _select(STATUS_OPTIONS),
    "Pillar": {"select": {}},
    "Angle": {"rich_text": {}},
    "Hook": {"rich_text": {}},
    "Draft Caption": {"rich_text": {}},
    "Client Comment": {"rich_text": {}},                       # client writes; we read
    "Brand QC Score": {"number": {}},                          # Studio seam
    "Brand QC Verdict": _select(["pass", "borderline", "fail"]),  # Studio seam
    "Composite Image": {"files": {}},                          # Studio seam
    "Aspect Ratio": {"select": {}},                            # Studio seam
    "Resize Check": _select(["organic ok", "paid ok", "needs resize"]),  # Studio seam
    "Creative Type": _select(["UGC", "Product showcase", "Video", "TV spot", "Carousel"]),  # Ads seam
    "Platform": _select(["LinkedIn", "Instagram", "Meta ad", "X"]),  # Mission/Ads seam
    "CTR": {"number": {}},                                     # Ads seam
    "ROAS": {"number": {}},                                    # Ads seam
    "Follows": {"number": {}},                                 # stage 6 — the winner metric
    "Winner": {"checkbox": {}},                                # stage 7 — top 2-3
    "Ad Status": _select(["Recommended", "Approved", "Live", "Declined"]),  # stages 8-10
    "Ad Budget": {"number": {}},                               # stage 8
    "Ad Audience": {"rich_text": {}},                          # stage 8
    "Hashtags": {"rich_text": {}},
    "Folder Path": {"rich_text": {}},                          # seam
    "Scheduled For": {"date": {}},                             # Mission seam
    "Published URL": {"url": {}},                              # Mission seam
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
    "qc_review": "For Review",
    "needs_revision": "For Review",
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


def _follows(post):
    """Pull follows-per-post out of metrics_json (set by Mission's analytics)."""
    mj = post.get("metrics_json")
    if not mj:
        return None
    try:
        return json.loads(mj).get("follows")
    except Exception:
        return None


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

    # Paid loop (stages 6-10).
    follows = _follows(post)
    if follows is not None:
        props["Follows"] = {"number": follows}
    if post["status"] in AD_STATUS_FROM_PIPELINE:
        props["Winner"] = {"checkbox": True}
        props["Ad Status"] = {"select": {"name": AD_STATUS_FROM_PIPELINE[post["status"]]}}
    if post.get("ad_budget") is not None:
        props["Ad Budget"] = {"number": post["ad_budget"]}
    if post.get("ad_audience"):
        props["Ad Audience"] = {"rich_text": _rt(post["ad_audience"])}
    return props


def _platform_label(p):
    return {"linkedin": "LinkedIn", "instagram": "Instagram",
            "meta-ad": "Meta ad", "x": "X"}.get((p or "").lower(), p)


def metric_properties(kpi_label, value, trend, source, is_mock):
    return {
        "KPI": {"title": _rt(kpi_label)},
        "Value": {"rich_text": _rt(value)},
        "Trend": {"rich_text": _rt(trend or "")},
        "Source": {"select": {"name": source}},
        "Is Mock": {"checkbox": bool(is_mock)},
    }
