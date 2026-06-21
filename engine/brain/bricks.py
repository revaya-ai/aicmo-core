"""Brick phase helpers for the AI CMO real chain.

context_block   — builds the cacheable 6-layer + libraries + VoC context list
                  with Anthropic prompt caching mark.
run_phase       — makes ONE Claude call per phase; falls back to offline artifact
                  on any error so the loop never crashes.
assemble        — combines artifacts into the {pillar, angle, hook, body} dict
                  that advance() expects.

Phase order: voc -> intake -> topic -> angle -> hook -> story
(voc is handled by ai_cmo_generate.run_chain before entering the loop)
"""

import os
import json

# ---------------------------------------------------------------------------
# Offline fallback artifacts by phase (used when Claude call fails).
# ---------------------------------------------------------------------------
_OFFLINE: dict = {
    "intake":  "Intake: seed idea locked (offline fallback).",
    "topic":   "Education",
    "angle":   "Simpler routines win. Most brands overcomplicate it.",
    "hook":    "The routine problem is not the ingredients.",
    "story":   "Pick three things. Do them every day. Give it four weeks. Simple beats fancy.",
}


def context_block(client: str, libs: dict, voc_signal: dict) -> list:
    """Build the cacheable context list for Anthropic messages.

    Returns a list of content blocks that can be embedded in the 'user' turn.
    The last block is marked cache_control ephemeral so the 6-layer + libraries
    are cached across the six sequential phase calls, targeting ~$0.02/post.
    """
    client_data_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "client-data", client
    )

    def _read(fname: str) -> str:
        path = os.path.join(client_data_dir, fname)
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    strategy   = _read("strategy.md")
    brand      = _read("brand-and-audience.md")
    voice      = _read("voice.md")
    offers     = _read("offers.md")
    competitor = _read("competitor-notes.md")
    seo        = _read("seo-notes.md")

    libs_text = "\n\n".join(
        f"## {key}\n{val}" for key, val in libs.items()
    )
    voc_text = json.dumps(voc_signal, indent=2)

    combined = (
        f"## Client: {client}\n\n"
        f"### Strategy\n{strategy}\n\n"
        f"### Brand & Audience\n{brand}\n\n"
        f"### Voice\n{voice}\n\n"
        f"### Offers\n{offers}\n\n"
        f"### Competitor Notes\n{competitor}\n\n"
        f"### SEO Notes\n{seo}\n\n"
        f"## Libraries\n{libs_text}\n\n"
        f"## Voice of Customer Signal\n{voc_text}"
    )

    # Mark with cache_control so the shared context is cached across calls.
    return [
        {
            "type": "text",
            "text": combined,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def run_phase(phase: str, ctx: list, seed: str, artifacts: dict) -> str:
    """Make one Claude call for a single phase; fall back to offline on any error.

    Parameters
    ----------
    phase     : one of intake | topic | angle | hook | story
    ctx       : the cached context block list (from context_block())
    seed      : the original seed idea for the post
    artifacts : ordered dict of all phases locked so far (prior outputs)
    """
    try:
        import anthropic  # imported here so offline path never requires the package

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        prior_text = "\n".join(
            f"{k}: {v}" for k, v in artifacts.items() if k != "voc"
        )

        phase_instructions = {
            "intake": (
                "You are the Intake brick. Your job: confirm and restate the seed idea "
                "as a single crisp sentence that the downstream bricks will work from. "
                f"Seed idea: {seed}\n\nReturn only the intake sentence."
            ),
            "topic": (
                "You are the Topic brick. Pick the single best content pillar for this post "
                "from the strategy.md pillars. Return only the pillar name, nothing else."
            ),
            "angle": (
                "You are the Angle brick. Write a single sentence angle (the fresh take / "
                "contrarian claim) for this post. Match the client voice. Return only the angle."
            ),
            "hook": (
                "You are the Hook brick. Write a single punchy opening hook line (max 12 words) "
                "that stops the scroll. Return only the hook."
            ),
            "story": (
                "You are the Story brick. Write the full post body (100-150 words). "
                "Match the voice profile. Use the locked angle and hook. "
                "Return only the body text."
            ),
        }

        instruction = phase_instructions.get(
            phase,
            f"You are the {phase} brick. Process the seed idea and return your output."
        )

        prompt_text = (
            f"{instruction}\n\n"
            f"Prior locked artifacts:\n{prior_text}\n\n"
            f"Seed idea: {seed}"
        )

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": ctx + [{"type": "text", "text": prompt_text}],
                }
            ],
        )

        result = response.content[0].text.strip()
        return result if result else _OFFLINE.get(phase, f"{phase} output")

    except Exception:
        # Never crash the loop. Return deterministic offline artifact.
        return _OFFLINE.get(phase, f"{phase} offline fallback")


def assemble(artifacts: dict) -> dict:
    """Combine the six locked artifacts into the draft dict advance() expects.

    Returns {pillar, angle, hook, body}.
    """
    return {
        "pillar": artifacts.get("topic", "Education"),
        "angle":  artifacts.get("angle", _OFFLINE["angle"]),
        "hook":   artifacts.get("hook",  _OFFLINE["hook"]),
        "body":   artifacts.get("story", _OFFLINE["story"]),
    }
