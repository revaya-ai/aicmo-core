# Notion Database — Design Spec (v2, post-QA)

> Status: approved direction (Shannon, 2026-06-21). Supersedes the v1 "MVP one database" framing.
> Our deliverable alongside Card 1 (Brain). Built in aicmo-core. Source: Jen's setup + our build transcript + the QA gap report (docs/qa/notion-design-review.md).

---

## Purpose

Notion is the per-client client surface AND the hub that connects every builder. The client reviews, comments, approves, and rejects here. SQLite (db.py) stays the engine's source of truth; Notion mirrors both ways.

## Spine model

SQLite authoritative. Notion is the human surface plus a read-back of the human decision and the client's comment. Offline STUB mode (JSON) when no token; real Notion API when `NOTION_TOKEN` is set. The pipeline never hard-depends on Notion.

## Architecture: one guest seat per client (full isolation)

Each client gets their **own** client page under the HQ parent, guest-shared to them. Inside it:
- their **own** Content Pipeline database (same schema for everyone),
- their **own** Metrics database (the dashboard data),
- a Brand & Voice page and a Requests area.

No shared database. No client can see another (Jen's "they never mix"). State is client-keyed:

```
data/notion_state.json = {
  "parent_page_id": "...",
  "clients": {
    "lumen-skin": {"page_id","pipeline_db_id","metrics_db_id","page_map":{post_id:notion_page_id},"kpis":[...]}
  }
}
```

## The one rule: approve forward, everything else goes back to the Brain

- **Approve** -> the card moves forward (scheduled/publish, owned by Mission).
- **Comment** -> the client's note is captured as the steering feedback.
- **Reject** -> status returns to `captured`, the client's comment is stored in `human_note`, the Brain re-runs and folds the note into the next draft.
- **QC fail** (Studio's vision gate returns fail/borderline) -> identical path: back to `captured`, the QC reason stored in `human_note`, Brain re-drafts. Same `send_back_to_brain(post_id, feedback)` helper as reject.

Off-brand or rejected work never sits; it loops back and the next draft lands closer. This is the feedback loop.

HARD CONSTRAINT (unchanged, verified by QA): no script ever sets a card to `approved`. Only a human-set Status in Notion advances a card, and only from `qc_review`. A QC pass score is not approval.

## Content Pipeline schema (the cross-builder contract)

Every field exists now so the other builders' stations write into the same card. We fill the Brain fields; the rest are defined seams.

| Notion property | Type | From posts | Written by |
|---|---|---|---|
| Title | title | derived from hook | Brain |
| Post ID | rich_text | id | Brain |
| Client | select | client | Brain |
| Status | select | status (mapped) | Brain sets In Review; **Client** advances |
| Pillar | select | pillar | Brain |
| Angle | rich_text | angle | Brain |
| Hook | rich_text | hook | Brain |
| Draft Caption | rich_text | body | Brain |
| Client Comment | rich_text | human_note (read back) | **Client** -> read by us |
| Brand QC Score | number | qc_score | Studio (seam) |
| Brand QC Verdict | select | pass / borderline / fail | Studio (seam) |
| Composite Image | files (external url) | image_path | Studio (seam) |
| Aspect Ratio | select | platform format | Studio (seam) |
| Resize Check | select | organic / paid sizing ok | Studio (seam) |
| Creative Type | select | UGC / product / video / TV spot | Ads (seam) |
| Platform | select | linkedin / instagram / meta-ad | Mission/Ads (seam) |
| CTR | number | click-through rate | Ads (seam) |
| ROAS | number | return on ad spend | Ads (seam) |
| Hashtags | rich_text | - | Brain/Studio |
| Folder Path | rich_text | - | seam |
| Scheduled For | date | scheduled_for | Mission (seam) |
| Published URL | url | published_url | Mission (seam) |

Status options: Idea, Draft, In Review, Approved, Rejected, Scheduled, Published, Analyzed.
SQLite->Notion: captured/idea->Idea, drafted->Draft, qc_review->In Review, approved->Approved, scheduled->Scheduled, published->Published, analyzed->Analyzed.
Notion->SQLite (the gate read-back): Approved->approved, Rejected-> send back to Brain (captured + comment), Needs revision-> send back to Brain.

## Intake (section 3)

The client adds a row at Status "Idea" (their seed idea). `pull_intake(client)` reads new Idea rows and creates a captured post in SQLite; the Brain picks it up. Two-way surface.

## Dashboard (section 6)

A per-client Metrics database, rows chosen from a standard KPI menu at setup:
followers, engagement_rate, **website_visits, website_conversions**, top_landing_pages, posts_shipped, leads, seo_rank, aeo_citations, revenue_mrr, ctr, roas.

Each metric row: KPI, Value, Trend, Source (GA4/GSC/social/Stripe/Meta), **Is Mock**. 
HONESTY GATE: any value not backed by a live integration is marked `Is Mock = true` and labeled, never presented as real. Un-wired KPIs are withheld, not faked. (From section 6 + our transcript.)

Built now: the Metrics DB + KPI selection + a stub metrics push (marked mock). Seam: the real GA4/GSC/social/Stripe wiring and Data Jumbo charts.

## Components (built in aicmo-core)

- `engine/dashboard/kpi_menu.py` (new) — the standard KPI library.
- `engine/dashboard/notion_schema.py` — full property schema + status maps + payload builders.
- `engine/dashboard/notion_client.py` — API wrapper + `create_child_page`.
- `engine/dashboard/notion_provision.py` — `provision_client(slug, kpis)`: child page + pipeline DB + metrics DB; client-keyed state.
- `engine/dashboard/notion_sync.py` — `push(client)`, `pull_gate(client)` (reads Status + Client Comment; reject -> send back), `pull_intake(client)`, `push_metrics(client)`.
- `engine/feedback.py` (new) — `send_back_to_brain(post_id, feedback)`: status -> captured, store feedback in human_note. Used by reject AND by Studio's QC-fail.
- `engine/brain/generate.py` — on re-draft, if `human_note` is set, fold it in as the revision instruction.

## Image rendering

Composite Image is a Notion `files` property with an external URL so it renders inline. Local `renders/x.png` paths show as text until Studio provides a hosted URL (documented seam).

## Verification (definition of done)

STUB (no token):
1. `provision_client("lumen-skin", kpis)` -> writes client-keyed state with stub ids; prints the pipeline + metrics schema.
2. Generate a post to qc_review; `push("lumen-skin")` -> board JSON with the card at "In Review".
3. Set the stub card to "Rejected" + a comment -> `pull_gate("lumen-skin")` -> post returns to `captured` with the comment in `human_note`; re-running Brain produces a revised draft that references the note.
4. `push_metrics("lumen-skin")` -> metrics rows, mock ones marked.

REAL (token set): same calls hit Notion; per-client page + DBs created; card approve/reject round-trips.

## Prerequisite for live

`NOTION_TOKEN` + a parent page shared with the integration (`NOTION_PARENT_PAGE_ID`, or auto-discovered).
