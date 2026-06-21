"""Notion sync — writes each pipeline stage to the AI CMO Pipeline database.

Called by run_demo.py after every status transition so you can watch
the full creative journey unfold in real time in Notion.

Database: AI CMO Pipeline (in Align AI Solutions HQ)
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN") or os.environ.get("NOTION_API_KEY")
DATABASE_ID  = "38662f5a-813a-8165-b198-ec7b0590b606"

_client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(auth=NOTION_TOKEN)
    return _client


def _rt(text: str) -> list:
    """Build a rich_text block, truncating to Notion's 2000-char limit."""
    return [{"type": "text", "text": {"content": str(text)[:2000]}}]


def create_page(post: dict) -> str:
    """Create a new Notion page for a post. Returns the Notion page ID."""
    notion = _get_client()
    props = {
        "Hook":     {"title": _rt(post.get("hook") or post.get("seed_idea") or "")},
        "Status":   {"select": {"name": post.get("status", "captured")}},
        "Seed Idea":{"rich_text": _rt(post.get("seed_idea") or "")},
        "Client":   {"rich_text": _rt(post.get("client") or "")},
        "Post ID":  {"rich_text": _rt(post.get("id") or "")},
        "Run At":   {"date": {"start": datetime.now(timezone.utc).isoformat()}},
    }
    result = notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=props,
    )
    return result["id"]


def update_page(notion_page_id: str, post: dict) -> None:
    """Update the Notion page with the latest post fields after each transition."""
    notion  = _get_client()
    status  = post.get("status", "")
    pillar  = post.get("pillar") or ""
    props = {
        "Hook":     {"title": _rt(post.get("hook") or post.get("seed_idea") or "")},
        "Status":   {"select": {"name": status}},
        "Seed Idea":{"rich_text": _rt(post.get("seed_idea") or "")},
        "Angle":    {"rich_text": _rt(post.get("angle") or "")},
        "Body":     {"rich_text": _rt(post.get("body") or "")},
        "Client":   {"rich_text": _rt(post.get("client") or "")},
        "Post ID":  {"rich_text": _rt(post.get("id") or "")},
    }
    if pillar:
        props["Pillar"] = {"select": {"name": pillar}}
    if post.get("qc_score") is not None:
        props["QC Score"] = {"number": post["qc_score"]}
    if post.get("qc_notes"):
        props["QC Notes"] = {"rich_text": _rt(post["qc_notes"])}

    notion.pages.update(page_id=notion_page_id, properties=props)
