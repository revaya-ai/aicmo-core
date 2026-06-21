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
    If the signal is present: reads the LOCKED angle from the DB, builds
    hook + body FROM that stored angle (never re-runs the full chain).
    Writes hook + body to the post, sets ``qc_notes="DEVELOP_STAGE:caption"``,
    then STOPS.
    If the signal is absent: no-op — post remains at DEVELOP_STAGE:positioning.

Stage 2b+3 confirm_caption(post_id)
    Reads the Notion confirm signal for stage ``"caption"``.
    If present: reads the LOCKED angle + hook from the DB, builds story/body
    FROM those stored artifacts (never re-runs the full chain), then calls
    ``render.run``, ``brand_qc.run``, which advance the post to ``qc_review``
    (via the normal brand_qc path).  Clears the ``DEVELOP_STAGE:`` marker from
    qc_notes so the sweep guard and normal pull_gate treat the post as a regular
    in-review card.
    If absent: no-op.

Lock contract
-------------
Each confirm stage reads the artifact stored on the post by the PREVIOUS stage
and uses it as the seed for the next brick(s).  This ensures that the caption
is always derived from the exact angle the operator confirmed — not from a
freshly regenerated positioning that may differ on a live (non-deterministic)
Claude API call.

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
from collections import OrderedDict

import db
from db import Status
from engine.brain import ai_cmo_generate, bricks as bricks_mod
from engine.brain import voc as voc_mod
from engine.brain.libraries import load_libraries
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

    # TODO: wire real Notion develop_confirm property read
    """
    notion_token = os.environ.get("NOTION_TOKEN")
    if notion_token:
        # Real Notion: deferred — no-op for now, returns None (confirm not detected)
        # TODO: wire real Notion develop_confirm property read
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
# Helpers: build downstream artifacts from locked priors (lock-contract path)
# ---------------------------------------------------------------------------

def _build_hook_and_body_from_locked_angle(post_id: str, locked_angle: str) -> tuple[str, str]:
    """Build hook + body FROM the locked angle stored on the post.

    This is the Stage 2a brick layer.  We reconstruct a minimal artifacts dict
    that contains only the priors known at this stage (voc, intake, topic, angle)
    and call ``bricks.run_phase`` for hook then story — seeded with the locked
    angle.  The Claude call falls back to the offline artifact on any error, so
    this is always safe.

    Returns ``(hook, body)``.
    """
    post   = db.get_post(post_id)
    client = post["client"]
    seed   = post["seed_idea"]

    # Build a minimal locked-priors dict seeded with the confirmed angle.
    # voc is always offline-safe; intake and topic can be lightweight placeholders
    # because hook and story only need angle in prior_text to do their job.
    voc_signal = voc_mod.voice_of_customer(client, seed)

    artifacts: dict = OrderedDict()
    artifacts["voc"]    = voc_signal
    artifacts["intake"] = seed          # minimal prior — hook/story don't use it directly
    artifacts["topic"]  = post.get("pillar") or "Education"
    artifacts["angle"]  = locked_angle  # the confirmed, locked artifact

    if not ai_cmo_generate._configured():
        # Offline path: derive hook and story deterministically from the locked angle.
        # We use bricks._OFFLINE for hook but derive the story from the locked angle
        # so the offline body at least references the confirmed positioning.
        hook = bricks_mod._OFFLINE["hook"]
        body = f"[offline] {locked_angle} {bricks_mod._OFFLINE['story']}"
        return hook, body

    # Online path: build context block and run only hook + story phases.
    libs = load_libraries()
    ctx  = bricks_mod.context_block(client, libs, voc_signal)

    hook = bricks_mod.run_phase("hook",  ctx, seed, artifacts)
    artifacts["hook"] = hook
    body = bricks_mod.run_phase("story", ctx, seed, artifacts)
    return hook, body


def _build_body_from_locked_angle_and_hook(
    post_id: str, locked_angle: str, locked_hook: str
) -> str:
    """Build story/body FROM the locked angle + hook stored on the post.

    This is the Stage 2b brick layer.  Used by ``confirm_caption`` when the
    body has not been set yet (e.g. if stages are called out of sequence or the
    body was never stored).  In the normal flow the body was written by
    ``confirm_positioning``; this acts as a safety re-derivation.

    Returns ``body``.
    """
    post   = db.get_post(post_id)
    client = post["client"]
    seed   = post["seed_idea"]

    voc_signal = voc_mod.voice_of_customer(client, seed)

    artifacts: dict = OrderedDict()
    artifacts["voc"]    = voc_signal
    artifacts["intake"] = seed
    artifacts["topic"]  = post.get("pillar") or "Education"
    artifacts["angle"]  = locked_angle
    artifacts["hook"]   = locked_hook

    if not ai_cmo_generate._configured():
        return f"[offline] {locked_angle} {bricks_mod._OFFLINE['story']}"

    libs = load_libraries()
    ctx  = bricks_mod.context_block(client, libs, voc_signal)
    return bricks_mod.run_phase("story", ctx, seed, artifacts)


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
    """Stage 2a: if the Notion confirm signal is present, produce hook + body and STOP.

    Confirm signal: ``develop_confirm == "positioning"`` on the board card.
    If the signal is absent, this is a no-op — the post stays at DEVELOP_STAGE:positioning.

    On confirm: reads the LOCKED angle from the DB (written by ``start``), builds
    hook + body FROM that stored angle only — does NOT re-run the full chain.
    This guarantees the caption is derived from the exact positioning the operator
    confirmed, not from a freshly regenerated angle.  Writes ``hook`` + ``body``
    to the post and advances the stage to ``DEVELOP_STAGE:caption``.  Status
    remains ``captured``.
    """
    confirm = _read_develop_confirm(post_id)
    if confirm != "positioning":
        # No confirm signal or wrong stage — no-op
        return

    # Read the LOCKED angle from the DB — do NOT re-run run_chain.
    post = db.get_post(post_id)
    locked_angle = post.get("angle") or ""

    # Build hook + body from the locked angle only.
    hook, body = _build_hook_and_body_from_locked_angle(post_id, locked_angle)

    db.update_post(post_id, hook=hook, body=body, qc_notes="DEVELOP_STAGE:caption")


def confirm_caption(post_id: str) -> None:
    """Stage 2b+3: if the Notion confirm signal is present, render + QC + land at qc_review.

    Confirm signal: ``develop_confirm == "caption"`` on the board card.
    If the signal is absent, this is a no-op — the post stays at DEVELOP_STAGE:caption.

    On confirm: reads the LOCKED angle + hook from the DB (written by prior stages),
    ensures the body is derived from them if needed, then:
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

    # Read locked priors — body was already written by confirm_positioning.
    # If body is missing (out-of-order call or recovery), re-derive from locked angle+hook.
    post = db.get_post(post_id)
    locked_angle = post.get("angle") or ""
    locked_hook  = post.get("hook")  or ""
    if not post.get("body"):
        body = _build_body_from_locked_angle_and_hook(post_id, locked_angle, locked_hook)
        db.update_post(post_id, body=body)

    # Stage 2b: render image
    render.run(post_id)

    # Stage 3: brand QC — advances post to qc_review (or needs_revision)
    brand_qc.run(post_id)

    # Clear the DEVELOP_STAGE marker so the post re-enters the normal pipeline
    post = db.get_post(post_id)
    if post:
        cleaned = _clear_develop_stage(post.get("qc_notes"))
        db.update_post(post_id, qc_notes=cleaned)
