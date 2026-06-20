---
description: BRAIN station. Turn a typed seed idea into an on-brand drafted post for a client, using the Brick chain, then persist it at status "drafted".
---

# /ai-cmo-generate

Take a seed idea and produce one on-brand draft for the client, ready for the Studio station to render and QC.

**Argument:** the seed idea, as free text. Example: `/ai-cmo-generate why competitors all sound the same`

**Client:** `lumen-skin` (the demo client for the hackathon).

## What to do

1. **Load the craft.** Read these three skills and follow them:
   - `content-os` (the Brick chain, the method you run)
   - `positioning-angles` (loaded by the Angle step)
   - `writing-style` (loaded by the Story and Shift step)

2. **Load the client context.** Read all six layers in `client-data/lumen-skin/`:
   - `positioning.md`, `brand-and-audience.md`, `strategy.md`, `offers.md`, `voice.md`, `guardrails.md`
   Do not invent brand facts. If a file is missing, stop and report the exact path.

3. **Run the Brick chain** from `content-os`, in order, locking each step:
   - Step 1 Intake: restate the seed in one line.
   - Step 2 Topic and pillar: one-line topic plus the pillar it serves, chosen from `strategy.md`.
   - Step 3 Angle: choose one named angle from `positioning-angles`.
   - Step 4 Hook: line one only, five to ten words, opens an information gap.
   - Step 5 Story and shift: outline the arc, write the body, run the `writing-style` self-check. Do not lock the body until the self-check passes.

4. **Persist the draft.** Run this exact command from the repo root, substituting your four locked artifacts:

```bash
python3 engine/save_draft.py --client lumen-skin --seed "$ARGUMENTS" \
  --pillar "<locked pillar>" --angle "<locked angle>" \
  --hook "<locked hook>" --body "<locked body>"
```

5. **Report back** the new record id (printed by the script) plus a short summary of the locked pillar, angle, and hook, and the full body.

## Rules

- Write ONLY these fields: pillar, angle, hook, body. Status becomes `drafted` automatically.
- Do not modify `db.py` or any other station's files.
- No em dashes or hyphens as breaks. No emojis. Show, do not claim. One idea per post.
