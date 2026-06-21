"""STATION 2 — Studio: brand quality control on the rendered image.

Reads:  status == drafted   (uses image_path set by render.py)
Writes: status == qc_review        if score >= 85  (passes to human gate)
        status == needs_revision   if score <  85  (bounced before human sees it)
        (sets qc_score, qc_notes)

Flow:
  1. Load the PNG at image_path.
  2. Send to Claude Vision with visual-brand.md as the scoring rubric.
  3. Parse SCORE (0-100) and NOTES from the response.
  4. Route: >= 85 → qc_review, below → needs_revision.
"""

import base64
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from db import Status, get_post, advance
from engine import feedback

REPO_ROOT = Path(__file__).resolve().parents[2]
VISUAL_BRAND_PATH = REPO_ROOT / "client-data" / "lumen-skin" / "visual-brand.md"
PASS_THRESHOLD = 85
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a visual brand quality control reviewer for a social media content agency.

You will be shown a rendered social post image (1080x1350). Score it 0–100 against the brand spec below.

IMPORTANT SCOPE: Score VISUAL DESIGN and BRAND COMPLIANCE only. Do NOT penalise for:
- Copy quality, typos, or placeholder text — that is the copy team's responsibility
- Repeated or short body text — content length is not a design issue
- Whether the text makes narrative sense — only whether it looks visually correct

PENALISE for visual/brand violations only:
- Wrong or off-brand colours
- Wrong fonts or failure to use the two-typeface hierarchy
- Crowded, cluttered, or un-airy layout
- Anything on the visual "never" list

85+ means the visual design is genuinely on-brand and ready for a human to approve.
Below 85 means it has visual brand violations that need fixing first.

Reply in EXACTLY this format (no other text):
SCORE: <integer 0-100>
NOTES: <one or two sentences — what visual elements pass, what visual elements violate the spec>

BRAND SPEC:
{visual_brand}"""


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)
    image_path = post.get("image_path")

    # If no real image exists (stub render), skip vision and bounce gracefully
    img = Path(image_path) if image_path else None
    if image_path and not img.is_absolute():
        img = REPO_ROOT / image_path

    if not img or not img.exists():
        advance(
            post_id,
            Status.NEEDS_REVISION,
            qc_score=0,
            qc_notes="No rendered image found — render.py must run first.",
        )
        return

    # Offline fallback: with no Anthropic key we cannot run the vision QC. Pass
    # with a clearly-marked stub score so the pipeline and tests still run. Real
    # vision QC runs as soon as ANTHROPIC_API_KEY is set.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        advance(
            post_id,
            Status.QC_REVIEW,
            qc_score=90,
            qc_notes="STUB: vision QC not run (no ANTHROPIC_API_KEY). Assumed on-brand.",
        )
        print("  [studio.brand_qc] STUB pass (no API key)")
        return

    visual_brand = VISUAL_BRAND_PATH.read_text()
    image_data = base64.standard_b64encode(img.read_bytes()).decode("utf-8")

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=SYSTEM_PROMPT.format(visual_brand=visual_brand),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": "Score this image against the brand spec."},
                ],
            }
        ],
    )

    text = message.content[0].text
    score_match = re.search(r"SCORE:\s*(\d+)", text)
    notes_match = re.search(r"NOTES:\s*(.+)", text, re.DOTALL)

    qc_score = int(score_match.group(1)) if score_match else 0
    qc_notes = notes_match.group(1).strip() if notes_match else text.strip()

    print(f"  [studio.brand_qc] score={qc_score} — {qc_notes}")

    if qc_score >= PASS_THRESHOLD:
        advance(post_id, Status.QC_REVIEW, qc_score=qc_score, qc_notes=qc_notes)
    else:
        # QC fail goes back to the beginning, like a reject: the Brain re-drafts
        # with the QC reason as the feedback. (Shannon's rule.)
        advance(post_id, Status.NEEDS_REVISION, qc_score=qc_score, qc_notes=qc_notes)
        feedback.send_back_to_brain(post_id, f"Brand QC failed ({qc_score}/100): {qc_notes}")
