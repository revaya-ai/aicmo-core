# QA Gap Report — Notion System Design (AI CMO)

> Auditor: QA manager (read-only design audit, no files changed)
> Date: 2026-06-21
> Scope audited: `docs/notion-system-mockup.html`, `docs/superpowers/specs/2026-06-20-notion-database-design.md`, `engine/dashboard/notion_schema.py`, `notion_sync.py`, `notion_provision.py`, `README.md`, plus the frozen `db.py` contract.
> Source legend: A = Jen's AI CMO, B = full system map, C = team build transcript.

---

## 1. VERDICT

**Sound thesis, faithful at the spine, but the build does NOT match its own design on two load-bearing points: per-client isolation and the reject-with-comment loop.** The mockup HTML describes a richer, correct system; the spec and code (`notion_schema.py`, `notion_sync.py`, `notion_provision.py`) implement a thinner one that drops fields the contract already carries, provisions one shared database instead of per-client databases, and never captures the client's comment on reject. Ship-blocking gaps are fixable without touching `db.py`.

---

## 2. GAPS

### G1 — Client comment on REJECT is never captured (BLOCKER, source A/C)
The entire thesis is "reject sends the post back to the Brain **with their comment as the instruction**" (mockup), "REJECT → back to the beginning … clients approve / COMMENT / reject" (C), "human edits/rejects → captured as a note → next draft lands closer" (A). But:
- `notion_schema.PROPERTIES` has **no comment / feedback / steering-note property at all**. The only client-writable field is `Status`.
- `notion_sync.pull_gate()` reads only the `Status` select. On reject it writes a hardcoded string: `fields["human_note"] = "Rejected in Notion"` — it never reads what the client actually wrote.
- `db.py` already has a `human_note` column ready to receive it. The pipe is just not connected.

**Fix:** Add a `Client Comment` (rich_text) property to `PROPERTIES`. In `pull_gate()`, read that property via `_plain_text(props.get("Client Comment"))` and pass it as `human_note` on reject **and** on `needs_revision`. The stub `card_for` needs a matching `client_comment` field so the offline flow exercises it.

### G2 — Design says per-client database; code provisions ONE shared database (BLOCKER, source A/design line)
Mockup + your one-line design: "each client has their OWN full Content Pipeline database … No client can ever see another … provisioned from one template: page + database + dashboard." Source A: per-client isolation, "they never mix," a guard blocks leaks. But:
- `notion_provision.provision()` creates a single database titled `"Content Pipeline"` under one `NOTION_PARENT_PAGE_ID`, stores one `database_id` in `data/notion_state.json`, and is idempotent on that single id.
- `notion_sync.push()` pushes **all** posts (`_all_posts()` across every status) into that one database, distinguished only by a `Client` select column.

A `Client` select on shared rows is the opposite of isolation — every client on that guest seat sees every other client's cards. This contradicts the design AND source A's hard isolation rule.

**Fix:** `provision(client_slug)` must take a client, create a per-client database (and ideally under a per-client parent page = the guest seat), and key state by client: `state["clients"][slug]["database_id"]` + per-client `page_map`. `push(client)` / `pull_gate(client)` must scope to that client's posts and database. Until then the spec's "MVP: one database" line is a known fidelity debt, not a finished design — flag it explicitly in the spec.

### G3 — Contract fields the mockup promises are absent from the schema (IMPORTANT, source C + db.py)
The mockup "The contract — Notion is the hub" table names fields each builder writes. `db.py` already carries them. `notion_schema.PROPERTIES` drops several, so the seams the design is built around have no Notion column to land in:

| Field (mockup contract / db.py) | In db.py? | In PROPERTIES? |
|---|---|---|
| `angle` | yes | **missing** |
| `platform` | yes (default linkedin) | **missing** (mockup card shows "Platform Instagram") |
| Client comment / feedback | `human_note` exists | **missing** (see G1) |
| `ad_budget` / `ad_audience` / `ad_status` (Ads seam: CTR, ROAS, Creative Type, Owner) | yes | **missing** |
| `metrics_json` (drives the KPI dashboard) | yes | **missing** |

