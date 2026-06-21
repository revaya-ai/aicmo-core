"""
engine/ingest.py — pattern-mining flywheel for the voice/angle libraries.

Two public functions:

    ingest(source_text, source_label) -> str
        Append the raw source text to libraries/raw-context/<safe-label>.md.
        This is the ONLY place raw content is stored. Returns the path written.

    mine(today, library="angle-library") -> list[str]
        Read every file in raw-context/, extract reusable PATTERNS (not raw
        content), append each as a stamped bullet to libraries/<library>.md,
        and return the list of patterns appended.

        Online path  (ANTHROPIC_API_KEY present): Claude API extracts patterns.
        Offline path (no key):                   deterministic heuristic extractor.

Marker handling choice:
    On first mine(), the `<!-- mined: (none yet) -->` marker is LEFT in place and
    new pattern bullets are APPENDED after it.  This preserves the marker as a
    harmless historical breadcrumb and avoids any rewrite of existing library
    content (safer, auditable).  Subsequent mine() calls simply append further
    bullets at the end of the file.
"""

import os
import re
from pathlib import Path

import engine.env  # noqa: F401 — ensures .env is loaded first

# ---------------------------------------------------------------------------
# Path constants (monkeypatched by tests)
# ---------------------------------------------------------------------------

LIBRARIES_DIR: Path = Path(__file__).resolve().parents[1] / "libraries"
RAW_CONTEXT_DIR: Path = LIBRARIES_DIR / "raw-context"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_label(label: str) -> str:
    """Convert an arbitrary label to a filesystem-safe filename stem."""
    return re.sub(r"[^\w\-]", "-", label).strip("-").lower()


def _offline_extract(source_text: str) -> list[str]:
    """
    Deterministic heuristic extractor — no LLM required.

    Heuristic: split text on sentence boundaries (period, exclamation, question
    mark), keep sentences that contain one or more of the angle signal words
    (cost, why, how, myth, truth, insider, contrast, before, after, without,
    hidden, real, stop, never, secret).  Deduplicate while preserving order.
    Return up to 5 candidate patterns as short phrase-summaries.

    Why this heuristic: angle patterns are claims that create tension.  Signal
    words surface claims about contrast, cost, or correction — the three most
    common angle shapes in the library.
    """
    SIGNALS = {
        "cost", "why", "how", "myth", "truth", "insider", "contrast",
        "before", "after", "without", "hidden", "real", "stop", "never",
        "secret", "problem", "lesson", "wrong", "fail", "transform",
        "reduce", "improve", "study", "result", "skin", "barrier", "damage",
        "texture", "redness", "lines", "weeks", "days", "clinical",
    }

    # Strip raw-context separators before processing.
    cleaned = re.sub(r"\n---\n", "\n", source_text)

    # Split on sentence-ending punctuation.
    sentences = re.split(r"(?<=[.!?])\s+", cleaned.strip())

    patterns: list[str] = []
    seen: set[str] = set()

    for sent in sentences:
        clean = sent.strip().rstrip(".")
        if not clean:
            continue
        lower = clean.lower()
        hits = sum(1 for sig in SIGNALS if sig in lower)
        if hits >= 1:
            # Normalise to a short phrase (first 120 chars).
            phrase = clean[:120]
            if phrase not in seen:
                seen.add(phrase)
                patterns.append(phrase)

    # Fallback: if nothing matched, return the first sentence trimmed.
    if not patterns and sentences:
        phrase = sentences[0].strip().rstrip(".")[:120]
        patterns.append(phrase)

    return patterns[:5]


def _online_extract(source_text: str) -> list[str]:
    """
    Call Claude to extract reusable angle patterns from source_text.
    Returns a list of short pattern strings (one per line from the response).
    Falls back to offline extractor on any exception.
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        prompt = (
            "You are a content strategist. Read the following raw source text and extract "
            "up to 5 reusable ANGLE PATTERNS. Each pattern must be a short, transferable "
            "insight or tension (10-20 words), not a quote or copy of the original. "
            "Return one pattern per line, plain text, no bullets.\n\n"
            f"SOURCE:\n{source_text[:3000]}"
        )
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        lines = [ln.strip() for ln in message.content[0].text.splitlines() if ln.strip()]
        return lines[:5] if lines else _offline_extract(source_text)
    except Exception:  # noqa: BLE001
        return _offline_extract(source_text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest(source_text: str, source_label: str) -> str:
    """
    Write raw source_text to libraries/raw-context/<safe_label>.md.
    Appends if the file already exists (accumulates across calls).
    Returns the absolute path written as a string.
    """
    RAW_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    safe = _safe_label(source_label)
    dest = RAW_CONTEXT_DIR / f"{safe}.md"

    separator = "\n\n---\n\n" if dest.exists() else ""
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(f"{separator}{source_text}\n")

    return str(dest)


def mine(today: str, library: str = "angle-library") -> list[str]:
    """
    Read all raw-context files, extract patterns (online or offline), append
    each as a stamped bullet to libraries/<library>.md.

    Parameters
    ----------
    today : str
        Injection point for the date stamp (YYYY-MM-DD).  Never calls
        datetime.now() — callers supply the date for determinism.
    library : str
        Stem of the target library file (default: "angle-library").

    Returns
    -------
    list[str]
        The pattern strings that were appended (one per bullet added).
    """
    # Collect all raw-context text.
    raw_texts: list[str] = []
    if RAW_CONTEXT_DIR.exists():
        for raw_file in sorted(RAW_CONTEXT_DIR.iterdir()):
            if raw_file.suffix == ".md":
                raw_texts.append(raw_file.read_text(encoding="utf-8"))

    if not raw_texts:
        return []

    combined = "\n\n".join(raw_texts)

    # Extract patterns — online if key present, else offline.
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        patterns = _online_extract(combined)
    else:
        patterns = _offline_extract(combined)

    if not patterns:
        return []

    # Append stamped bullets to the target library.
    library_path = LIBRARIES_DIR / f"{library}.md"
    library_path.parent.mkdir(parents=True, exist_ok=True)
    if not library_path.exists():
        library_path.write_text(f"# {library.replace('-', ' ').title()}\n\n<!-- mined: (none yet) -->\n")

    stamp = f"<!-- mined: {today} -->"
    bullet_lines = [f"- {p} {stamp}" for p in patterns]
    with library_path.open("a", encoding="utf-8") as fh:
        fh.write("\n" + "\n".join(bullet_lines) + "\n")

    return patterns
