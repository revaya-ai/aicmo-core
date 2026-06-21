"""Provision a client's Notion guest seat: a client page + their own Content
Pipeline database + their own Dashboard Metrics database. One per client, fully
isolated (Jen's 'clients never mix').

STUB (no NOTION_TOKEN): print the schemas and write stub ids to client-keyed
state. REAL (token + a shared parent page): create the page + both databases.

State (data/notion_state.json):
{
  "parent_page_id": "...",
  "clients": { "<slug>": {page_id, pipeline_db_id, metrics_db_id, page_map, kpis} }
}
"""

import json
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.dashboard import kpi_menu, notion_client, notion_schema  # noqa: E402

STATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "notion_state.json"
)


def _load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(STATE_PATH)), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def _title_of(page: dict) -> str:
    for v in page.get("properties", {}).values():
        if v.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in v.get("title", []))
    return ""


def parent_page_id(state: dict) -> str:
    """Resolve the HQ parent page: env, then cached state, then search (cache it)."""
    env = os.environ.get("NOTION_PARENT_PAGE_ID", "").strip()
    if env:
        return env
    if state.get("parent_page_id"):
        return state["parent_page_id"]
    pages = notion_client.search_pages()
    if not pages:
        raise RuntimeError(
            "No NOTION_PARENT_PAGE_ID set and no page shared with the integration. "
            "Share a page (e.g. 'AI CMO') with the integration first."
        )
    target = next((p for p in pages if _title_of(p).strip().lower() == "ai cmo"), pages[0])
    state["parent_page_id"] = target["id"]
    return target["id"]


def provision_client(slug: str, kpis=None, client_name=None) -> dict:
    """Create (or reuse) a client's page + pipeline DB + metrics DB. Returns the
    client's state record. Idempotent once provisioned."""
    state = _load_state()
    clients = state.setdefault("clients", {})
    rec = clients.get(slug)
    if rec and rec.get("pipeline_db_id"):
        # backfill the Paid Ads DB for clients provisioned before it existed
        if not rec.get("paid_db_id"):
            if notion_client.is_configured():
                paid = notion_client.create_database(
                    rec["page_id"], "Paid Ads", notion_schema.PAID_PROPERTIES)
                rec["paid_db_id"] = paid["id"]
            else:
                rec["paid_db_id"] = f"stub-paid-{slug}"
            clients[slug] = rec
            _save_state(state)
        return rec

    kpis = kpis or kpi_menu.DEFAULT_KPIS
    name = client_name or slug.replace("-", " ").title()

    if notion_client.is_configured():
        parent = parent_page_id(state)
        page = notion_client.create_child_page(parent, f"{name} — AI CMO")
        page_id = page["id"]
        pipeline = notion_client.create_database(
            page_id, "Content Pipeline", notion_schema.PIPELINE_PROPERTIES
        )
        metrics = notion_client.create_database(
            page_id, "Dashboard — Metrics", notion_schema.METRICS_PROPERTIES
        )
        paid = notion_client.create_database(
            page_id, "Paid Ads", notion_schema.PAID_PROPERTIES
        )
        rec = {
            "page_id": page_id,
            "pipeline_db_id": pipeline["id"],
            "metrics_db_id": metrics["id"],
            "paid_db_id": paid["id"],
            "page_map": {},
            "paid_map": {},
            "kpis": kpis,
            "mode": "real",
        }
    else:
        print(f"STUB provision for '{slug}' (no NOTION_TOKEN). Would create:")
        print(f"  page: '{name} — AI CMO'")
        print(f"  Content Pipeline DB (organic, {len(notion_schema.PIPELINE_PROPERTIES)} props)")
        print(f"  Paid Ads DB (the new component, {len(notion_schema.PAID_PROPERTIES)} props)")
        print(f"  Dashboard — Metrics DB, KPIs: {kpis}")
        rec = {
            "page_id": f"stub-page-{slug}",
            "pipeline_db_id": f"stub-pipe-{slug}",
            "metrics_db_id": f"stub-metrics-{slug}",
            "paid_db_id": f"stub-paid-{slug}",
            "page_map": {},
            "paid_map": {},
            "kpis": kpis,
            "mode": "stub",
        }

    clients[slug] = rec
    _save_state(state)
    return rec


def ensure_schema(slug: str) -> dict:
    """Bring a client's existing databases up to the current schema (adds any new
    fields, e.g. the paid-loop properties). Idempotent. Real mode only."""
    rec = provision_client(slug)
    if notion_client.is_configured():
        notion_client.update_database(rec["pipeline_db_id"], notion_schema.PIPELINE_PROPERTIES)
        notion_client.update_database(rec["metrics_db_id"], notion_schema.METRICS_PROPERTIES)
        if rec.get("paid_db_id"):
            notion_client.update_database(rec["paid_db_id"], notion_schema.PAID_PROPERTIES)
        print(f"schema synced for '{slug}'")
    return rec


def save_client(slug: str, rec: dict) -> None:
    state = _load_state()
    state.setdefault("clients", {})[slug] = rec
    _save_state(state)


def main():
    import argparse

    p = argparse.ArgumentParser(description="Provision a client's Notion guest seat.")
    p.add_argument("slug")
    p.add_argument("--kpis", nargs="*", default=None)
    p.add_argument("--name", default=None)
    a = p.parse_args()
    rec = provision_client(a.slug, kpis=a.kpis, client_name=a.name)
    print(f"client '{a.slug}': pipeline={rec['pipeline_db_id']} metrics={rec['metrics_db_id']}")


if __name__ == "__main__":
    main()
