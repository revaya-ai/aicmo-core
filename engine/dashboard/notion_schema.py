"""The Notion contract: the Content Pipeline property schema + status maps.

Shared by notion_provision (creates the database) and notion_sync (push/pull).
Mirrors Jen's client-workspace "Content Pipeline" board, mapped to our db.py
posts record.
"""

# Notion database property definitions for the "Content Pipeline" database.
PROPERTIES = {
    "Title": {"title": {}},
    "Post ID": {"rich_text": {}},
    "Client": {"select": {}},
    "Status": {
        "select": {
            "options": [
                {"name": n}
                for n in [
                    "Draft",
                    "In Review",
                    "Approved",
                    "Rejected",
                    "Needs revision",
                    "Scheduled",
                    "Published",
                    "Analyzed",
                ]
            ]
        }
    },
    "Pillar": {"select": {}},
    "Hook": {"rich_text": {}},
    "Draft Caption": {"rich_text": {}},
    "Brand QC Score": {"number": {}},
    "Brand QC Notes": {"rich_text": {}},
    "Composite Image": {"rich_text": {}},
    "Aspect Ratio": {"select": {}},
    "Hashtags": {"rich_text": {}},
    "Folder Path": {"rich_text": {}},
    "Scheduled For": {"date": {}},
    "Published URL": {"url": {}},
}

# SQLite status -> Notion Status label (what the client sees on the board).
STATUS_SQLITE_TO_NOTION = {
    "drafted": "Draft",
    "qc_review": "In Review",
    "approved": "Approved",
    "rejected": "Rejected",
    "needs_revision": "Needs revision",
    "scheduled": "Scheduled",
    "published": "Published",
    "analyzed": "Analyzed",
    "ad_recommended": "Analyzed",
    "ad_approved": "Analyzed",
    "ad_live": "Published",
}

# The human gate: Notion label the client sets -> the SQLite status to advance to.
STATUS_NOTION_TO_SQLITE_GATE = {
    "Approved": "approved",
    "Rejected": "rejected",
    "Needs revision": "needs_revision",
}


def _rt(text):
    """Notion rich_text payload, truncated to a safe length."""
    return [{"type": "text", "text": {"content": (text or "")[:1900]}}]


def card_for(post: dict) -> dict:
    """Offline board card (stub mode). Plain JSON, human-readable."""
    return {
        "post_id": post["id"],
        "title": (post.get("hook") or post.get("seed_idea") or "Untitled")[:100],
        "status_label": STATUS_SQLITE_TO_NOTION.get(post["status"], post["status"]),
        "client": post.get("client"),
        "pillar": post.get("pillar"),
        "hook": post.get("hook"),
        "draft_caption": post.get("body"),
        "brand_qc_score": post.get("qc_score"),
        "composite_image": post.get("image_path"),
        "published_url": post.get("published_url"),
    }


def properties_for(post: dict) -> dict:
    """Notion page properties payload (real mode)."""
    title = (post.get("hook") or post.get("seed_idea") or "Untitled")[:100]
    props = {
        "Title": {"title": _rt(title)},
        "Post ID": {"rich_text": _rt(post["id"])},
        "Status": {
            "select": {"name": STATUS_SQLITE_TO_NOTION.get(post["status"], post["status"])}
        },
        "Hook": {"rich_text": _rt(post.get("hook"))},
        "Draft Caption": {"rich_text": _rt(post.get("body"))},
        "Brand QC Notes": {"rich_text": _rt(post.get("qc_notes"))},
    }
    if post.get("client"):
        props["Client"] = {"select": {"name": post["client"]}}
    if post.get("pillar"):
        props["Pillar"] = {"select": {"name": post["pillar"]}}
    if post.get("qc_score") is not None:
        props["Brand QC Score"] = {"number": post["qc_score"]}
    if post.get("image_path"):
        props["Composite Image"] = {"rich_text": _rt(post["image_path"])}
    if post.get("published_url"):
        props["Published URL"] = {"url": post["published_url"]}
    if post.get("scheduled_for"):
        props["Scheduled For"] = {"date": {"start": post["scheduled_for"]}}
    return props
