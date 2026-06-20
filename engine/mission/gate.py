"""STATION 3 — Mission: the human approval gate.

Reads:  status == qc_review
Writes: status == approved          (human says ship it)
        status == rejected          (human kills it)
        status == needs_revision    (human wants changes)
        (optionally sets human_note)

Signature: run(post_id: str, auto_approve: bool = False) -> None

This is the one true human-in-the-loop step. The real gate is a person clicking
in the Flask app below. For the unattended demo loop, run.py passes
auto_approve=True and this function approves automatically.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Allow `python engine/mission/gate.py` to find the shared db.py at repo root.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from db import Status, get_post, advance


def run(post_id: str, auto_approve: bool = False) -> None:
    post = get_post(post_id)

    if auto_approve:
        advance(
            post_id,
            Status.APPROVED,
            human_note="AUTO-APPROVED (demo loop).",
        )
        return

    # Without auto_approve the decision belongs to a human acting through the
    # Flask app below. If the loop calls this directly, fail loud so a
    # misconfigured run is obvious rather than silently auto-approving.
    raise RuntimeError(
        f"Post {post_id} is at {post['status']} and needs human review. "
        "Run the Flask gate app (python engine/mission/gate.py) or pass "
        "auto_approve=True."
    )


# --------------------------------------------------------------------------
# The REAL human gate — a small, phone-friendly Flask board.
# Run it with:  python engine/mission/gate.py   then open http://localhost:5000
# Lists every post waiting at qc_review and lets a human Approve / Reject /
# Revise. Approve -> approved (post ships). Reject -> rejected (killed).
# Revise -> needs_revision (bounced back to the studio with a note).
# --------------------------------------------------------------------------

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI CMO &middot; Approval Gate</title>
  <style>
    :root {{
      --bg:#F7F3EC; --accent:#C77B58; --ink:#2E2620; --muted:#D9CFC1;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; background:var(--bg); color:var(--ink);
      font-family:"Inter","Work Sans",system-ui,sans-serif;
      -webkit-font-smoothing:antialiased;
    }}
    header {{
      padding:28px 20px 18px; border-bottom:1px solid var(--muted);
      position:sticky; top:0; background:var(--bg); z-index:5;
    }}
    header h1 {{
      margin:0; font-family:"Fraunces",Georgia,serif; font-weight:600;
      font-size:22px; letter-spacing:.2px;
    }}
    header p {{ margin:4px 0 0; color:#7a6f63; font-size:13px; }}
    .wrap {{ max-width:620px; margin:0 auto; padding:20px 16px 64px; }}
    .empty {{
      text-align:center; color:#7a6f63; padding:72px 20px;
      font-size:16px; line-height:1.6;
    }}
    .card {{
      background:#fff; border:1px solid var(--muted); border-radius:14px;
      overflow:hidden; margin:0 0 22px; box-shadow:0 1px 3px rgba(46,38,32,.06);
    }}
    .card .img {{
      width:100%; aspect-ratio:4/5; background:var(--muted);
      display:flex; align-items:center; justify-content:center;
      color:#9a8d7d; font-size:13px; object-fit:cover;
    }}
    img.img {{ display:block; }}
    .card .meta {{ padding:18px 18px 6px; }}
    .pillar {{
      display:inline-block; font-size:11px; letter-spacing:.8px;
      text-transform:uppercase; color:var(--accent); font-weight:700;
      margin-bottom:8px;
    }}
    .hook {{ font-family:"Fraunces",Georgia,serif; font-size:19px; line-height:1.35; margin:0 0 10px; }}
    .body {{ white-space:pre-wrap; font-size:15px; line-height:1.6; color:#403730; margin:0 0 14px; }}
    .qc {{ font-size:12px; color:#7a6f63; border-top:1px dashed var(--muted); padding-top:10px; }}
    .qc b {{ color:var(--ink); }}
    .actions {{ display:flex; gap:10px; padding:14px 18px 20px; }}
    .actions button {{
      flex:1; padding:14px 8px; border:0; border-radius:10px; cursor:pointer;
      font-size:15px; font-weight:600; font-family:inherit;
    }}
    .approve {{ background:var(--accent); color:#fff; }}
    .revise  {{ background:#fff; color:var(--ink); border:1px solid var(--muted) !important; }}
    .reject  {{ background:#fff; color:#b23b3b; border:1px solid #e7c4c4 !important; }}
    .actions button:active {{ transform:translateY(1px); }}
  </style>
</head>
<body>
  <header>
    <h1>AI CMO &middot; Approval Gate</h1>
    <p>{count}</p>
  </header>
  <div class="wrap">{cards}</div>
</body>
</html>"""

