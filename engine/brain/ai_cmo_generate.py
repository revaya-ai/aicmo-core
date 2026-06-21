"""STATION 1B, Brain: real Brick chain generation.

run(post_id, auto_approve=False) — identical signature to generate.run so
run.py and the sweep call it unchanged. When ANTHROPIC_API_KEY is unset or
any call errors, delegates to the deterministic offline generate.run.

run_chain(post_id) — runs the six bricks in order, returning an OrderedDict
with EXACTLY these keys: voc, intake, topic, angle, hook, story. No extras.
The assemble step (producing the DB-ready draft dict) lives in bricks.assemble,
called by run() after run_chain returns.
"""

import os
from collections import OrderedDict

from db import Status, get_post, advance
from engine.brain import voc as voc_mod
from engine.brain import generate as offline
from engine.brain.libraries import load_libraries
from engine.brain import bricks

# The six phase keys in the order they must be returned.
PHASES = ["voc", "intake", "topic", "angle", "hook", "story"]


def _configured() -> bool:
    """True when a real Anthropic API key is available."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _offline_context(client: str) -> dict:
    """Mirror generate.run's context assembly for the offline fallback."""
    strategy_md = offline._read(client, "strategy.md")
    brand_md    = offline._read(client, "brand-and-audience.md")
    voice_md    = offline._read(client, "voice.md")
    return {
        "pillars":     offline.parse_pillars(strategy_md),
        "audience":    offline.parse_primary_audience(brand_md),
        "is_anti_hype": "anti-hype" in voice_md.lower(),
    }


def run_chain(post_id: str) -> OrderedDict:
    """Run the six bricks in order, locking one artifact per phase.

    Returns an OrderedDict with EXACTLY the keys:
        voc, intake, topic, angle, hook, story
    (no _draft, no body — assemble is called separately in run())

    When no API key is present, all six artifacts are derived deterministically
    from the offline stub so the chain is fully testable without network access.
    """
    post = get_post(post_id)
    client, seed = post["client"], post["seed_idea"]

    # Phase 0: Voice of Customer — always offline-safe.
    voc_signal = voc_mod.voice_of_customer(client, seed)

    artifacts = OrderedDict()
    artifacts["voc"] = voc_signal

    if not _configured():
        # Offline path: derive remaining five phases from the deterministic stub.
        ctx      = _offline_context(client)
        feedback = post.get("human_note")
        draft    = offline.generate_draft(seed, ctx, feedback=feedback)

        artifacts["intake"] = seed
        artifacts["topic"]  = draft["pillar"]
        artifacts["angle"]  = draft["angle"]
        artifacts["hook"]   = draft["hook"]
        artifacts["story"]  = draft["body"]
        return artifacts

    # Online path: one cached context block, five sequential Claude calls.
    libs = load_libraries()
    ctx  = bricks.context_block(client, libs, voc_signal)

    for phase in PHASES[1:]:   # skip "voc" — already set
        artifacts[phase] = bricks.run_phase(phase, ctx, seed, artifacts)

    return artifacts


def run(post_id: str, auto_approve: bool = False) -> None:
    """Entry point. Identical signature to generate.run.

    If no API key: delegates entirely to the offline station (preserves all
    existing behaviour including human_note fold-in and auto_approve).
    If keyed: runs the real Brick chain, assembles the draft, and advances.
    """
    if not _configured():
        return offline.run(post_id, auto_approve)

    artifacts = run_chain(post_id)
    d = bricks.assemble(artifacts)
    advance(
        post_id,
        Status.DRAFTED,
        pillar=d["pillar"],
        angle=d["angle"],
        hook=d["hook"],
        body=d["body"],
    )
