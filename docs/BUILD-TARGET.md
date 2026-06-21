# AI CMO, full build target

This is the whole system the AI CMO is being built toward, transcribed from the
architecture map across its six sections. It exists because the README documents
the four-station loop and the two pieces our team built (Brain + Notion), but the
full platform is much larger. This doc is the map of everything, so no builder
assumes a section is done when it is still a stub or absent.

For the env vars every section needs, see `.env.example`. For the named-tool
audit (which external service each station reads, and its real status), see
`docs/qa/reference-architecture.md`.

## Status legend

- **BUILT** real and working in this repo today
- **PARTIAL** partly present in this repo
- **STUB** a deterministic placeholder that returns canned data
- **NOT BUILT** absent from this repo (named in the architecture only)

A "ref: complete" note means a reference implementation already exists in the
sibling repo `aicmo-complete` that this repo can learn from.

## Automation scorecard (the target)

- Production loop (render, score, publish, track): about 95 percent automated. The only human decision is approve or reject at `qc_review`.
- Reasoning and drafting (`/develop` plus the Brick chain): about 60 percent automated. Two STOP-and-confirm gates.
- Analytics, SEO, GEO, dashboards: about 90 percent automated. Cron-driven. Only the Data Jumbo embed is manual.

---

## 1. Overview, multi-repo architecture

The system spans three repos plus a client VPS. This repo (`aicmo-core`) is the
public engine.

| Component | Status | Note |
|---|---|---|
| ZeroArc AIOS (private, source of truth) | NOT BUILT (here) | Upstream private repo. Out of scope for this repo. |
| zeroarc-aicmo-core (public engine) | BUILT (this repo) | De-cliented, human-gate + RCA guard. Genesis 2026-06-12. |
| Client VPS (Hostinger, ZeroArc-operated) | NOT BUILT | `aicmo-core/` clone, git pull nightly, never hand-edit. |
| `{client}-data/` private 6-layer context + brands.json | PARTIAL | `client-data/lumen-skin/` exists as the demo. brands.json not present. |
| `{client}-context-ref` raw source (brand decks, audits, never deployed) | NOT BUILT | Private raw-source store. |
| `sync_aicmo_core.py` + nightly git pull | NOT BUILT | The sync seam from engine to client VPS. |

---

## 2. Onboarding, VPS setup, 6-layer context, migration

| Component | Status | Note |
|---|---|---|
| A. Client VPS setup (Hostinger KVM2, Ubuntu 24.04): sudo user + SSH key, scoped GitHub deploy key, clone + Cursor, harden ufw/fail2ban/lock SSH | NOT BUILT | Runbook only. ".env, cron, app, systemd" explicitly not yet. |
| B. 6-layer context: Positioning, Brand & Audience (ICP), Strategy, Offers & Funnels, Voice, Guardrails | BUILT | Present per client in `client-data/`. The Brain reads all six. |
| B. visual-brand.md + brand.css | PARTIAL | Present for lumen-skin. |
| B. Output: commit + mirror to Notion per layer | NOT BUILT | |
| B. Lock: brand-test picks pipeline + type | NOT BUILT | |
| C. Migration (Zool): snapshot crontab/systemd, clone Core + data (`link_client_data.sh`), fill brands.json + .env preflight, dedicated Notion Pipeline DB, cutover deny/allow-list, audit-bot systemd handover, 7-day grace + archive secrets | NOT BUILT | Per-client migration playbook. |
| C. Per-client gen routing, client DB idles | NOT BUILT | Flagged NOT BUILT in the architecture itself. |

---

## 3. Content Engine, /capture to /develop (Brick chain) to /schedule

| Component | Status | Note |
|---|---|---|
| `/capture` (stub idea into content.db) | PARTIAL | Idea capture exists via `engine/save_draft.py` and the loop seed. |
| Brick chain (5-phase, each LOCKS one artifact): 0 Intake (surface + brand), 1 Topic + pillar, 2 Angle + archetype, 3 Hook (2-3 + 1), 4 Story/Shift (outline + 1 shift) | BUILT | The Brain. Lives in `.claude/skills/content-os` + `engine/brain/`. |
| `/develop` back half (~60% automated, two STOP gates): Stage 0 Intelligence, Stage 1 Positioning STOP, Stage 2a Caption STOP, Stage 2b Visual + sec4, Stage 3 Status=drafted | NOT BUILT | Core has `/ai-cmo-generate` only, not the staged `/develop`. |
| Voice / pattern libraries: strategy.md, voice-os.md, angle-library.md, hook-library.md, story-structures.md | PARTIAL | Present as skills (`positioning-angles`, `hook-library`, `story-structures`, `writing-style`). |
| `seo_guardrails.py` (8 checks + 21 banned + 10-pt) | NOT BUILT | |
| Flywheel: `/ingest` raw context, mine PATTERNS only into libraries | NOT BUILT | |
| `/schedule` (cadence gaps, interactive, never auto) | NOT BUILT | |
| Persona agents: Strategist (Jess), Architect (Max), Copywriter (Creative), Creative (Clara), Strategy (Maya) | NOT BUILT | Named in the map. |
| Persona agent: Ads | NOT BUILT | Flagged NOT BUILT in the architecture itself. |

