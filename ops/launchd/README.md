# ops/launchd — AI CMO Cron Jobs

Five launchd agents run the AI CMO autonomy loop on this Mac. Identical jobs
move to VPS (Ubuntu/systemd) for production.

---

## Architecture: single dispatcher

All plists invoke `engine.cron` — a single CLI dispatcher:

```
python3 -m engine.cron <job> --client <slug>
```

Valid jobs: `cycle`, `publish`, `publish_check`, `engagement`, `metrics_push`

---

## Schedule

| Plist | Job | Cadence |
|---|---|---|
| `com.aicmo.cycle.plist` | `cron_cycle` — draft, render, QC, surface In Review | every 30 min |
| `com.aicmo.publish.plist` | `publish.run` — push scheduled posts to platforms | 06:30 and 18:30 |
| `com.aicmo.publish-check.plist` | `publish_check.run` — verify live URLs | every 30 min |
| `com.aicmo.engagement.plist` | `engagement_sync.run` — pull real metrics, update Notion | nightly 19:30 |
| `com.aicmo.metrics-push.plist` | `notion_metrics_push.run` — aggregate KPIs → Notion Metrics DB | daily 06:30 |

---

## Setting the Python path

The plists use `/opt/homebrew/bin/python3`. If your environment differs, find
the correct absolute path:

```bash
# From the repo root:
python3 -c "import sys; print(sys.executable)"
```

Replace the `<string>/opt/homebrew/bin/python3</string>` line in each plist
with that output. If you use a venv:

```bash
cd /Users/short/Downloads/aicmo-core
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -c "import sys; print(sys.executable)"  # -> .venv/bin/python3
```

---

## Load all jobs

```bash
cd /Users/short/Downloads/aicmo-core/ops/launchd

launchctl load com.aicmo.cycle.plist
launchctl load com.aicmo.publish.plist
launchctl load com.aicmo.publish-check.plist
launchctl load com.aicmo.engagement.plist
launchctl load com.aicmo.metrics-push.plist
```

Verify they are loaded:

```bash
launchctl list | grep com.aicmo
```

---

## Unload all jobs

```bash
cd /Users/short/Downloads/aicmo-core/ops/launchd

launchctl unload com.aicmo.cycle.plist
launchctl unload com.aicmo.publish.plist
launchctl unload com.aicmo.publish-check.plist
launchctl unload com.aicmo.engagement.plist
launchctl unload com.aicmo.metrics-push.plist
```

---

## Force-trigger a job immediately (for testing)

```bash
launchctl kickstart -k gui/$(id -u)/com.aicmo.cycle
```

Or run the dispatcher directly:

```bash
cd /Users/short/Downloads/aicmo-core
python3 -m engine.cron cycle --client lumen-skin
python3 -m engine.cron publish --client lumen-skin
python3 -m engine.cron publish_check --client lumen-skin
python3 -m engine.cron engagement --client lumen-skin
python3 -m engine.cron metrics_push --client lumen-skin
```

---

## Logs

All jobs log to `outputs/logs/<job>.log` (combined stdout+stderr):

```bash
tail -f /Users/short/Downloads/aicmo-core/outputs/logs/cycle.log
tail -f /Users/short/Downloads/aicmo-core/outputs/logs/publish.log
tail -f /Users/short/Downloads/aicmo-core/outputs/logs/publish-check.log
tail -f /Users/short/Downloads/aicmo-core/outputs/logs/engagement.log
tail -f /Users/short/Downloads/aicmo-core/outputs/logs/metrics-push.log
```

---

## Demo win condition

> Type an idea in Notion. The Mac drafts it, renders the image, runs QC, and
> surfaces the card as "In Review" — unattended. You approve in Notion. At the
> next 06:30 or 18:30 publish window the post ships. That night at 19:30
> engagement metrics sync back to the Notion Metrics DB.

Full loop cadence:

```
[every 30 min]  cycle:        Notion intake -> draft -> render -> QC -> In Review
[06:30, 18:30]  publish:      scheduled posts -> platform (Zernio stub offline)
[every 30 min]  publish_check: verify live URLs
[19:30 nightly] engagement:   pull real metrics -> Notion pipeline cards
[06:30 daily]   metrics_push: aggregate KPIs -> Notion Metrics DB
```

---

## Lint plists before loading

```bash
plutil -lint /Users/short/Downloads/aicmo-core/ops/launchd/*.plist
```

All five should output `OK`.
