# Notion views — the 2-minute manual finish

The provisioning script builds the databases, the dashboard tiles, and the
section headings automatically. Two things the Notion API cannot reliably create
are **board** and **calendar** views, so finish those by hand once per client.
Open the "Lumen Skin Studio — AI CMO" page first.

## 1. Board view (the pipeline kanban)

1. On the **Content Pipeline** database, click the view name at its top-left (it
   says **Table**), then **+ New view** (or the small dropdown next to the view).
2. Choose **Board**.
3. Open the board's **•••** (or the layout settings) → **Group by** → select
   **Status**.
4. Name the view **Board**.

You now get columns: Idea · Draft · In Review · Approved · Rejected · Scheduled ·
Published, matching the mockup. Drag the **Board** view to be the default (left-most).

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