---

## 4. Render and Placid, how images are made and QC'd

| Component | Status | Note |
|---|---|---|
| Render input: visual-brand.md + brand.css, `templates/social/*.html.j2` | PARTIAL | Template present; render does not consume it yet. |
| `social_render.py` (Playwright, 1080x1350 @2x) | STUB | `engine/studio/render.py` sets the path, produces no file. ref: complete |
| `brand_qc.py` (Claude Sonnet 4.6 vision, pass/borderline/fail) | STUB | `engine/studio/brand_qc.py` hardcodes a passing score. ref: complete |
| Output: PNG + Notion image (`aicmo_page_body.py`) | NOT BUILT | |
| Render routing (`config/templates.json`, locked via brand-test): claude_html DEFAULT (~$0.001 + $0.012), gemini_direct optional, placid_composite BUILT-but-DEFERRED | NOT BUILT | ref: complete has Placid + Gemini + Playwright backends. |
| Placid setup: build template, fields (image/headline/subhead/cta/wordmark), record UUID + slots, aspect ratios (1080x1350 canonical), `placid_client.py` drives API, live cmd `/placid-visual` | NOT BUILT | ref: complete (`engine/integrations/placid.py`) |

---

## 5. Orchestrator state machine + Distribution (target ~95% automated)

| Component | Status | Note |
|---|---|---|
| State machine: captured to drafted to qc_review to approved (HUMAN GATE) to scheduled to published to analyzed (future) | BUILT | `run.py` walks the pipeline. `db.py` is the frozen contract. |
| Hard constraint: no script ever promotes a row to approved; a QC pass score is NOT approval | BUILT | Enforced by the human gate. |
| Off-ramps: needs_revision + Feedback, rejected (dead end), compliance_review (clinical), publish_error | PARTIAL | needs_revision and rejected exist; compliance_review and publish_error not modeled. |
| `ai_cmo_regenerate.py` (NOT on cron, manual) | NOT BUILT | |
| Zernio API single publish layer | STUB | `engine/mission/publish.py` writes a fake URL. ref: complete (`engine/mission/zernio.py`) |
| Distribution schedules: LinkedIn company (07/12/20 wkdays), LinkedIn jen-personal (Mon/Wed 09:00), Instagram (08/12, 30/20), 30-min buffer, 14-day lookahead | NOT BUILT | `engine/mission/schedule.py` is basic. |
| `collect_zernio_analytics.py` (19:00) | STUB | `engine/mission/analytics.py` returns mock metrics. |
| `engagement_sync.py` (19:30 to Notion) | NOT BUILT | ref: complete (`engine/mission/engagement_sync.py`) |

---

## 6. Analytics, SEO, GEO, Client Dashboard (target ~90% automated)

This entire section is absent from this repo today.

| Component | Status | Note |
|---|---|---|
| External sources: GA4 (prop 526918509), Google Search Console, DataForSEO (ranks + AIO), ChatGPT/Claude/Perplexity AIO, Stripe (MRR) | NOT BUILT | ref: complete has DataForSEO + AEO/AIO. |
| DataOS `collect.py` (06:00 daily): `collect_ga` (06:00, OAuth2), `collect_gsc` (06:15), `collect_geo` (Mon 07:45, cap $5), `collect_stripe` (+ auto), `data/data.db`, `generate_metrics.py` + key-metrics.md (`/prime`) | NOT BUILT | ref: complete has `intelligence` + `aeo`. |
| Reporting (Monday crons): `weekly_brief.py` (08:00, to Notion Briefs DB + Gemini narrative), `portfolio_digest.py` (08:00, to Telegram), `weekly_report.py` (08:15, HTML/brand), weekly Notion report (narrative + 6 charts) | NOT BUILT | ref: complete has `dashboard/report.py` + `metrics.py`. |
| AI CMO Client Dashboard (`/dashboard-setup {slug}`): Phase 0 `dashboard_preflight.py` (readiness gate, no empty tiles), Phase 1 `notion_metrics_push.py` (daily 06:30, Metrics DB), Phase 2 `notion_dashboard.py` (scaffold page), Phase 3 Data Jumbo + pipeline (MANUAL, Notion UI) | NOT BUILT | "Zool blocked at Phase 0 (no GSC/Zernio/GEO)." |
| `dashboard_metrics.py` (shared defs + 4-day freshness) | NOT BUILT | Honesty gate: tiles with no live data are withheld, never faked. |

---

## How to use this doc

1. Find your station or section above.
2. Anything marked STUB or NOT BUILT is open work. Anything BUILT is done and should not be re-touched without the contract conversation.
3. Set only the env vars your section reads (see `.env.example`). Vars marked [NOT WIRED YET] there are the seam you add when you wire the real path.
4. When you move a component from STUB to BUILT, update its row here and re-run the source-reconciliation auditor (`docs/qa/README.md`).
