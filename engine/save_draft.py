"""Brain persistence helper.

Writes a finished Brick-chain draft to the frozen db.py contract at status
'drafted'. This is the ONLY field write Brain performs: pillar, angle, hook,
body. It never touches any other column and never modifies db.py.
"""
import argparse
import os
import sys

# Allow running as `python3 engine/save_draft.py` from the repo root: put the
# repo root (where db.py lives) on the path before importing the contract.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db


def save_draft(client, seed_idea, pillar, angle, hook, body, platform="linkedin"):
    """Create a post and advance it to 'drafted' with the four locked artifacts.

    Returns the new post id.
    """
    db.init_db()
    post_id = db.create_post(client=client, seed_idea=seed_idea, platform=platform)
    db.advance(
        post_id,
        db.Status.DRAFTED,
        pillar=pillar,
        angle=angle,
        hook=hook,
        body=body,
    )
    return post_id


def main():
    p = argparse.ArgumentParser(description="Persist a Brain draft at status 'drafted'.")
    p.add_argument("--client", required=True)
    p.add_argument("--seed", required=True)
    p.add_argument("--pillar", required=True)
    p.add_argument("--angle", required=True)
    p.add_argument("--hook", required=True)
    p.add_argument("--body", required=True)
    p.add_argument("--platform", default="linkedin")
    a = p.parse_args()
    print(save_draft(a.client, a.seed, a.pillar, a.angle, a.hook, a.body, a.platform))


if __name__ == "__main__":
    main()
