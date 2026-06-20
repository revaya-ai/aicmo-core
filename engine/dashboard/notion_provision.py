"""Provision the Content Pipeline database in Notion.

STUB (no NOTION_TOKEN): print the schema it would create and write a stub
database id to data/notion_state.json.
REAL (NOTION_TOKEN + NOTION_PARENT_PAGE_ID): create the database via the API and
store its id.

Idempotent: once data/notion_state.json carries a database_id, provision() reuses
it instead of creating another.
"""

import json
import os
import sys

# Run as `python3 engine/dashboard/notion_provision.py` from the repo root.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.dashboard import notion_client, notion_schema  # noqa: E402

STATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "notion_state.json"
)
DB_TITLE = "Content Pipeline"


def _load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(STATE_PATH)), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def provision() -> str:
    """Create the Content Pipeline database. Returns the database id (real or stub)."""
    state = _load_state()
    if state.get("database_id"):
        return state["database_id"]

    if notion_client.is_configured():
        parent = os.environ.get("NOTION_PARENT_PAGE_ID", "").strip()
        if not parent:
            raise RuntimeError(
                "NOTION_PARENT_PAGE_ID is required to provision the database. "
                "Share a Notion page with your integration and set its id."
            )
        resp = notion_client.create_database(parent, DB_TITLE, notion_schema.PROPERTIES)
        db_id = resp["id"]
        mode = "real"
    else:
        db_id = "stub-content-pipeline"
        mode = "stub"
        print(
            f"STUB provision (no NOTION_TOKEN). Would create database "
            f"'{DB_TITLE}' with properties:"
        )
        for name, definition in notion_schema.PROPERTIES.items():
            print(f"  - {name}: {list(definition.keys())[0]}")

    state["database_id"] = db_id
    state["mode"] = mode
    _save_state(state)
    return db_id


def main():
    print(f"Content Pipeline database id: {provision()}")


if __name__ == "__main__":
    main()
