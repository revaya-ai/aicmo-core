# Notion Database — Design Spec

> Status: approved (Shannon, 2026-06-20). Our deliverable alongside Card 1 (Brain). Built in aicmo-core.
> Source: Jen's client-workspace screenshots ("(Client) — AI CMO") + the frozen db.py contract.

---

## Purpose

Give the AI CMO a real Notion surface: the client sees their content pipeline in Notion and approves or rejects each post from their phone. This is Jen's actual selling point ("approve in your real Notion"), and it is the missing piece. SQLite (db.py) stays the engine's source of truth. Notion is the human gate.

## Spine model

SQLite is authoritative. Notion is the human-facing mirror plus a read-back of the one human decision:
1. Push: posts at `qc_review` appear in Notion as cards, Status "In Review".
2. Approve: the client flips Status to "Approved" or "Rejected" in Notion.
3. Read back: a sync reads Notion, finds the decisions, and advances the SQLite record (approved -> `approved`, rejected -> `rejected` with the human note).

Everything runs offline in STUB mode (JSON file) when no `NOTION_TOKEN` is set, and switches to the real Notion API when the token is present. The pipeline never hard-depends on Notion being up.

## The database (MVP: Content Pipeline)

One Notion database, "Content Pipeline", matching Jen's screenshot. Properties and their source in our `posts` record:

| Notion property | Notion type | From posts |
|---|---|---|
| Title | title | derived from hook |
| Post ID | rich_text | id (maps the card back to SQLite) |
| Client | select | client |
| Status | select | status, mapped (see below) |
| Pillar | select | pillar |
| Hook | rich_text | hook |
| Draft Caption | rich_text | body |
| Brand QC Score | number | qc_score |
| Brand QC Notes | rich_text | qc_notes |
| Composite Image | url | image_path |
| Aspect Ratio | select | (default 1080x1350) |
| Hashtags | rich_text | (optional) |
| Folder Path | rich_text | (optional) |
| Scheduled For | date | scheduled_for |
| Published URL | url | published_url |

Status value mapping (SQLite -> Notion label):
`drafted`->Draft, `qc_review`->In Review, `approved`->Approved, `rejected`->Rejected, `needs_revision`->Needs revision, `scheduled`->Scheduled, `published`->Published, `analyzed`->Analyzed.
Read-back mapping (Notion label the human sets -> SQLite advance): Approved->`approved`, Rejected->`rejected`, Needs revision->`needs_revision`.

## Components (built in aicmo-core)

1. `engine/dashboard/notion_client.py` — thin Notion API wrapper. Reads `NOTION_TOKEN`. `is_configured()` is true only when a token is set. All HTTP isolated here.
2. `engine/dashboard/notion_provision.py` — creates the Content Pipeline database under a parent page (`NOTION_PARENT_PAGE_ID`) with the full property schema. Idempotent: records the created database id to `data/notion_state.json` and reuses it. STUB mode prints the schema it would create and writes the state file with a stub id.
3. `engine/dashboard/notion_sync.py` — `push()` upserts pipeline posts as Notion pages (create if no mapped page, else update), keyed by Post ID. `pull_gate()` reads the database, finds rows whose human-set Status is Approved/Rejected/Needs revision, and advances the matching SQLite record. STUB mode reads/writes `outputs/notion-mirror.json` so the flow is testable offline.

(The existing `engine/dashboard/notion_mirror.py` JSON board is the starting point for the stub; notion_sync supersedes it with create/update + read-back.)

## Contract additions

The Notion property schema above is the "Notion contract". The page-id mapping (Post ID -> Notion page id) lives in `data/notion_state.json`, gitignored. No change to `db.py`.

## Error handling

- No `NOTION_TOKEN`: run in STUB mode, never touch the network, label output "stub" so no false success.
- Token set but `NOTION_PARENT_PAGE_ID` missing on provision: fail loud with the exact missing env var.
- API error on push/pull: surface it, do not silently swallow; the SQLite record is unchanged so a retry is safe.

## Verification (definition of done)

STUB mode (no token), end to end:
1. Run the loop so posts exist; run `notion_provision.py` -> writes `data/notion_state.json` with a stub database id and prints the schema.
2. `notion_sync.py push` -> writes `outputs/notion-mirror.json` containing a card per pipeline post with the mapped Status labels.
3. Simulate a human approval in the stub board (flip a card to Approved), run `notion_sync.py pull` -> the matching SQLite post advances to `approved`.
4. Real mode is exercised only when `NOTION_TOKEN` + `NOTION_PARENT_PAGE_ID` are set; same card shape, no downstream change.

## Prerequisite for the live demo

A Notion internal integration token (`NOTION_TOKEN`) and a parent page shared with the integration (`NOTION_PARENT_PAGE_ID`). Not needed to build or test in stub mode.