If the seam fields aren't in the schema, the "other builders write into the same card" promise (mockup, C) cannot hold — there is nowhere for Studio/Mission/Ads to write. At minimum add `Angle`, `Platform`, and the Ads/performance fields as documented seam columns now (empty until those stations land), exactly as the mockup says ("These fields exist in the schema now so the other builders' stations write into the same cards").

### G4 — No QC verdict field; only a numeric score (IMPORTANT, source A/B)
Source A/B: the vision gate scores every render **pass / borderline / fail** and off-brand never reaches the queue. The schema has `Brand QC Score` (number) + `Brand QC Notes` only — no categorical verdict. A number alone can't express "borderline," and there is no field that records the pass/fail decision the human-queue gating depends on.

**Fix:** Add `Brand QC Verdict` (select: Pass / Borderline / Fail). `db.py` has no column for it, so either derive it from score thresholds at push time (no contract change) or raise a contract change with the builders. Document which.

### G5 — Resizing / format QC (organic vs paid) not represented (IMPORTANT, source C)
C: "organic vs paid need different dimensions per platform; the QC step should verify the correct size/format for organic AND for paid." Schema has a single `Aspect Ratio` select defaulting to 1080x1350. There is no field distinguishing organic vs paid renders or recording a size/format check result.

**Fix:** This is a Studio/Ads seam, fine to defer the *enforcement*, but add the seam columns now: `Format Check` (select: organic-ok / paid-ok / wrong-size) or per-variant aspect ratios, so the resize-QC result has a home. Note it as a seam in the spec.

### G6 — KPI / Metrics database and the other client databases are designed but not provisioned (IMPORTANT, source A + design)
The design ("their OWN KPI dashboard") and mockup section 6 describe a per-client Metrics table + dashboard with a standard KPI menu, plus Jen's full workspace (A): Reports, Brand & Voice, Onboarding & Intake, Requests. `notion_provision.py` provisions **only** the Content Pipeline database. The mockup itself scopes the dashboard as "Built now: structure + KPI selection + a Metrics table per client." None of that exists in `provision()`.

**Fix:** Extend `provision()` to also create a per-client `Metrics` database (the KPI menu as rows/props) and the `Brand & Voice` + `Requests` pages, since the design says these are built now. Reports / Onboarding can stay seams. Right now the spec's "MVP: Content Pipeline" silently drops the dashboard the one-line design promises — reconcile the two documents.

### G7 — Honesty gate on un-backed dashboard tiles is not encoded (IMPORTANT, source B/C)
B HONESTY GATE: "tiles with no live data are withheld, never faked." C: "mock/dummy data is fine for the demo but must be marked as mock, never presented as real." The mockup dashboard shows hard numbers (Followers 4,210, etc.) with **no mock label and no withhold rule**. Nothing in schema or provisioning marks a tile as mock or withholds an unwired tile.

**Fix:** Add a "demo data" marker to any tile fed by a not-yet-wired seam, and a rule that a metric with no live source renders empty/withheld, not zero or invented. Bake this into the dashboard provisioning, not just convention.

### G8 — Composite Image property type mismatch (NICE-TO-HAVE, internal consistency)
The spec's property table lists `Composite Image | url`, but `notion_schema.PROPERTIES` defines it as `rich_text` and `properties_for()` writes it as rich_text holding `image_path`. Jen's real Notion uses a file/image-style field so the render is visible on the card (mockup shows the composite inline). A rich_text path string won't render the image.

**Fix:** Decide: `files` (upload/URL the client can see) vs `url` vs `rich_text`. Align the spec table, `PROPERTIES`, and `properties_for()`. The mockup's whole "client sees the post and the on-brand image and makes one decision" UX depends on the image actually displaying.

