"""Full demo runner — uses the Claude-powered Brain mock + real Studio + Notion sync.

Run this to see the complete creative journey end-to-end and watch it
appear live in Notion. Does NOT touch Shannon's generate.py or Laura's mission files.

Usage:
    python run_demo.py "why your competitors all sound the same"
    python run_demo.py "the 10-step routine is a lie"
"""

import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import db
from db import get_post

# Use the Claude-powered mock Brain instead of Shannon's stub
from engine.brain import generate_mock as brain
from engine.studio import render as studio_render
from engine.studio import brand_qc as studio_brand_qc
from engine.mission import gate as mission_gate
from engine.mission import schedule as mission_schedule
from engine.mission import publish as mission_publish
from engine.mission import analytics as mission_analytics
from scripts import notion_sync

CLIENT = "lumen-skin"

PIPELINE = [
    ("brain.mock",       brain),
    ("studio.render",    studio_render),
    ("studio.brand_qc",  studio_brand_qc),
    ("mission.gate",     mission_gate),
    ("mission.schedule", mission_schedule),
    ("mission.publish",  mission_publish),
    ("mission.analytics",mission_analytics),
]


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python run_demo.py "<seed idea>"')
        sys.exit(1)

    seed_idea = sys.argv[1]
    db.init_db()
    post_id = db.create_post(CLIENT, seed_idea)
    print(f"\n🎬 AI CMO Demo")
    print(f"   Seed idea : {seed_idea}")
    print(f"   Post ID   : {post_id}")
    print(f"   Client    : {CLIENT}\n")

    # Create the Notion page immediately so you can open it while it runs
    notion_page_id = notion_sync.create_page(get_post(post_id))
    print(f"   Notion    : https://notion.so/{notion_page_id.replace('-', '')}\n")

    for label, station in PIPELINE:
        before = get_post(post_id)["status"]
        station.run(post_id, auto_approve=True)
        post  = get_post(post_id)
        after = post["status"]

        if before == after:
            print(f"  {before:<16} (no transition)  [{label}]")
        else:
            print(f"  {before:<16} → {after:<16} [{label}]")

        # Sync to Notion after every transition
        notion_sync.update_page(notion_page_id, post)

    print("\n─────────────────────────────────────────")
    post = get_post(post_id)
    print(f"  Hook      : {post.get('hook', '')}")
    print(f"  Pillar    : {post.get('pillar', '')}")
    print(f"  Angle     : {post.get('angle', '')}")
    print(f"  QC Score  : {post.get('qc_score', 'n/a')}")
    print(f"  Status    : {post.get('status', '')}")
    print(f"\n  Notion    : https://notion.so/{notion_page_id.replace('-', '')}")
    print("─────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
