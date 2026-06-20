"""BRICK PHASE 0, Brain: Voice of Customer.

Phase 0 runs BEFORE Intake. The source materials start the content chain with
Voice of Customer, not with the seed idea, so the chain is:

    Phase 0 Voice of Customer -> Intake -> Topic -> Angle -> Hook -> Story

voice_of_customer(client, seed_idea) returns the VoC signal that informs every
downstream brick: the audience persona, the real pain points, and the actual
phrases customers use. The default path is a DETERMINISTIC OFFLINE stub that
reads the client's 6-layer context (client-data/<client>/brand-and-audience.md
and strategy.md) and derives the signal from what is really written there: the
primary audience, what the audience cares about, and what turns them off. No
API, no network, no dependencies, so the loop runs offline.

A configured DataForSEO client MAY be injected to enrich the phrasing with real
query language (how people phrase the topic inside search and AI tools). That is
strictly additive. When no client is injected, or the injected client is not
configured, the offline signal stands on its own and the function never touches
the network.
"""

import os
import re

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


def _parse_primary_audience(brand_md: str) -> str:
    """Pull the primary audience persona name from brand-and-audience.md."""
    lines = brand_md.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("## primary audience"):
            for follow in lines[i + 1 : i + 5]:
                match = re.search(r'\*\*"?(.+?)"?\*\*', follow)
                if match:
                    return match.group(1).strip().strip('"')
    return ""


def _parse_bullets_under(brand_md: str, heading_prefix: str) -> list:
    """Collect markdown bullet lines under a heading until the next heading."""
    bullets = []
    in_section = False
    for line in brand_md.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(heading_prefix.lower()):
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def voice_of_customer(client: str, seed_idea: str, dataforseo_client=None) -> dict:
    """Build the Voice of Customer signal for a client and seed idea.

    Returns a dict with: audience, pain_points (list), customer_phrases (list),
    seed_idea. Offline by default and grounded in the loaded client context. The
    optional dataforseo_client enriches customer_phrases only when it is both
    provided and configured.
    """
    brand_md = _read(client, "brand-and-audience.md")
    _strategy_md = _read(client, "strategy.md")

    audience = _parse_primary_audience(brand_md) or "your reader"

    # "What turns them off" maps directly to pain points the content must answer.
    turn_offs = _parse_bullets_under(brand_md, "## what turns them off")
    # "What they care about" becomes the language the customer actually uses.
    cares = _parse_bullets_under(brand_md, "## what they care about")

    pain_points = list(turn_offs)
    customer_phrases = list(cares)

    # Always anchor at least one signal to the seed so the chain has a thread.
    seed = seed_idea.strip()
    if seed:
        customer_phrases.append(seed)

    # Optional live enrichment. Strictly additive and only when configured.
    if dataforseo_client is not None:
        try:
            if dataforseo_client.is_configured():
                enriched = dataforseo_client.ai_keyword_data([seed])
                for task in enriched.get("tasks", []):
                    for result in task.get("result", []) or []:
                        phrase = result.get("keyword")
                        if phrase:
                            customer_phrases.append(phrase)
        except Exception:
            # Enrichment is best effort. The offline signal already stands.
            pass

    return {
        "audience": audience,
        "pain_points": pain_points,
        "customer_phrases": customer_phrases,
        "seed_idea": seed,
    }