### G9 — README has no "What our team built" section to audit (NICE-TO-HAVE, process)
The audit brief points at a README "What our team built" section. The README headers are: Who this is for, contract-first rule, status pipeline, 4 stations, run the loop, Brain command, full architecture, going real, QA, Layout. **No such section exists.** The README is internally consistent but doesn't narrate the Notion client surface for a reader. Minor, but if the brief expects it, add it.

---

## 3. CORRECTLY DEFERRED (genuine seams — do not over-build)

- **Studio render + brand_qc internals** (image generation, vision pass). Schema reserves Composite Image / Brand QC fields; Studio fills them. Correct.
- **Mission distribution** (Zernio publish, schedule buffer, publish-check, analytics pull). `Scheduled For` / `Published URL` columns reserve the seam. Correct.
- **Ads / paid loop** (top performers → Meta, spend gate). Defined as theoretical for the hackathon. Correct to defer execution — but the *fields* must exist now (see G3).
- **Live data wiring for the dashboard** (GA4 / GSC / Stripe / Data Jumbo chart embeds). Structure now, integrations later — correct, provided the honesty gate (G7) is in place.
- **STUB-mode JSON board** as the offline stand-in for Notion. Sound, keeps the pipeline from hard-depending on Notion being up. Correct.
- **Reports / Onboarding & Intake databases** as later seams. Acceptable to defer (but Metrics + Brand & Voice + Requests are in the "built now" design — see G6).

---

## 4. RISKS / CONTRADICTIONS (hard-rule checks)

- **HARD CONSTRAINT — "a QC pass is NOT approval, no script ever promotes a row to approved" (B): PASS.** `notion_sync` only advances on a human-set Status (`STATUS_NOTION_TO_SQLITE_GATE` = Approved/Rejected/Needs revision), and `_advance_if_pending` only acts on posts still at `qc_review`. The QC score never promotes. Confirmed safe — preserve this in any refactor.
- **PER-CLIENT ISOLATION (A): FAIL.** One shared database keyed by a `Client` select is not isolation (G2). This is the most serious fidelity break — it directly violates source A's "they never mix" and your own "No client can ever see another."
- **HONESTY GATE (B/C): NOT ENFORCED.** Dashboard shows real-looking numbers with no mock marker / withhold rule (G7). Risk: presenting invented data as real in the demo.
- **FEEDBACK LOOP (A): BROKEN.** Reject writes a hardcoded note, not the client's words (G1). The "next draft lands closer / edits-per-post trend down" loop cannot work without the real comment flowing to the Brain.
- **Idempotency / retry-safety: PASS.** Push upserts by Post ID via `page_map`; pull is guarded by status; API errors leave SQLite unchanged. Good.

---

## 5. TOP 5 TO FIX BEFORE BUILDING (ranked)

1. **Capture the client comment on reject/needs-revision (G1).** Add a `Client Comment` property, read it in `pull_gate()`, pass it as `human_note`. Without this the core thesis does not function. No `db.py` change needed.
2. **Make provisioning + sync per-client (G2).** `provision(client)` → per-client database under the client's guest-shared page; scope `push`/`pull_gate` by client. Restores isolation, the design's headline claim.
3. **Add the seam fields the contract already promises (G3).** `Angle`, `Platform`, and the Ads/performance + `metrics_json` columns, so Studio/Mission/Ads have somewhere to write. Reconcile spec table ↔ `PROPERTIES`.
4. **Add `Brand QC Verdict` (Pass/Borderline/Fail) (G4)** and the organic/paid format-check seam (G5), so the vision gate's actual decision and the resize check have a home.
5. **Provision the Metrics/dashboard (+ Brand & Voice, Requests) the design says are built now, with the honesty gate baked in (G6 + G7).** Un-wired tiles render empty or marked "demo," never faked. Reconcile "MVP: one database" in the spec with the one-line design that promises a per-client dashboard.
