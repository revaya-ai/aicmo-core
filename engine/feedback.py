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


def reprocess_to_review(post_id: str) -> None:
    """Take a sent-back (captured) post back through Brain + Studio to qc_review,
    so the revised draft lands in front of the human again. Without this, a
    rejected card stalls at 'captured' and never re-drafts. Imports are local to
    avoid a circular import at module load.
    """
    from engine.brain import ai_cmo_generate as brain
    from engine.studio import brand_qc, render

    brain.run(post_id)      # captured -> drafted (folds human_note feedback in)
    render.run(post_id)     # re-render the image
    brand_qc.run(post_id)   # drafted -> qc_review (back in front of the human)


def reject_and_redraft(post_id: str, feedback: str) -> None:
    """Full reject/QC-fail loop: store the feedback, then re-draft to qc_review."""
    send_back_to_brain(post_id, feedback)
    reprocess_to_review(post_id)
