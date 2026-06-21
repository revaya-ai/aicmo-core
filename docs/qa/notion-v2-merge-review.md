# QA Re-Audit — Notion v2 + Mission/Ads Merge Review (AI CMO)

Date: 2026-06-21. Read-only audit. Scope: verify prior findings closed in v2, and check the merge contract between Brain+Notion (our side) and Mission+Ads (theirs).

---

## 1. VERDICT

**v2 closed every prior finding, but the merge left the reject loop only half-wired: a rejected post resets to `captured` with its comment, and the Brain CAN fold that comment in — but no orchestrator ever re-runs the Brain on a `captured` post, so a rejected/QC-failed card silently stalls. One BLOCKER, fixable in a few lines.**

---

## 2. PRIOR FINDINGS

| Finding | Status | Evidence |
|---|---|---|
| B1 — Reject-with-comment loop not wired (no comment field; hardcoded note; client comment never read) | **CLOSED** (design + storage) / see B2 for the runtime gap | `notion_schema.py:27` `Client Comment` rich_text; `:69-70` APPROVE/SEND_BACK labels; `notion_sync.py:84-86` reject routes to `feedback.send_back_to_brain(post_id, comment)`; `feedback.py:18-21` stores comment in `human_note` at `captured`; `generate.py:166` reads `human_note` as feedback; `generate.py:131-137` folds it into the re-draft |
| B2 — Per-client isolation violated (one shared DB, Client column) | **CLOSED** | `notion_provision.py:68-97` `provision_client(slug)` creates a per-client page + own pipeline DB + own metrics DB; state client-keyed under `clients[slug]` (`:10-12`); `notion_sync._client_posts` (`:39-43`) scopes to one client; `push`/`pull_gate`/`push_metrics` all take `client` |
| I1 — Missing seam fields (Angle, Platform, Creative Type, CTR, ROAS) | **CLOSED** | `notion_schema.py:24,33-36` Angle, Creative Type, Platform, CTR, ROAS all present as typed seams |
| I2 — No Brand QC Verdict (pass/borderline/fail) | **CLOSED** | `notion_schema.py:29` `Brand QC Verdict` select `[pass, borderline, fail]` |
| I3 — No organic-vs-paid resize field | **CLOSED** | `notion_schema.py:31-32` `Aspect Ratio` + `Resize Check` select `[organic ok, paid ok, needs resize]` |
| I4 — No dashboard / Metrics provisioning | **CLOSED** | `notion_provision.py:87-89` creates per-client Metrics DB; `kpi_menu.py` KPI library; `notion_sync.push_metrics` (`:141+`) writes KPIs |
| I5 — No honesty gate (mock marking) | **CLOSED** | `notion_schema.py:49` `Is Mock` checkbox; `metric_properties(..., is_mock)` `:138-145`; `kpi_menu.py:27-33` MOCK_VALUES surfaced with is_mock until a live integration lands |
| I6 — Composite Image not rendering (rich_text path) | **CLOSED** | `notion_schema.py:30` now `files`; `properties_for` `:121-125` writes external-url file so it renders inline (text fallback for local paths is a documented seam) |

All eight prior items are closed in the schema/provisioning/sync code. The remaining problem is a runtime orchestration gap introduced by how the merged pipeline is driven (below), not a schema regression.

---

## 3. MERGE / INTEGRATION ISSUES

### BLOCKER — A rejected post never gets re-drafted; it stalls at `captured`
- **The loop:** reject → `feedback.send_back_to_brain` → `db.advance(post_id, CAPTURED, human_note=note)` (`feedback.py:21`). Correct so far.
- **The gap:** `brain.generate.run()` is the only thing that drafts, and it is called from exactly ONE place: `run.py:54` `_run_pre_gate(post_id)`, on a post `run.py:50` just created. `grep` for `generate.run` / callers of the Brain returns only that import (`who_calls_brain_run`). Nothing anywhere does `list_by_status(CAPTURED)` to pick rejected posts back up (`scan_for_loop` — no captured scan exists; the only `while True` is Notion pagination in `notion_client.py:94`).
- **The Flask gate** (`gate.py:237-240`) only drives FORWARD on Approve (`driver.drive`). On Reject/Revise it calls `db.advance(post_id, decision, ...)` with `decision` = `rejected` or `needs_revision` (`gate.py:230-237`) — it does NOT route through `feedback.send_back_to_brain` and does NOT re-invoke the Brain. So even the human gate's reject path lands a post at `rejected`/`needs_revision` and stops.
- **Net:** the re-draft capability is real (`generate.py:166` reads `human_note`; `:131-137` applies it) but is never triggered after a reject. The rejected card stalls. The "off-brand work never sits, it loops back" promise in the v2 spec is not true at runtime.
- **Fix (small):** add a re-draft entry point. Either (a) a `drive_brain()` that does `for p in list_by_status(Status.CAPTURED): generate.run(p["id"])` and call it from `run.py` and after every send-back, or (b) have `feedback.send_back_to_brain` (and the Notion `pull_gate` reject branch) immediately call `generate.run(post_id)` so the post returns to `drafted` with the note folded in. Also fix the **Flask gate reject/revise branch** to route through `send_back_to_brain` so the Flask door behaves like the Notion door.

