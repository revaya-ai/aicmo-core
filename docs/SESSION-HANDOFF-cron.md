# AI CMO — Session Handoff (for the local-cron work)

> Hand this to the next session. Goal there: build the **local cron orchestration**
> (no VPS — runs on the Mac). Everything below is current as of 2026-06-21.

---

## What this is

The **AI CMO**: a content marketing department that runs as software. The live
framing is **Jamie's organic-to-paid engine**: post organically → measure
**follows** → put ad budget only behind the **top 2-3 winners**.

Our team's scope was **Card 1 (Brain) + the Notion database**. Two other builders
did **Card 2 (Studio: render + QC)** and **Card 3 (Mission: publish + ads + gate)**.
**All four are merged to `main`.**

- Repo: `/Users/short/Downloads/aicmo-core`
- GitHub: `revaya-ai/aicmo-core`, branch `main` (everything pushed)

---

## The architecture (the model the cron plugs into)

- **Notion = the client database.** Everything is stored there and every action
  happens there: approve / comment / reject content, approve / decline ad spend,
  submit ideas (intake).
- **SQLite (`db.py`) = the engine's local working store** (the frozen contract).
  It mirrors to Notion both ways. Notion is what the client sees; SQLite is what
  the agents read/write locally.
- **Local machine = orchestration.** No VPS. The cron's job is to run the agent
  pipeline and sync Notion on a schedule.
- **Flask** (`engine/mission/gate.py`, localhost:5050) is a **dev-only** local
  approval page. The client never uses it. Notion is the real gate.

### The pipeline (statuses in `db.py` `Status`)
```
captured → drafted → qc_review →[HUMAN]→ approved → scheduled → published
        → analyzed → ad_recommended →[HUMAN]→ ad_approved → ad_live
off-ramps: needs_revision, rejected   (reject / QC-fail loop back to the Brain)
```
Two human gates (qc_review = content, ad_recommended = ad spend). Everything else
is automated. No script ever sets `approved` or `ad_approved` — only a human, via
Notion.

---

## What's DONE

- **Full loop runs green offline:** `python3 run.py "your idea"` walks one idea
  through Brain → Studio → Mission to `ad_live` (or `analyzed` if not a winner).
