"""Thin Notion API wrapper. All Notion HTTP lives here, nowhere else.

is_configured() is true only when NOTION_TOKEN is set. When it is not, the
sync/provision stub paths never call into this module, so the whole pipeline
runs offline with no network access.

Uses urllib from the stdlib, so there is no third-party dependency to install.
"""

import json
import os
import urllib.error
import urllib.request

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def token() -> str:
    return os.environ.get("NOTION_TOKEN", "").strip()


def is_configured() -> bool:
    return bool(token())


def _request(method: str, path: str, payload: dict = None) -> dict:
    url = f"{API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token()}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        # Surface the failure loudly. The caller leaves SQLite untouched, so a
        # retry is always safe. No silent success.
        raise RuntimeError(f"Notion {method} {path} failed: {e.code} {body}") from e


def create_database(parent_page_id: str, title: str, properties: dict) -> dict:
    return _request(
        "POST",
        "/databases",
        {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        },
    )


def create_page(database_id: str, properties: dict) -> dict:
    return _request(
        "POST",
        "/pages",
        {"parent": {"database_id": database_id}, "properties": properties},
    )


def create_child_page(parent_page_id: str, title: str) -> dict:
    """Create a regular page nested under another page (the client's guest seat)."""
    return _request(
        "POST",
        "/pages",
        {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {"title": [{"type": "text", "text": {"content": title}}]},
        },
    )


def create_database_in_page(parent_page_id: str, title: str, properties: dict) -> dict:
    """Create a database inside a page (alias of create_database for clarity)."""
    return create_database(parent_page_id, title, properties)


def append_blocks(page_id: str, blocks: list) -> dict:
    """Append content blocks (headings, callouts, paragraphs) to a page."""
    return _request("PATCH", f"/blocks/{page_id}/children", {"children": blocks})


def search_pages() -> list:
    """Return pages the integration can access."""
    resp = _request("POST", "/search", {"filter": {"property": "object", "value": "page"}})
    return resp.get("results", [])


def update_page(page_id: str, properties: dict) -> dict:
    return _request("PATCH", f"/pages/{page_id}", {"properties": properties})


def query_database(database_id: str) -> list:
    results = []
    payload = {}
    while True:
        resp = _request("POST", f"/databases/{database_id}/query", payload)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        payload = {"start_cursor": resp["next_cursor"]}
    return results
