# Notion views — the 2-minute manual finish

The provisioning script builds the databases, the dashboard tiles, and the
section headings automatically. Two things the Notion API cannot reliably create
are **board** and **calendar** views, so finish those by hand once per client.
Open the "Lumen Skin Studio — AI CMO" page first.

## 1. Board view grouped by STAGE (not Pillar)

The board defaults to grouping by **Pillar**. Switch it to **Status** (the stage):

1. On the **Content Pipeline** board, click the **•••** (top-right of the view) →
   **Group** → **Group by** → choose **Status**.
2. Turn on **Hide empty groups** (removes leftover legacy columns that have no
   cards).
3. Optional: open the **Status** property and delete any old options you don't
   want (Idea, Draft, In Review, Approved, Analyzed, Needs revision). The live
   stages are **Captured · For Review · Scheduled · Published · Rejected**.

You now get stage columns: **Captured → For Review → Scheduled → Published**
(+ Rejected). The client approves a **For Review** card by dragging it forward to
**Scheduled**; rejects by dragging it to **Rejected** (which loops it back to the
Brain to re-draft).

## 2. Calendar view (scheduled posts)

1. Same view switcher → **+ New view** → **Calendar**.
2. Set the calendar's date property to **Scheduled For**.
3. Name it **Calendar**.

Scheduled posts now show on their dates (with the post title + platform once
Mission fills those fields).

## 3. Optional polish

- **Dashboard tiles side by side:** drag one KPI callout to the right edge of
  another to snap them into columns (2-3 across) for a tile-grid look.
- **Metrics as cards:** on the Dashboard — Metrics database, add a **Gallery**
  view for a card layout instead of the table.
- **Order:** drag the intro callout + Dashboard section above the two databases
  if you want the dashboard at the very top of the page.

## Note for the team

`data/notion_state.json` holds each client's real page + database ids. Running a
STUB command (no NOTION_TOKEN) overwrites it with stub ids, which then points the
real commands at stub ids. Keep stub testing and real runs separate, or restore
the real ids before running against live Notion.