- **Brain (ours):** skills (`content-os` Brick chain, `writing-style`,
  `positioning-angles`, `hook-library`, `story-structures`), the
  `/ai-cmo-generate` command, `engine/brain/generate.py` (deterministic, grounded
  in the client's 6-layer context, no key needed), `voc.py`. Reject/QC-fail folds
  the feedback note into the re-draft.
- **Studio (merged):** real Playwright render (`engine/studio/render.py`) + Claude
  vision brand QC (`engine/studio/brand_qc.py`). Falls back to stub-pass with no
  ANTHROPIC key so the loop always runs.
- **Mission/Ads (merged):** `engine/mission/driver.py`, `gate.py`, `schedule.py`,
  `publish.py`, `analytics.py`, `engine/ads/ads_agent.py` (winner score + spend
  gate + push to ad_live).
- **Notion (ours), matches the full product build:**
  - per-client **guest seat** = own page + own Content Pipeline DB + own Metrics DB
    (`notion_provision.provision_client(slug, kpis)`),
  - full schema incl. paid-loop fields (Follows, Winner, Ad Status, Ad Budget,
    Ad Audience) + seam fields (Platform, Creative Type, CTR, ROAS, QC Verdict),
  - **both gates read back** (content via `Status`, ad-spend via `Ad Status`),
  - dashboard Metrics (honesty gate: un-wired values marked `Is Mock`),
  - page layout (intro + KPI tiles + section headings).
- **Live on Shannon's Notion:** Lumen Skin guest seat is provisioned; the board
  currently shows a content-gate card (In Review) and an ad-spend-gate card
  (Winner, 140 follows, Ad Status Recommended, $50).
- **QA:** passed twice; reject-loop tests + mission tests pass (16/20; the 4 fails
  are only `flask` not installed in the sandbox).

---

## The functions the cron will call (the building blocks)

All in `engine/dashboard/`:
- `notion_provision.provision_client(slug, kpis)` — create a client's seat.
- `notion_provision.ensure_schema(slug)` — sync DB schema (idempotent).
- `notion_sync.push(client)` — pipeline → Notion board.
- `notion_sync.pull_gate(client)` — read human decisions:
  content Approved → advance; Rejected/Needs revision → re-draft loop;
  Ad Status Approved → `ad_approved`; Declined → drop. Then pushes states back.
- `notion_sync.pull_intake(client)` — client "Idea" rows → new `captured` posts.
- `notion_sync.push_metrics(client)` — refresh dashboard KPIs.
- `notion_layout.build_page_layout(client)` — one-time page layout.

The stations (called by `run.py`): `engine.brain.generate.run(post_id)`,
`engine.studio.render.run`, `engine.studio.brand_qc.run`, then Mission's
`driver`/`gate`/`publish`/`analytics`/`ads`.

Mode: real Notion when `NOTION_TOKEN` is set, otherwise an offline JSON board.

---

## What the local cron needs to do (the open work)

A scheduled loop, per client. Suggested cycle (use **launchd** on the Mac since no
VPS, or `crontab`):

1. `pull_intake(client)` — pick up new ideas the client typed in Notion.
2. **Sweep `captured` posts** through Brain → Studio (draft → render → QC) to
   `qc_review`, then `push(client)` so they appear **In Review** for the human.
   *(This sweep does NOT exist yet — `run.py` only runs the Brain once on a fresh
   post. The reject path auto-reprocesses inside `pull_gate`, but intake-created
   `captured` posts need the cron to process them. This is the main new piece.)*
3. `pull_gate(client)` — apply the human's content + ad-spend decisions.
4. For `approved` posts: run Mission (`driver`) → schedule → publish → analytics →
   ads-recommend → `push(client)`.
5. `push_metrics(client)` — refresh the dashboard.

Cadence idea: intake + sweep + pull every few minutes; metrics + analytics daily.

---

## OPEN items / gotchas (read before building cron)

1. **No captured-sweep yet** — the cron must add it (item 2 above). It's the
   single most important new piece for autonomy.
2. **ANTHROPIC_API_KEY not picked up** — Shannon's key is not in `.env` under that
   exact name, so Brain's real command + Studio QC ran in stub mode. Rename to
   exactly `ANTHROPIC_API_KEY` to enable real Claude. (Engine `generate.py` is
   deterministic offline; the real Claude-written draft comes from the
   `/ai-cmo-generate` command run in Claude Code.)
3. **Stub vs real state clash** — running ANY stub command (no `NOTION_TOKEN`)
   overwrites `data/notion_state.json` with stub ids, which then points real
   commands at stub ids. Keep stub testing and real runs separate, or restore the
   real ids (below). Worth splitting into two state files as a hardening pass.
4. **Reconcile merge leftovers** — Studio added a *second* `scripts/notion_sync.py`
   (canonical is `engine/dashboard/notion_sync.py`), plus `run_demo.py` (vs `run.py`)
   and `engine/brain/generate_mock.py` (vs `generate.py`). Pick canonical, delete
   the rest, so the cron has one clear entry point.
5. **Manual Notion views** — board (group by Status) + calendar (Scheduled For) are
   a 2-min UI step: `docs/notion-views-manual.md`.
6. **human_note collision (latent)** — the comment + Mission status messages share
   the `human_note` column. Safe today; give the steering comment its own field if
   the loop gets busier.
7. **4 mission tests fail = `flask` not installed** (env only, not a code bug).

---

## Key facts the cron session needs

- **Run:** `python3 run.py "idea"` · dev gate page: `python3 engine/mission/gate.py`
- **Tests:** `python3 -m pytest tests/` (mission + notion)
- **Statuses:** see pipeline above (`db.Status.*`).
- **.env keys:** `NOTION_TOKEN` (set, works) · `ANTHROPIC_API_KEY` (needs correct
  name) · `ZERNIO_API_KEY`, `META_ADS_TOKEN` (for live publish/ads) ·
  `NOTION_PARENT_PAGE_ID` (optional; auto-discovered).
- **Live Notion ids (lumen-skin):** these are ids, not secrets —
  - parent page: `386861da-2aae-8069-8d67-d794281b8fe7`
  - client page: `386861da-2aae-81f7-8543-d7a3978e5a11`
  - pipeline DB: `386861da-2aae-81ac-b040-dd0f1facdb42`
  - metrics DB:  `386861da-2aae-813d-a00b-f7794e44cd2c`
  - (held in `data/notion_state.json`, which is gitignored)
- **Reference docs in repo:** `docs/superpowers/specs/2026-06-20-notion-database-design.md`
  (Notion spec), `docs/notion-system-mockup.html` (the approved design),
  `docs/qa/notion-v2-merge-review.md` (latest QA), `docs/notion-views-manual.md`,
  `HANDOFF-GUIDE` (Card 3 builder's 10-stage org-to-paid guide).
