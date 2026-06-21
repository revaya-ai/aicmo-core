# aicmo-core

**The AI CMO.** A content marketing department that runs as software.

One content idea ("a post") is a single database row that walks through a status
pipeline. Each station reads the row at one status, does its job, and advances it
to the next: it ideates, designs, gets human sign-off, publishes, measures, and
recommends paid promotion on the winners.

The whole loop runs OFFLINE on the Python standard library with no API keys.
Every external service (image render, publishing, analytics, ad platforms) has a
stub that runs by default and only calls the real service when the matching env
var is set. So a fresh clone walks a seed idea from `captured` all the way to
`ad_live` with one command and no setup.

This repo is the engine. The Brain (Station 1) and the Notion client are real;
the other stations run as stubs today and swap in real logic without ever
touching the contract. The full platform across all six sections, with the build
status of every component, is mapped in
[`docs/BUILD-TARGET.md`](docs/BUILD-TARGET.md).

## Who this is for (ICP)
A small business with a marketing team of one, or a founder who can't afford a
marketing team at all. The AI CMO runs the content department for them: ideates,
designs, gets human sign-off, publishes, measures, and recommends paid promotion
on the winners.

Demo client: **Lumen Skin Studio**, a small-batch skincare brand
(`client-data/lumen-skin/`).

## The contract-first rule
`db.py` is the **frozen contract**. It defines the `posts` table, the `Status`
constants, and the helper functions every station uses. Changing it requires all
builders to agree. A schema change breaks everyone at once. Everything else (the
station internals) is yours to rewrite freely.

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

## The 4 stations

| Station | Folder | Reads -> Writes | What it does |
|---|---|---|---|
| 1. Brain | `engine/brain/` | `captured` -> `drafted` | Turns a seed idea into an on-brand draft via the Brick chain (Intake, Topic, Angle, Hook, Story), grounded in the client's own brand files. |
| 2. Studio | `engine/studio/` | `drafted` -> image -> `qc_review` / `needs_revision` | Renders the post to a 1080x1350 graphic and scores it against the brand spec (vision QC). |
| 3. Mission | `engine/mission/` | `qc_review` -> `approved` -> `scheduled` -> `published` -> `analyzed` | The human approval gate, then schedule, publish, and pull analytics. |
| 4. Ads | `engine/ads/` | `analyzed` -> `ad_recommended` -> `ad_approved` -> `ad_live` | Recommends paid promotion on winners only, behind a human spend gate. |

The one human decision lives between render and publish: `mission.gate`. For which
stations are real, stubbed, or not built, see
[`docs/BUILD-TARGET.md`](docs/BUILD-TARGET.md).

## How to run the loop

No installs needed. Standard library only.

```bash
python3 run.py "why your competitors all sound the same"
```

This creates a post, walks it through every station, prints each status
transition, and prints the final row as JSON. The post ends at `ad_live` if it is
a winner, or `analyzed` if its engagement does not clear the promote threshold.

The published URL is a stub; real publishing needs `ZERNIO_API_KEY`. The Notion
board writes to `outputs/notion-mirror.json` offline, and to a real board behind
`NOTION_TOKEN` plus `NOTION_PARENT_PAGE_ID`. The human gate and the ad spend gate
auto-approve in `run.py` (via `auto_approve=True`) so the loop completes
unattended; in production a person taps Approve in Notion.

## The Brain command

The craft lives in skills, the Brain runs through a command. `/ai-cmo-generate`
is a Claude Code command, not a shell command. Without Claude Code, walk the loop
with `python3 run.py "<seed>"`.

| Command | Walks | Skills loaded |
|---|---|---|
| `/ai-cmo-generate "<seed>"` | `captured` -> `drafted` | content-os, positioning-angles, writing-style, hook-library, story-structures |

## The full architecture

The four-station loop is the spine. The complete platform adds onboarding and VPS
setup, the front-of-funnel intelligence and AEO layer, the render and Placid
backends, distribution scheduling, and the analytics, SEO, GEO, and client
dashboard layer. All of it, section by section with the build status of every
component, is in [`docs/BUILD-TARGET.md`](docs/BUILD-TARGET.md). The reference
implementation for the parts not yet built here lives in the sibling repo
`aicmo-complete`.

## Going real (optional)

Each stub upgrades to the real service by setting one env var. The loop never
needs any of these. Every variable the full system uses, grouped by station and
commented, is in [`.env.example`](.env.example). Today the only env vars the
engine actually reads are `NOTION_TOKEN` and `NOTION_PARENT_PAGE_ID` (the Notion
board). The rest are the seams each station wires as it goes real. For the
named-tool audit (which service each station reads, and its real status), see
[`docs/qa/reference-architecture.md`](docs/qa/reference-architecture.md).

## QA

This system is checked against its source materials, not just against itself. The
QA approach, the auditor charter, and the audit trail live in
[`docs/qa/README.md`](docs/qa/README.md). The principle: a QA pass that audits the
code against an incomplete spec still ships an incomplete system, so the spec
itself gets audited against the source.

## Layout

```
db.py            # FROZEN CONTRACT (schema + helpers)
run.py           # orchestrator, walks one idea through every station
client-data/     # 6-layer context per client (lumen-skin demo)
templates/       # social post template (Station 2 renders this)
engine/          # the 4 stations + the Notion dashboard client
.claude/skills/  # the craft: content-os, positioning-angles, writing-style, hook-library, story-structures
.claude/commands/ # the Brain: ai-cmo-generate
docs/            # BUILD-TARGET.md (full map), qa/ (audit), notion-setup.md, superpowers/ (plans + specs)
data/            # aicmo.db created here (gitignored)
outputs/         # notion-mirror.json (stub board, gitignored)
```
