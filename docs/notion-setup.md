# Notion setup — connect your workspace and build the database

You do not "share the workspace." You create an integration (a key), share one
page with it, and put two values in `.env`. Then a script builds the database.

Five steps, about 5 minutes.

## 1. Create the integration (gives you NOTION_TOKEN)

1. Go to https://www.notion.so/my-integrations
2. Click **New integration**.
3. Name it `AI CMO`. Pick your new workspace. Type: **Internal**.
4. Under capabilities, enable **Read content**, **Update content**, **Insert content**.
5. Submit, then copy the **Internal Integration Secret** (starts with `ntn_` or `secret_`).
   This is your `NOTION_TOKEN`. Treat it like a password.

## 2. Make a parent page

In your new workspace, create one empty page, for example **AI CMO**. The database
will be created inside this page.

## 3. Share that page with the integration

1. Open the page.
2. Top-right **...** menu → **Connections** (or **Add connections**).
3. Select the **AI CMO** integration. Confirm.

This is what actually grants access. The integration can now read and write that
page and anything inside it.

## 4. Get the page id (gives you NOTION_PARENT_PAGE_ID)

Copy the page URL. It looks like:

```
https://www.notion.so/AI-CMO-24f1a9c0b8e34e7d9c2a1b6f0e5d4c3b
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

The long id at the end (32 hex characters, dashes optional) is your
`NOTION_PARENT_PAGE_ID`. If there is a `?v=...` on the end, ignore that part.

## 5. Put both values in `.env`

Open `.env` in the repo root (copy `.env.example` to `.env` first if needed) and set:

```
NOTION_TOKEN=ntn_your_secret_here
NOTION_PARENT_PAGE_ID=24f1a9c0b8e34e7d9c2a1b6f0e5d4c3b
```

Never paste the token into chat or commit it. `.env` is gitignored.

## 6. Build the database

From the repo root, load `.env` and run provision:

```bash
set -a && . ./.env && set +a
python3 engine/dashboard/notion_provision.py
```

This creates the **Content Pipeline** database inside your AI CMO page, with all
the columns (Title, Status, Pillar, Hook, Draft Caption, Brand QC Score, ...).
Refresh Notion and it is there. The database id is saved to
`data/notion_state.json` so it is created only once.

## 7. Push real content and approve

```bash
set -a && . ./.env && set +a
python3 run.py "why competitors all sound the same"   # generate a post through the pipeline
python3 engine/dashboard/notion_sync.py push          # push it to your Notion board
```

Open Notion, find the card at status **In Review**, change Status to **Approved**,
then pull the decision back into the pipeline:

```bash
python3 engine/dashboard/notion_sync.py pull          # advances the approved post
```

That is the full loop on your real Notion: generated, pushed, approved by a human
in Notion, advanced. Same commands work offline first (no token) in stub mode, so
you can rehearse before connecting.
