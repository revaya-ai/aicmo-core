"""BRAIN MOCK — Claude-powered stand-in for Shannon's real Brick chain.

Reads the 6-layer client context and runs a condensed version of the
5-brick chain via Claude so you can see the full creative journey without
waiting for the real Brain to be built.

Usage: imported by run_demo.py instead of engine/brain/generate.py
"""

from pathlib import Path
from dotenv import load_dotenv
import anthropic

from db import Status, get_post, advance

REPO_ROOT    = Path(__file__).resolve().parents[2]
CLIENT_DATA  = REPO_ROOT / "client-data" / "lumen-skin"
load_dotenv(REPO_ROOT / ".env")

MODEL = "claude-sonnet-4-6"


def _load_context() -> str:
    files = [
        "positioning.md", "brand-and-audience.md", "strategy.md",
        "offers.md", "voice.md", "guardrails.md",
    ]
    parts = []
    for f in files:
        path = CLIENT_DATA / f
        if path.exists():
            parts.append(f"## {f}\n{path.read_text().strip()}")
    return "\n\n".join(parts)


def run(post_id: str, auto_approve: bool = False) -> None:
    post    = get_post(post_id)
    seed    = post["seed_idea"]
    context = _load_context()
    client  = anthropic.Anthropic()

    # --- Brick 1+2: Topic + Angle ---
    r = client.messages.create(
        model=MODEL, max_tokens=300,
        system=f"You are a content strategist. Use only the brand context below.\n\n{context}",
        messages=[{"role": "user", "content":
            f"Seed idea: \"{seed}\"\n\n"
            "Reply in this exact format:\n"
            "PILLAR: <one of: Education | Authority | Story | Offer>\n"
            "ANGLE: <one sharp sentence — the angle competitors aren't using>"
        }]
    )
    lines  = {l.split(":")[0].strip(): ":".join(l.split(":")[1:]).strip()
              for l in r.content[0].text.strip().splitlines() if ":" in l}
    pillar = lines.get("PILLAR", "Education")
    angle  = lines.get("ANGLE", seed)

    # --- Brick 3: Hook ---
    r = client.messages.create(
        model=MODEL, max_tokens=120,
        system=f"You write scroll-stopping LinkedIn hooks. Brand voice rules:\n\n{(CLIENT_DATA / 'voice.md').read_text()}",
        messages=[{"role": "user", "content":
            f"Angle: {angle}\nWrite ONE hook line. No em dashes. No generic openers. Max 15 words."
        }]
    )
    hook = r.content[0].text.strip().strip('"')

    # --- Brick 4+5: Story + anti-slop pass ---
    guardrails = (CLIENT_DATA / "guardrails.md").read_text()
    r = client.messages.create(
        model=MODEL, max_tokens=600,
        system=(
            f"You write LinkedIn posts in the client's exact voice.\n\n"
            f"BRAND CONTEXT:\n{context}\n\n"
            f"GUARDRAILS:\n{guardrails}"
        ),
        messages=[{"role": "user", "content":
            f"Hook: {hook}\nAngle: {angle}\n\n"
            "Write the full post body (3-5 short paragraphs). "
            "No em dashes. No 'game-changer', 'revolutionary', or hollow openers. "
            "End with one direct sentence the reader can act on today."
        }]
    )
    body = r.content[0].text.strip()

    print(f"  [brain.mock] pillar={pillar} | hook={hook[:60]}…")
    advance(post_id, Status.DRAFTED, pillar=pillar, angle=angle, hook=hook, body=body)
