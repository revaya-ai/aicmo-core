"""The feedback loop. Anything that is not 'approve' sends the post back to the
Brain with a note, and the next draft folds the note in.

Two callers use this:
- the human gate, when the client Rejects (carries the client's comment), and
- Studio's brand QC, when the vision gate returns fail/borderline (carries the
  QC reason). Same destination either way: back to the start.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402


def send_back_to_brain(post_id: str, feedback: str) -> None:
    """Reset a post to 'captured' and store the feedback for the Brain re-draft."""
    note = (feedback or "").strip() or "Sent back for revision (no note given)."
    db.advance(post_id, db.Status.CAPTURED, human_note=note)
