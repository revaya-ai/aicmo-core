"""Per-client Notion sync. Each client has their own page + databases.

push(client)        upsert that client's pipeline posts to their board.
pull_gate(client)   read the client's Status + Comment decisions:
                      Approved      -> advance to approved
                      Rejected /    -> send back to the Brain with the comment
                      Needs revision
pull_intake(client) read client-created "Idea" rows -> new captured posts.
push_metrics(client) write the client's chosen KPIs to their Metrics DB (mock-marked).

STUB mode (no NOTION_TOKEN) uses outputs/<client>-board.json as the stand-in
board; flipping a card's status_label + client_comment simulates the client.
"""

import json
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import db  # noqa: E402
from engine import feedback  # noqa: E402
from engine.dashboard import (  # noqa: E402
    kpi_menu,
    notion_client,
    notion_provision,
    notion_schema,
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")


def _board_path(client):
    return os.path.join(OUT_DIR, f"{client}-board.json")


def _client_posts(client):
    posts = []
    for status in db.STATUSES:
        posts.extend(p for p in db.list_by_status(status) if p.get("client") == client)
    return posts


# ---------- push ----------

def push(client: str) -> str:
    rec = notion_provision.provision_client(client)
    posts = _client_posts(client)

    if notion_client.is_configured():
        page_map = rec.get("page_map", {})
        paid_map = rec.get("paid_map", {})
        for post in posts:
            # organic content card
            props = notion_schema.properties_for(post)
            page_id = page_map.get(post["id"])
            if page_id:
                notion_client.update_page(page_id, props)
            else:
                resp = notion_client.create_page(rec["pipeline_db_id"], props)
                page_map[post["id"]] = resp["id"]
            # a promoted winner also gets a Paid Ads card (the new component)
            if post["status"] in notion_schema.AD_STATUS_FROM_PIPELINE:
                pprops = notion_schema.paid_properties_for(post)
                ad_id = paid_map.get(post["id"])
                if ad_id:
                    notion_client.update_page(ad_id, pprops)
                else:
                    paid_map[post["id"]] = notion_client.create_page(rec["paid_db_id"], pprops)["id"]
        rec["page_map"] = page_map
        rec["paid_map"] = paid_map
        notion_provision.save_client(client, rec)
        return rec["pipeline_db_id"]

    cards = [notion_schema.card_for(p) for p in posts]
    board = {"mode": "stub", "client": client, "database_id": rec["pipeline_db_id"], "cards": cards}
    os.makedirs(os.path.abspath(OUT_DIR), exist_ok=True)
    with open(_board_path(client), "w", encoding="utf-8") as fh:
        json.dump(board, fh, indent=2)
    return _board_path(client)


# ---------- pull gate (the human decision) ----------

def _apply_decision(post_id, label, comment, applied):
    """Apply one human decision. Only acts on posts still at qc_review (idempotent)."""
    post = db.get_post(post_id)
    if not post or post["status"] != db.Status.QC_REVIEW:
        return
    if label in notion_schema.APPROVE_LABELS:
        db.advance(post_id, db.Status.APPROVED)
        applied.append((post_id, "approved"))
    elif label in notion_schema.SEND_BACK_LABELS:
        # Reject / needs-revision: store the comment AND re-draft back to qc_review,
        # so the revised post lands in front of the human again (not stalled).
        feedback.reject_and_redraft(post_id, comment)
        applied.append((post_id, "rejected_and_redrafted"))


def _apply_ad_decision(post_id, ad_label, applied):
    """The second gate (ad spend). Only acts on posts at ad_recommended."""
    if not post_id or not ad_label:
        return
    post = db.get_post(post_id)
    if not post or post["status"] != db.Status.AD_RECOMMENDED:
        return
    if ad_label == notion_schema.AD_APPROVE_LABEL:
        db.advance(post_id, db.Status.AD_APPROVED, ad_spend_approved_by="client (Notion)")
        applied.append((post_id, "ad_spend_approved"))
    elif ad_label == notion_schema.AD_DECLINE_LABEL:
        db.advance(post_id, db.Status.ANALYZED)  # drop the ad, leave the post analyzed
        applied.append((post_id, "ad_declined"))


def pull_gate(client: str) -> list:
    applied = []
    rec = notion_provision.provision_client(client)

    if notion_client.is_configured():
        # content gate — read from the Content Pipeline (organic)
        for row in notion_client.query_database(rec["pipeline_db_id"]):
            pr = row.get("properties", {})
            post_id = _plain(pr.get("Post ID"))
            if post_id:
                _apply_decision(post_id, _select(pr.get("Status")),
                                _plain(pr.get("Client Comment")), applied)
        # ad-spend gate — read from the Paid Ads DB (the new component)
        if rec.get("paid_db_id"):
            for row in notion_client.query_database(rec["paid_db_id"]):
                pr = row.get("properties", {})
                _apply_ad_decision(_plain(pr.get("Source Post")),
                                   _select(pr.get("Ad Status")), applied)
        if applied:
            push(client)  # reflect new states (rejected -> re-drafted In Review)
        return applied

    path = _board_path(client)
    if not os.path.exists(path):
        return applied
    with open(path, encoding="utf-8") as fh:
        board = json.load(fh)
    for card in board.get("cards", []):
        _apply_decision(card.get("post_id"), card.get("status_label"),
                        card.get("client_comment"), applied)
        _apply_ad_decision(card.get("post_id"), card.get("ad_status_label"), applied)
    if applied:
        push(client)  # reflect new states (rejected -> re-drafted In Review)
    return applied


# ---------- pull intake (client-submitted ideas) ----------

def pull_intake(client: str) -> list:
    """Read 'Idea' rows the client created (no Post ID yet) -> new captured posts."""
    created = []
    rec = notion_provision.provision_client(client)
    if not notion_client.is_configured():
        return created  # intake from Notion needs the real API
    for row in notion_client.query_database(rec["pipeline_db_id"]):
        pr = row.get("properties", {})
        if _select(pr.get("Status")) != "Idea":
            continue
        if _plain(pr.get("Post ID")):
            continue  # already imported
        seed = _plain(pr.get("Title")) or _plain(pr.get("Draft Caption"))
        if not seed:
            continue
        pid = db.create_post(client=client, seed_idea=seed)
        notion_client.update_page(row["id"], {"Post ID": {"rich_text": notion_schema._rt(pid)}})
        rec.setdefault("page_map", {})[pid] = row["id"]
        created.append((pid, seed))
    notion_provision.save_client(client, rec)
    return created


# ---------- push metrics (the dashboard) ----------

def push_metrics(client: str) -> int:
    """Write the client's chosen KPIs to their Metrics DB. Mock values are marked."""
    rec = notion_provision.provision_client(client)
    rows = kpi_menu.resolve(rec.get("kpis"))
    n = 0
    if notion_client.is_configured():
        existing = {_plain(r["properties"].get("KPI")): r["id"]
                    for r in notion_client.query_database(rec["metrics_db_id"])}
        for key, label, source in rows:
            props = notion_schema.metric_properties(
                label, kpi_menu.MOCK_VALUES.get(key, "n/a"), "", source, is_mock=True
            )
            if label in existing:
                notion_client.update_page(existing[label], props)
            else:
                notion_client.create_page(rec["metrics_db_id"], props)
            n += 1
        return n
    # stub
    out = [{"kpi": label, "value": kpi_menu.MOCK_VALUES.get(key, "n/a"),
            "source": source, "is_mock": True} for key, label, source in rows]
    os.makedirs(os.path.abspath(OUT_DIR), exist_ok=True)
    with open(os.path.join(OUT_DIR, f"{client}-metrics.json"), "w", encoding="utf-8") as fh:
        json.dump({"mode": "stub", "client": client, "metrics": out}, fh, indent=2)
    return len(out)


# ---------- helpers ----------

def _plain(prop):
    if not prop:
        return ""
    rts = prop.get("rich_text") or prop.get("title") or []
    return "".join(r.get("plain_text", "") for r in rts)


def _select(prop):
    if not prop:
        return ""
    sel = prop.get("select")
    return sel.get("name") if sel else ""


def main():
    import argparse

    p = argparse.ArgumentParser(description="Per-client Notion sync.")
    p.add_argument("action", choices=["push", "pull", "intake", "metrics"])
    p.add_argument("client")
    a = p.parse_args()
    if a.action == "push":
        print("pushed ->", push(a.client))
    elif a.action == "pull":
        print("decisions applied:", pull_gate(a.client))
    elif a.action == "intake":
        print("ideas imported:", pull_intake(a.client))
    else:
        print("metrics written:", push_metrics(a.client))


if __name__ == "__main__":
    main()
