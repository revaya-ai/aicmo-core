"""engine/develop.py — /develop operator co-pilot with two human STOP gates.

Operator flow
-------------
Stage 0+1  start(post_id)
    Runs VoC + Intake + Topic + Angle (positioning bricks) via
    ``ai_cmo_generate.run_chain``.  Writes the angle artifact to the post,
    sets ``qc_notes="DEVELOP_STAGE:positioning"``, then STOPS.
    The post remains at ``captured`` status.  The cron sweep will skip it.

Stage 2a   confirm_positioning(post_id)
    Reads the Notion confirm signal for stage ``"positioning"``.
    If the signal is present: runs Hook + Story bricks, writes hook + body to
    the post, sets ``qc_notes="DEVELOP_STAGE:caption"``, then STOPS.
    If the signal is absent: no-op — post remains at DEVELOP_STAGE:positioning.

Stage 2b+3 confirm_caption(post_id)
    Reads the Notion confirm signal for stage ``"caption"``.
    If present: calls ``render.run``, ``brand_qc.run``, which advance the post
    to ``qc_review`` (via the normal brand_qc path).  Clears the
    ``DEVELOP_STAGE:`` marker from qc_notes so the sweep guard and normal
    pull_gate treat the post as a regular in-review card.
    If absent: no-op.

Confirm signal
--------------
In **stub mode** (no ``NOTION_TOKEN``): the signal is read from the stub board
JSON at ``outputs/<client>-board.json``.  The card for this post must have a
field ``develop_confirm`` whose value equals the current stage string (e.g.
``"positioning"`` or ``"caption"``).

In **real Notion mode**: the same field name is read from the Notion page
properties for this post's card.  (Real Notion implementation deferred — the
``_read_develop_confirm`` helper below returns ``None`` when Notion is
configured, as a safe no-op placeholder until the Notion schema is extended.)

None of these functions ever sets ``Status.APPROVED``.

Sweep guard
-----------
``engine.cycle.sweep`` filters out any captured post whose ``qc_notes``
contains ``DEVELOP_STAGE:``.  This module does NOT call sweep; it runs
alongside the cron sweep as a separate operator-initiated pipeline.
"""

import engine.env  # noqa: F401 — must be first project import to load .env

import json
import os

import db
from db import Status
from engine.brain import ai_cmo_generate
from engine.studio import render, brand_qc

# Path to stub outputs directory — module-level so tests can monkeypatch it
# (mirrors notion_sync.OUT_DIR pattern).
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")


# ---------------------------------------------------------------------------
# Confirm signal reader
# ---------------------------------------------------------------------------

def _board_path(client: str) -> str:
    return os.path.join(OUT_DIR, f"{client}-board.json")


def _read_develop_confirm(post_id: str) -> str | None:
    """Read the ``develop_confirm`` field from the stub board JSON for this post.

    Returns the confirm value (e.g. ``"positioning"`` or ``"caption"``) if
    present and non-null, or ``None`` if absent / not set.

    In real Notion mode (NOTION_TOKEN configured), this returns ``None`` as a
    safe no-op placeholder — real Notion integration is deferred.
    """
    notion_token = os.environ.get("NOTION_TOKEN")
    if notion_token:
        # Real Notion: deferred — no-op for now, returns None (confirm not detected)
        return None

    # Stub mode: read from board JSON
    post = db.get_post(post_id)
    if not post:
        return None
    client = post["client"]
    path = _board_path(client)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None

    for card in data.get("cards", []):
        if card.get("post_id") == post_id:
            val = card.get("develop_confirm")
            return val if val else None
    return None


# ---------------------------------------------------------------------------
# Helper: strip DEVELOP_STAGE: marker from qc_notes
# ---------------------------------------------------------------------------

def _clear_develop_stage(qc_notes: str | None) -> str:
    """Remove the DEVELOP_STAGE:<stage> token from qc_notes. Returns cleaned string."""
    if not qc_notes:
        return ""
    parts = [p for p in qc_notes.split() if not p.startswith("DEVELOP_STAGE:")]
    return " ".join(parts).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start(post_id: str) -> None:
    """Stage 0+1: run positioning bricks (VoC + Intake + Topic + Angle) and STOP.

    Writes ``angle`` to the post and sets ``qc_notes="DEVELOP_STAGE:positioning"``.
    The post remains at ``captured`` status.  The cron sweep will skip it.

    The offline fallback in ``ai_cmo_generate.run_chain`` is intact — this
    function works without ANTHROPIC_API_KEY.
    """
    # Run the full chain to get all six artifacts (offline-safe)
    artifacts = ai_cmo_generate.run_chain(post_id)

    # Stage 1 artifact: angle (positioning stop)
    angle = artifacts.get("angle", "")

    # Write positioning artifact and mark the develop stage; status stays CAPTURED
    db.update_post(post_id, angle=angle, qc_notes="DEVELOP_STAGE:positioning")


def confirm_positioning(post_id: str) -> None:
    """Stage 2a: if the Notion confirm signal is present, produce hook + caption and STOP.

    Confirm signal: ``develop_confirm == "positioning"`` on the board card.
    If the signal is absent, this is a no-op — the post stays at DEVELOP_STAGE:positioning.

    On confirm: runs Hook + Story via ``ai_cmo_generate.run_chain`` (all six
    bricks run; we use the hook + story artifacts).  Writes ``hook`` + ``body``
    to the post and advances the stage to ``DEVELOP_STAGE:caption``.  Status
    remains ``captured``.
    """
    confirm = _read_develop_confirm(post_id)
    if confirm != "positioning":
        # No confirm signal or wrong stage — no-op
        return

    # Run full chain again to get hook + story artifacts (offline-safe, fast)
    artifacts = ai_cmo_generate.run_chain(post_id)

    hook = artifacts.get("hook", "")
    body = artifacts.get("story", "")

    db.update_post(post_id, hook=hook, body=body, qc_notes="DEVELOP_STAGE:caption")


def confirm_caption(post_id: str) -> None:
    """Stage 2b+3: if the Notion confirm signal is present, render + QC + land at qc_review.

    Confirm signal: ``develop_confirm == "caption"`` on the board card.
    If the signal is absent, this is a no-op — the post stays at DEVELOP_STAGE:caption.

    On confirm:
      1. ``render.run(post_id)`` — sets image_path
      2. ``brand_qc.run(post_id)`` — advances post to ``qc_review`` (or
         ``needs_revision`` on QC fail; the DEVELOP_STAGE marker is still
         cleared so the sweep can pick it up on the next pass if needed)
      3. Clears the ``DEVELOP_STAGE:`` token from qc_notes so the post is
         treated as a normal in-review card by pull_gate and the sweep guard.

    NEVER sets ``Status.APPROVED``.
    """
    confirm = _read_develop_confirm(post_id)
    if confirm != "caption":
        # No confirm signal or wrong stage — no-op
        return

    # Stage 2b: render image
    render.run(post_id)

    # Stage 3: brand QC — advances post to qc_review (or needs_revision)
    brand_qc.run(post_id)

    # Clear the DEVELOP_STAGE marker so the post re-enters the normal pipeline
    post = db.get_post(post_id)
    if post:
        cleaned = _clear_develop_stage(post.get("qc_notes"))
        db.update_post(post_id, qc_notes=cleaned)
