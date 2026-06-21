# engine/guardrails/compliance.py
"""Cosmetic-claims compliance gate for the AI CMO content engine.

Reads an optional `client-data/<client>/compliance.md` file.
If the file has a `## banned claims` section, each non-empty, non-comment
line is treated as a banned phrase (case-insensitive substring match).

When no ruleset file exists the check always passes — other clients are
not penalised by a ruleset they have not configured.

Public API:
    check(client: str, text: str) -> dict
        Returns {"passed": bool, "violations": list[str]}.
"""

import os

CLIENT_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "client-data")


def _banned(client: str) -> list:
    """Return the list of banned phrases for *client*, or [] if none configured."""
    path = os.path.join(CLIENT_DATA_DIR, client, "compliance.md")
    if not os.path.exists(path):
        return []
    out, capture = [], False
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s.lower().startswith("## banned claims"):
            capture = True
            continue
        if s.startswith("##"):
            capture = False
        if capture and s and not s.startswith("#"):
            phrase = s.lstrip("- ").lower()
            if phrase:
                out.append(phrase)
    return out


def check(client: str, text: str) -> dict:
    """Check *text* against the banned-claims ruleset for *client*.

    Returns:
        {"passed": bool, "violations": list[str]}
    """
    low = (text or "").lower()
    violations = [b for b in _banned(client) if b and b in low]
    return {"passed": not violations, "violations": violations}
