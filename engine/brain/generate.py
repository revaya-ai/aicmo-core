"""STATION 1, Brain: idea to draft.

Reads:  status == captured  (uses seed_idea)
Writes: status == drafted   (sets pillar, angle, hook, body)

Signature: run(post_id: str, auto_approve: bool = False) -> None

The Brain is a chain of "bricks", each one transforming the post a little:
    Intake -> Topic -> Angle -> Hook -> Story

This module is the DETERMINISTIC OFFLINE stand-in for that chain. It genuinely
loads and uses the client's 6-layer context (client-data/<client>/*.md): it
parses the real content pillars from strategy.md, picks one deterministically by
hashing the seed, pulls the primary audience from brand-and-audience.md, and
respects the voice from voice.md. The output is grounded in the loaded context,
not constants. It uses no API and has no dependencies, so the loop runs offline.

The production-quality copy comes from the /ai-cmo-generate command (the
model-driven Brick chain), which calls Claude per brick with this same context.
This stand-in exists so the pipeline is testable and runnable with zero keys.
"""

import hashlib
import os
import re

from db import Status, get_post, advance

CLIENT_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "client-data"
)


def _read(client: str, filename: str) -> str:
    """Read a client-data file, returning '' if it is missing."""
    path = os.path.join(CLIENT_DATA_DIR, client, filename)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_pillars(strategy_md: str) -> list:
    """Pull the content pillar names out of strategy.md.

    The strategy file lists pillars as bold markdown items under a pillars
    heading, e.g. "1. **Education (40%)** ...". We extract the bold label and
    strip the trailing weight in parentheses, returning clean pillar names like
    "Education", "Proof", "Behind the studio", "Offers".
    """
    pillars = []
    in_pillars = False
    for line in strategy_md.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## content pillars"):
            in_pillars = True
            continue
        if in_pillars and stripped.startswith("## "):
            break
        if in_pillars:
            match = re.search(r"\*\*(.+?)\*\*", stripped)
            if match:
                label = match.group(1)
                # Drop a trailing "(40%)" weight if present.
                label = re.sub(r"\s*\(.*?\)\s*$", "", label).strip()
                if label:
                    pillars.append(label)
    return pillars


def parse_primary_audience(brand_md: str) -> str:
    """Pull the primary audience persona name from brand-and-audience.md.

    Returns the quoted persona name (e.g. 'Overwhelmed Olivia') from the line
    following the "## Primary audience" heading, or '' if not found.
    """
    lines = brand_md.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## primary audience"):
            # Scan the next few non-empty lines for a bold or quoted persona.
            for follow in lines[i + 1 : i + 5]:
                match = re.search(r'\*\*"?(.+?)"?\*\*', follow)
                if match:
                    return match.group(1).strip().strip('"')
    return ""


def pick_pillar(pillars: list, seed: str) -> str:
    """Deterministically pick one pillar from the real list by hashing the seed.

    Same seed always picks the same pillar. Falls back to 'Education' only when
    strategy.md yielded no pillars at all.
    """
    if not pillars:
        return "Education"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    index = digest[0] % len(pillars)
    return pillars[index]


def generate_draft(seed: str, context: dict) -> dict:
    """Build pillar, angle, hook, body from the seed plus the loaded context.

    context carries: pillars (list), audience (str), is_anti_hype (bool from
    voice.md). The output references the real audience and pillar so it is
    grounded, not a constant.
    """
    premise = seed.strip()
    pillars = context.get("pillars") or []
    audience = context.get("audience") or "your reader"

    pillar = pick_pillar(pillars, premise)

    angle = (
        f"Through the {pillar} pillar: most brands get '{premise}' wrong. "
        f"Here is the simpler truth for {audience}."
    )

    hook = f"{premise} is not a skincare problem. It is a routine problem."

    body = (
        f"{premise}\n\n"
        f"If you are {audience}, you have heard this a hundred ways. "
        "Here is what actually moves the needle for your skin, without the "
        "10-step routine. Pick three things, do them every day, give it four "
        "weeks.\n\n"
        "Simple beats fancy. That is the Lumen Skin Studio way."
    )

    return {"pillar": pillar, "angle": angle, "hook": hook, "body": body}


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)
    seed = post["seed_idea"]
    client = post["client"]

    # --- Brick: Intake ---------------------------------------------------
    # Load the real 6-layer context for this client.
    strategy_md = _read(client, "strategy.md")
    brand_md = _read(client, "brand-and-audience.md")
    voice_md = _read(client, "voice.md")

    pillars = parse_pillars(strategy_md)
    audience = parse_primary_audience(brand_md)
    is_anti_hype = "anti-hype" in voice_md.lower()

    context = {
        "pillars": pillars,
        "audience": audience,
        "is_anti_hype": is_anti_hype,
    }

    # --- Bricks: Topic -> Angle -> Hook -> Story -------------------------
    draft = generate_draft(seed, context)

    advance(
        post_id,
        Status.DRAFTED,
        pillar=draft["pillar"],
        angle=draft["angle"],
        hook=draft["hook"],
        body=draft["body"],
    )
