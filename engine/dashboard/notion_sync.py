"""Notion sync: push the pipeline to Notion, and pull the human's decisions back.

push()      upserts every pipeline post to the Content Pipeline database (real
            mode) or writes the JSON board outputs/notion-mirror.json (stub mode).
pull_gate() reads the human's Status decisions (Approved / Rejected / Needs
            revision) and advances the matching SQLite record. Only posts still
            at qc_review are acted on, so re-running is safe (idempotent).

STUB mode (no NOTION_TOKEN) is fully offline: the JSON board is the stand-in for
the Notion board, and flipping a card's status_label simulates the human tapping
Approve.
"""

import json
import os
import sys

# Run as `python3 engine/dashboard/notion_sync.py push|pull` from the repo root.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import db  # noqa: E402
from engine.dashboard import notion_client, notion_provision, notion_schema  # noqa: E402

BOARD_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "outputs", "notion-mirror.json"
)
STATE_PATH = notion_provision.STATE_PATH


def _load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(STATE_PATH)), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def _all_posts() -> list:
    posts = []
    for status in db.STATUSES:
        posts.extend(db.list_by_status(status))
    return posts


def push() -> str:
    """Upsert every pipeline post to Notion (real) or the JSON board (stub).

    Returns the database id (real) or the board path (stub).
    """
    database_id = notion_provision.provision()
    posts = _all_posts()

    if notion_client.is_configured():
        state = _load_state()
        page_map = state.get("page_map", {})
        for post in posts:
            props = notion_schema.properties_for(post)
            page_id = page_map.get(post["id"])
            if page_id:
                notion_client.update_page(page_id, props)
            else:
                resp = notion_client.create_page(database_id, props)
                page_map[post["id"]] = resp["id"]
        state["page_map"] = page_map
        _save_state(state)
        return database_id

    cards = [notion_schema.card_for(p) for p in posts]
    board = {"mode": "stub", "database_id": database_id, "cards": cards}
    os.makedirs(os.path.dirname(os.path.abspath(BOARD_PATH)), exist_ok=True)
    with open(BOARD_PATH, "w", encoding="utf-8") as fh:
        json.dump(board, fh, indent=2)
    return BOARD_PATH


def _advance_if_pending(post_id: str, new_status: str, applied: list) -> None:
    """Advance a post only if it is still awaiting the gate. Keeps pull idempotent."""
    post = db.get_post(post_id)
    if not post or post["status"] != db.Status.QC_REVIEW:
        return
    fields = {}
    if new_status == db.Status.REJECTED:
        fields["human_note"] = "Rejected in Notion"
    db.advance(post_id, new_status, **fields)
    applied.append((post_id, new_status))


def _plain_text(prop: dict) -> str:
    if not prop:
        return ""
    rts = prop.get("rich_text") or prop.get("title") or []
    return "".join(r.get("plain_text", "") for r in rts)


def _select_name(prop: dict) -> str:
    if not prop:
        return ""
    sel = prop.get("select")
    return sel.get("name") if sel else ""


def pull_gate() -> list:
    """Read human decisions and advance matching SQLite records.

    Returns a list of (post_id, new_status) that were applied.
    """
    applied = []

    if notion_client.is_configured():
        database_id = notion_provision.provision()
        for row in notion_client.query_database(database_id):
            props = row.get("properties", {})
            post_id = _plain_text(props.get("Post ID"))
            label = _select_name(props.get("Status"))
            new_status = notion_schema.STATUS_NOTION_TO_SQLITE_GATE.get(label)
            if post_id and new_status:
                _advance_if_pending(post_id, new_status, applied)
        return applied

    if not os.path.exists(BOARD_PATH):
        return applied
    with open(BOARD_PATH, encoding="utf-8") as fh:
        board = json.load(fh)
    for card in board.get("cards", []):
        label = card.get("status_label")
        new_status = notion_schema.STATUS_NOTION_TO_SQLITE_GATE.get(label)
        post_id = card.get("post_id")
        if post_id and new_status:
            _advance_if_pending(post_id, new_status, applied)
    return applied


def main():
    import argparse

    p = argparse.ArgumentParser(description="Notion sync: push board or pull decisions.")
    p.add_argument("action", choices=["push", "pull"])
    a = p.parse_args()
    if a.action == "push":
        print(f"Pushed pipeline to: {push()}")
    else:
        applied = pull_gate()
        print(f"Applied {len(applied)} human decision(s): {applied}")


if __name__ == "__main__":
    main()