CARD = """
<div class="card">
  {image}
  <div class="meta">
    <span class="pillar">{pillar}</span>
    <p class="hook">{hook}</p>
    <p class="body">{body}</p>
    <p class="qc">QC score: <b>{qc_score}</b> &middot; {qc_notes}</p>
  </div>
  <form class="actions" method="post" action="/decide/{id}">
    <button class="approve" name="decision" value="approved">Approve</button>
    <button class="revise"  name="decision" value="needs_revision">Revise</button>
    <button class="reject"  name="decision" value="rejected">Reject</button>
  </form>
</div>"""

SPEND_CARD = """
<div class="card">
  <div class="meta">
    <span class="pillar">Ad recommended</span>
    <p class="hook">{hook}</p>
    <p class="body">{rationale}</p>
    <p class="qc">Budget: <b>${budget}</b> &middot; Audience: {audience}</p>
  </div>
  <form class="actions" method="post" action="/spend/{id}">
    <button class="approve" name="decision" value="ad_approved">Approve spend</button>
    <button class="reject"  name="decision" value="decline">Decline</button>
  </form>
</div>"""


def _esc(text) -> str:
    s = "" if text is None else str(text)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def create_app():
    from flask import Flask, request, redirect, send_from_directory

    import db

    app = Flask(__name__)

    @app.route("/")
    def index():
        rows = db.list_by_status(Status.QC_REVIEW)
        if not rows:
            cards = (
                '<div class="empty">Nothing waiting for review.<br>'
                "When the studio passes a post, it shows up here.</div>"
            )
            count = "Inbox zero"
        else:
            count = f"{len(rows)} post{'s' if len(rows) != 1 else ''} waiting for your call"
            built = []
            for p in rows:
                img_path = p.get("image_path") or ""
                full = os.path.join(REPO_ROOT, img_path) if img_path else ""
                if img_path and os.path.exists(full):
                    image = f'<img class="img" src="/render/{_esc(img_path)}" alt="post graphic">'
                else:
                    image = '<div class="img">graphic preview</div>'
                built.append(
                    CARD.format(
                        image=image,
                        pillar=_esc(p.get("pillar") or "Post"),
                        hook=_esc(p.get("hook") or ""),
                        body=_esc(p.get("body") or ""),
                        qc_score=_esc(p.get("qc_score")),
                        qc_notes=_esc(p.get("qc_notes") or ""),
                        id=_esc(p["id"]),
                    )
                )
            cards = "".join(built)
        spend_rows = db.list_by_status(Status.AD_RECOMMENDED)
        spend_built = []
        for p in spend_rows:
            spend_built.append(
                SPEND_CARD.format(
                    hook=_esc(p.get("hook") or ""),
                    rationale=_esc(p.get("human_note") or ""),
                    budget=_esc(p.get("ad_budget")),
                    audience=_esc(p.get("ad_audience") or ""),
                    id=_esc(p["id"]),
                )
            )
        if spend_built:
            cards = cards + (
                '<h2 style="font-family:Fraunces,Georgia,serif;font-size:18px;'
                'margin:28px 0 12px;">Spend approvals</h2>' + "".join(spend_built)
            )
        return PAGE.format(count=count, cards=cards)

    @app.route("/render/<path:img_path>")
    def render_file(img_path):
        # Serve the rendered PNG from the repo so the preview shows in the card.
        directory = os.path.join(REPO_ROOT, os.path.dirname(img_path))
        return send_from_directory(directory, os.path.basename(img_path))

    @app.route("/decide/<post_id>", methods=["POST"])
    def decide(post_id):
        decision = request.form["decision"]
        if decision not in (Status.APPROVED, Status.REJECTED, Status.NEEDS_REVISION):
            return "bad decision", 400
        labels = {
            Status.APPROVED: "Human approved — ship it.",
            Status.REJECTED: "Human rejected — killed.",
            Status.NEEDS_REVISION: "Human asked for a revision.",
        }
        db.advance(post_id, decision, human_note=labels[decision])
        if decision == Status.APPROVED:
            from engine.mission import driver
            driver.drive(post_id)  # walk it to the spend gate
        return redirect("/")

    @app.route("/spend/<post_id>", methods=["POST"])
    def spend(post_id):
        decision = request.form["decision"]
        if decision == "ad_approved":
            from engine.ads import ads_agent
            ads_agent.approve_spend(post_id, approved_by="human via gate")
        elif decision == "decline":
            db.update_post(post_id, ad_status="declined")
        else:
            return "bad decision", 400
        return redirect("/")

    return app


if __name__ == "__main__":
    # Port 5050, not 5000: macOS AirPlay Receiver squats on 5000.
    print("AI CMO gate running -> open http://localhost:5050")
    create_app().run(debug=True, port=5050)
