"""Lay out a client's Notion page to match the approved design: an intro, a
Dashboard section with KPI 'tiles' (callouts), and section headings for Intake,
Brand & Voice, and Requests.

The Notion API builds content blocks reliably. It does NOT reliably build board
or calendar VIEWS or gallery tiles, so those remain a short manual step in the
Notion UI (see docs/notion-views-manual.md). This module does everything the API
can do automatically.
"""

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from engine.dashboard import kpi_menu, notion_client, notion_provision  # noqa: E402


def _rt(text):
    return [{"type": "text", "text": {"content": text}}]


def _h2(text):
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": _rt(text)}}


def _para(text):
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(text)}}


def _callout(text, emoji, color="default"):
    return {
        "object": "block",
        "type": "callout",
        "callout": {"rich_text": _rt(text), "icon": {"type": "emoji", "emoji": emoji},
                    "color": color},
    }


def _divider():
    return {"object": "block", "type": "divider", "divider": {}}


def build_page_layout(client: str):
    """Append the dashboard tiles + section headings to the client's page. Idempotent."""
    rec = notion_provision.provision_client(client)

    if not notion_client.is_configured():
        print(f"STUB: would lay out '{client}' page (intro + dashboard tiles + sections).")
        return rec
    if rec.get("layout_built"):
        print("layout already built; skipping (idempotent).")
        return rec

    blocks = [
        _callout(
            "Your AI CMO. Review the Content Pipeline: approve, comment, or reject. "
            "Six steps run themselves, the seventh is you.",
            "🤝", "blue_background",
        ),
        _divider(),
        _h2("Dashboard"),
    ]
    for key, label, source in kpi_menu.resolve(rec.get("kpis")):
        val = kpi_menu.MOCK_VALUES.get(key, "n/a")
        blocks.append(_callout(f"{label}:  {val}   ·   {source}   ·   (mock)", "📈",
                               "gray_background"))
    blocks += [
        _divider(),
        _h2("Intake — add an idea"),
        _para("Add a row to Content Pipeline with Status = Idea. The AI CMO drafts it."),
        _h2("Brand & Voice"),
        _para("How the engine sounds like you: positioning, audience, voice, guardrails."),
        _h2("Requests"),
        _para("Drop a note in any comment and we pick it up."),
    ]

    notion_client.append_blocks(rec["page_id"], blocks)  # well under the 100-block limit
    rec["layout_built"] = True
    notion_provision.save_client(client, rec)
    print(f"laid out {len(blocks)} blocks on the '{client}' page")
    return rec


def main():
    import argparse

    p = argparse.ArgumentParser(description="Lay out a client's Notion page.")
    p.add_argument("client")
    a = p.parse_args()
    build_page_layout(a.client)


if __name__ == "__main__":
    main()
