"""engine/cron.py — Single CLI dispatcher for all launchd cron jobs.

Usage (all plists point here):
    python -m engine.cron <job> --client <slug>

Jobs:
    cycle           engine.cycle.cron_cycle(client) -> dict
    publish         engine.mission.publish.run(client) -> int
    publish_check   engine.mission.publish_check.run(client) -> int
    engagement      engine.mission.engagement_sync.run(client) -> int
    metrics_push    engine.mission.notion_metrics_push.run(client) -> int

import engine.env is the first statement — it must remain so to load .env
before any other project import.
"""

import engine.env  # noqa: F401 — must be first project import to load .env

import argparse
import os
import sys

JOBS = {
    "cycle": ("engine.cycle", "cron_cycle"),
    "publish": ("engine.mission.publish", "run"),
    "publish_check": ("engine.mission.publish_check", "run"),
    "engagement": ("engine.mission.engagement_sync", "run"),
    "metrics_push": ("engine.mission.notion_metrics_push", "run"),
}


def _run(job: str, client: str):
    os.makedirs("outputs/logs", exist_ok=True)
    if job not in JOBS:
        print(f"[cron] Unknown job: {job!r}. Valid jobs: {', '.join(JOBS)}", file=sys.stderr)
        sys.exit(1)
    module_path, func_name = JOBS[job]
    import importlib
    mod = importlib.import_module(module_path)
    fn = getattr(mod, func_name)
    result = fn(client)
    print(f"[cron] {job} client={client!r} -> {result}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI CMO cron dispatcher")
    parser.add_argument("job", choices=list(JOBS), help="Which cron job to run")
    parser.add_argument("--client", default="lumen-skin", help="Client slug (default: lumen-skin)")
    args = parser.parse_args()
    _run(args.job, args.client)
