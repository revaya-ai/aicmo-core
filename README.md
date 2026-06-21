# aicmo-core

**The AI CMO.** A content marketing department that runs as software.

This is the hackathon build. One content idea ("a post") is a single database
row that walks through a status pipeline. Each station reads the row at one
status, does its job, and advances it to the next. **Two pieces are now real:
Station 1 (the Brain) and the Notion database, both built by our team** (see
"What our team built" below). The remaining stations are still stubs that return
canned data, swapped for real logic without ever touching the contract.

## Who this is for (ICP)
A small business with a marketing team of one, or a founder who can't afford a
marketing team at all. The AI CMO runs the content department for them: ideates,
designs, gets human sign-off, publishes, measures, and recommends paid promotion
on the winners.

Demo client: **Lumen Skin Studio**, a small-batch skincare brand
(`client-data/lumen-skin/`).

---

## What our team built (Card 1: Brain + the Notion database)

Our team owns two pieces. Both are real (not stubs), verified, and pushed. This
section is what we present.

### 1. The Brain (Station 1) — idea to on-brand draft

**What it is:** the "Think + Write" station. It turns a typed seed idea into an
on-brand drafted post, grounded in the client's own brand files, using the Brick
chain. No generic AI mush, because every post is five locked decisions before a
word is written.

- **The craft** lives in `.claude/skills/`: `content-os` (the 5-step Brick chain:
  Voice-of-Customer → Intake → Topic → Angle → Hook → Story), `writing-style`
  (anti-AI-slop), `positioning-angles`, `hook-library`, `story-structures`.
- **The command** `/ai-cmo-generate "<seed idea>"` runs the chain in Claude Code,
  loads the 6-layer client context, and persists the draft via
  `engine/save_draft.py`.
- **The offline engine** `engine/brain/generate.py` + `voc.py` parse the real
  client context (pillars, audience, voice) and produce a grounded draft with no
  API key, so the pipeline is testable offline.

Run it (offline, no keys):

```bash
python3 run.py "why competitors all sound the same"     # full loop; Brain is the first real station
# or persist a draft the exact way the command does:
python3 engine/save_draft.py --client lumen-skin --seed "..." \
  --pillar "Education" --angle "..." --hook "..." --body "..."
```

**How to present it:** "Marketing's bottleneck was never the writing, it was the
deciding. The Brain makes five locked decisions, pillar, angle, hook, story,
grounded in the client's own brand files, before it writes a word."

### 2. The Notion database (the human gate + client surface)

**What it is:** the client's real Notion board where every post lives and where
the one human decision happens, Approve or Reject, from a phone. SQLite stays the
engine's source of truth; Notion is the human surface, with a read-back that
turns the client's tap into a pipeline advance.

- `engine/dashboard/notion_provision.py` — creates the Content Pipeline database
  (the columns from Jen's board) in your Notion page.
- `engine/dashboard/notion_sync.py` — `push` (pipeline → board) and `pull` (the
  client's Approve/Reject → advances SQLite).
- `engine/dashboard/notion_schema.py` — property schema + status maps.
  `notion_client.py` — the API wrapper (stdlib, no extra install).

Run it (offline stub, no Notion account needed):

```bash
python3 engine/dashboard/notion_provision.py     # prints the schema, writes a stub db id
python3 engine/dashboard/notion_sync.py push     # writes outputs/notion-mirror.json (the stub board)
# flip a card's status_label to "Approved" to simulate the client, then:
python3 engine/dashboard/notion_sync.py pull     # advances the matching post to approved
```

**Go live:** set `NOTION_TOKEN` + `NOTION_PARENT_PAGE_ID`, then the same commands
hit the real Notion API. Same card shape, nothing downstream changes.

**How to present it:** "Six steps run themselves, the seventh is a person. They
open Notion, tap Approve, and the post ships. We built the board, the push, and
the read-back. One tap, eight seconds, from anywhere."

### Notion or a custom app?

Notion is the fast surface and it is what we demo. But SQLite is the source of
truth and Notion is just one surface hanging off `notion_sync`. For a real $1M
client you put a branded app on the same engine, no change to the Brain or the
pipeline. The database was never the product. The engine was.

## The contract-first rule
`db.py` is the **frozen contract**. It defines the `posts` table, the `Status`
constants, and the helper functions every station uses. Changing it requires
**all three builders to agree** — a schema change breaks everyone at once.
Everything else (the station internals) is yours to rewrite freely.

## The status pipeline

```
captured                          (a seed idea lands)
   |  brain.generate
drafted                           (pillar, angle, hook, body written)
   |  studio.render               (image_path set)
   |  studio.brand_qc
qc_review                         (passed visual QC, awaiting human)
   |  mission.gate  [HUMAN]
approved        (or rejected / needs_revision off-ramp)
   |  mission.schedule
scheduled
   |  mission.publish
published
   |  mission.analytics
analyzed                          (metrics in)
   |  ads.ads_agent               (only if it's a winner)
ad_recommended
   |  [HUMAN spend gate]
ad_approved
   |  ads.ads_agent
ad_live
```

Off-ramps: `needs_revision` and `rejected` (set at the human gate or by QC).

## The 4 stations (who owns what)

| Station | Folder | Reads -> Writes | Owner |
|---|---|---|---|
| 1. Brain | `engine/brain/` | `captured` -> `drafted` (Intake→Topic→Angle→Hook→Story brick chain) | Builder A |
| 2. Studio | `engine/studio/` | `drafted` -> image -> `qc_review` / `needs_revision` (HTML→PNG render + vision QC ≥85) | Builder B |
| 3. Mission | `engine/mission/` | `qc_review` -> `approved` -> `scheduled` -> `published` -> `analyzed` (human gate + publish + analytics) | Builder C |
| 4. Ads | `engine/ads/` | `analyzed` -> `ad_recommended` -> `ad_approved` -> `ad_live` (recommend-only, human spend gate) | Builder C |

## How to run

No installs needed for the stub loop. Standard library only.

```bash
python run.py "why your competitors all sound the same"
```

This creates a post, walks it through every station, prints each status
transition, and prints the final row as JSON. It runs green on minute one.

The human gate and the ad spend gate auto-approve in `run.py` (via
`auto_approve=True`) so the demo completes unattended.

## For builders

1. Read `db.py`. That is the contract. **Do not change it** without the other
   two builders agreeing.
2. Open your station file. The docstring tells you exactly which status you read,
   which status you write, and the function signature.
3. Find the `# TODO(builder):` markers. Replace the stub logic there with real
   logic. Keep the same read/write statuses and the same `run(post_id,
   auto_approve=False)` signature.
4. Run `python run.py "..."` after every change. The loop must stay green.

Real builds will need the deps in `requirements.txt` and the keys in
`.env.example` (copy it to `.env`). The stub loop needs neither.

## Layout

```
db.py            # FROZEN CONTRACT (schema + helpers)
run.py           # orchestrator — walks one idea through every station
client-data/     # 6-layer context per client (lumen-skin demo)
templates/       # social post template (Station 2 screenshots this)
engine/          # the 4 stations
data/            # aicmo.db created here (gitignored)
```
