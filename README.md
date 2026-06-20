# aicmo-core

**The AI CMO.** A content marketing department that runs as software.

This is the hackathon skeleton. One content idea ("a post") is a single database
row that walks through a status pipeline. Each station reads the row at one
status, does its job, and advances it to the next. Today every station is a
**stub** that returns canned data. Builders swap stubs for real logic without
ever touching the contract.

## Who this is for (ICP)
A small business with a marketing team of one, or a founder who can't afford a
marketing team at all. The AI CMO runs the content department for them: ideates,
designs, gets human sign-off, publishes, measures, and recommends paid promotion
on the winners.

Demo client: **Lumen Skin Studio**, a small-batch skincare brand
(`client-data/lumen-skin/`).

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

## Card 3 — Mission Control

- `engine/mission/gate.py` — the human board (two gates): content Approve/Revise/Reject and ad spend Approve/Decline. Run: `.venv/bin/python engine/mission/gate.py` → http://localhost:5050
- `engine/mission/driver.py` — `drive(post_id)` runs schedule → publish → analytics → ads after approval; shared by the board and `run.py`.
- `engine/mission/{schedule,publish,analytics}.py` — demo-safe smart stubs (no API keys).
- `engine/ads/ads_agent.py` — winner score + Claude rationale (templated fallback) + stub ad pusher behind the spend gate.

Tests: `.venv/bin/python -m pytest tests/mission/ -v`

## Layout

```
db.py            # FROZEN CONTRACT (schema + helpers)
run.py           # orchestrator — walks one idea through every station
client-data/     # 6-layer context per client (lumen-skin demo)
templates/       # social post template (Station 2 screenshots this)
engine/          # the 4 stations
data/            # aicmo.db created here (gitignored)
```