### IMPORTANT — Two gates with inconsistent reject semantics (Notion vs Flask)
- **Approve:** consistent. Both gates advance `qc_review → approved` only on a human action. `notion_sync._apply_decision:81-83` and `gate.py decide:118-121`. `pull_gate` is idempotent — it only acts on posts still at `qc_review` (`notion_sync.py:79`), so no double-advance hazard even if both run.
- **Reject:** INCONSISTENT. Notion reject → `send_back_to_brain` → `captured` (loops). Flask reject → `rejected` / `needs_revision` (dead-ends, no Brain). Same button, two outcomes. Decide which gate is canonical (spec says Notion is the client-facing gate; Flask is the internal/demo gate) and make Flask's reject path match (route to `send_back_to_brain`).
- **Which is real:** the v2 spec names Notion as the client gate; `gate.py` is the internal Flask board used by `run.py`'s auto demo. State this explicitly so the demo doesn't show the dead-end Flask reject path.

### IMPORTANT (latent) — human_note is overwritten downstream; reuse for two purposes collides
- `human_note` carries the reject/QC comment for the Brain (`generate.py:166`). But it is also overwritten by: the auto gate `gate.py:34` (`"AUTO-APPROVED (demo loop)."`), the Flask gate `gate.py:237` (`"Human approved — ship it."`), and the Ads station `ads_agent.py:121` (stores the ad rationale). No collision in the happy forward path (the note is consumed at draft time, before approval). But the moment the re-draft loop is wired (the BLOCKER fix), order matters: re-run the Brain BEFORE any approve writes a new note, or move the steering comment to its own column (e.g. add a `revision_note` field) so an approval message can't poison the next re-draft. Flag now; cheap to design around.

### NICE — No test covers the reject→re-draft loop
- `tests/mission/` covers driver, gate routes, ads, schedule, publish, analytics, full_loop — all the FORWARD path. `grep` finds no test asserting a rejected post returns to `drafted` with the comment folded in. Because the loop doesn't actually close (BLOCKER), `test_full_loop` passing gives false confidence. Add a test: capture → draft → qc → reject(comment) → assert re-drafted and `angle/body` contains the feedback.

### Hard-constraint check — PASS
No script auto-promotes to `approved` without a human. `gate.run` with `auto_approve` is the demo-only door and fails loud otherwise (`gate.py:30-45`). `driver.drive` starts at `approved` and only walks forward to `scheduled/published/analyzed/ad_recommended` — it never sets `approved` (`driver.py:13-19`). `ads_agent` stops at `ad_recommended` and requires `approve_spend(..., approved_by=...)` for the second human gate (`gate.py:124-129`, `ads_agent.py`). Notion `pull_gate` only advances on a human-set `Approved` label (`notion_sync.py:81-83`). No competing orchestration: `run.py` (demo) and the Flask gate (human) both funnel through the single `driver.drive` conveyor — one pipeline, two doors, as designed.

---

## 4. TOP FIXES BEFORE THE DEMO (ranked)

1. **Wire the re-draft trigger (BLOCKER).** Make a reject actually re-run the Brain: call `generate.run(post_id)` from `send_back_to_brain` (or add a `captured` sweep). Without this, demoing a rejection shows a stalled card, not the feedback loop — the headline feature of the v2 spec.
2. **Unify the Flask reject path with the Notion one.** Route Flask reject/revise through `send_back_to_brain` so both gates loop instead of dead-ending. Document Notion as the client gate, Flask as internal.
3. **Separate the steering comment from the status-message human_note** (add `revision_note` or consume-before-overwrite ordering) so approval/ads messages can't contaminate the next re-draft once the loop is live.
4. **Add a reject→re-draft regression test** so the closed loop stays closed.
