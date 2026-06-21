"""One-command demo of the Winner Engine (Jamie's method).

Posts a batch of organic content (simulated — nothing actually goes live),
measures the follows each earned, ranks them, and promotes only the top 2-3 to
paid ads. This is the Card 3 showpiece.

    python demo_winners.py            # default: 6 posts, top 3 win
    python demo_winners.py 8 2        # 8 posts, top 2 win

Everything is dry-run: no accounts, no posting, no spend. The follows are
generated locally so the leaderboard is real-looking but safe to run on stage.
"""

import sys

import db
from engine.brain import generate as brain
from engine.studio import render, brand_qc as qc
from engine.mission import schedule, publish, analytics
from engine.ads import winners

IDEAS = [
    "why your competitors all sound the same",
    "the 3-step routine that actually works",
    "the 10-step routine is a trap",
    "why we cut our product line in half",
    "what 'clean' actually means on a label",
    "the 90-second routine that fits real life",
    "the ingredient everyone fears (and shouldn't)",
    "what your skin is really telling you",
]


def main() -> None:
    n_posts = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    db.init_db()
    print(f"\nPosting {n_posts} organic pieces (simulated) and measuring follows...\n")
    for idea in IDEAS[:n_posts]:
        pid = db.create_post("lumen-skin", idea, platform="instagram")
        brain.run(pid)            # write
        render.run(pid)           # design
        qc.run(pid)               # brand-check
        db.advance(pid, db.Status.APPROVED)   # (human gate auto-approved for the demo)
        schedule.run(pid)         # schedule
        publish.run(pid)          # "publish"
        analytics.run(pid)        # measure follows

    # Jamie's method: rank by follows, promote only the top N.
    print(winners.leaderboard_text(top_n=top_n))
    result = winners.review_and_recommend(top_n=top_n)
    won = len(result["winners"])
    print(f"  -> {won} winners promoted to PAID ADS; "
          f"{len(result['ranked']) - won} stay organic-only (not worth the spend).\n")

    print("  Why the #1 winner earned its ad budget:")
    top = db.get_post(result["winners"][0]["id"])   # rank-1 post, fresh from the DB
    print(f"    {top['human_note']}\n")
    print("  (Dry run — nothing posted, no money spent. Add API keys in .env to go live.)\n")


if __name__ == "__main__":
    main()
