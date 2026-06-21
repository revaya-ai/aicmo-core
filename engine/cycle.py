# engine/cycle.py
"""Captured-sweep + idempotent cron_cycle orchestrator.

sweep(client) -> int
    Walk every 'captured' row for the given client through:
        ai_cmo_generate (draft) -> seo_guardrails (score) -> render -> brand_qc
    Lands each post at 'qc_review' (or 'needs_revision' on QC fail).
    NEVER writes Status.APPROVED.

cron_cycle(client) -> dict
    Full idempotent cycle:
        pull_intake -> sweep -> push -> pull_gate -> drive APPROVED rows -> push -> push_metrics
    Human approval happens ONLY in Notion (via pull_gate). This function never sets approved.
    Returns {"swept": int, "driven": int}.
"""

import engine.env  # noqa: F401 — must be first project import to load .env

import db
from db import Status
from engine.brain import ai_cmo_generate
from engine.studio import render, brand_qc
from engine.guardrails import seo_guardrails, compliance
from engine.dashboard import notion_sync
from engine.mission import driver


def _client_rows(client: str, status: str) -> list:
    return [p for p in db.list_by_status(status) if p.get("client") == client]


def sweep(client: str) -> int:
    """Walk every captured row to qc_review. Never sets approved."""
    rows = _client_rows(client, Status.CAPTURED)
    for post in rows:
        pid = post["id"]

        # Station 1 — Brain: captured -> drafted
        ai_cmo_generate.run(pid)

        # Guardrails: score SEO on the drafted body; store failures in qc_notes
        body = (db.get_post(pid) or {}).get("body", "") or ""
        g = seo_guardrails.score(body)
        if not g["passed"]:
            db.update_post(pid, qc_notes="seo_fail:" + ",".join(g.get("failures", [])))

        # Compliance gate: flag drug claims for human review (never blocks or redrafts)
        c = compliance.check(client, body)
        if not c["passed"]:
            prior = (db.get_post(pid) or {}).get("qc_notes") or ""
            flag = "COMPLIANCE_FAIL:" + ";".join(c["violations"])
            db.update_post(pid, qc_notes=(prior + " " + flag).strip())

        # Station 2 — Studio: render image (drafted -> image_path set, status unchanged)
        render.run(pid)

        # Station 2 — Studio: brand QC (-> qc_review or needs_revision)
        brand_qc.run(pid)

    return len(rows)


def cron_cycle(client: str) -> dict:
    """Idempotent full cycle. Human approval happens ONLY in Notion."""
    # Pull client-submitted ideas into captured rows
    notion_sync.pull_intake(client)

    # Draft, score, render, and QC every captured row
    swept = sweep(client)

    # Surface qc_review posts to the human board
    notion_sync.push(client)

    # Read human Approve/Reject decisions from the board (only pull_gate sets approved)
    notion_sync.pull_gate(client)

    # Drive posts the HUMAN has already approved (status == approved set by pull_gate)
    driven = 0
    for post in _client_rows(client, Status.APPROVED):
        driver.drive(post["id"], auto_approve=False)
        driven += 1

    # Sync final statuses and metrics back to Notion
    notion_sync.push(client)
    notion_sync.push_metrics(client)

    return {"swept": swept, "driven": driven}
