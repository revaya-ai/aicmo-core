"""
Task 11: /ingest pattern-mining flywheel tests.

All tests use tmp_path to redirect LIBRARIES_DIR and RAW_CONTEXT_DIR so the
real libraries/*.md files are never modified by the test suite.
"""

import importlib
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_ingest(monkeypatch, tmp_path):
    """Import engine.ingest with library paths redirected to tmp_path."""
    import engine.ingest as ingest_mod

    # Redirect the module-level path constants before use.
    libs_dir = tmp_path / "libraries"
    libs_dir.mkdir()
    raw_dir = libs_dir / "raw-context"
    raw_dir.mkdir()

    monkeypatch.setattr(ingest_mod, "LIBRARIES_DIR", libs_dir)
    monkeypatch.setattr(ingest_mod, "RAW_CONTEXT_DIR", raw_dir)

    # Seed a minimal angle-library.md in the tmp dir.
    (libs_dir / "angle-library.md").write_text(
        "# Angle Library\n\nSome existing content.\n\n<!-- mined: (none yet) -->\n"
    )
    return ingest_mod, libs_dir, raw_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ingest_writes_raw_source(monkeypatch, tmp_path):
    """ingest() must create the raw-context file containing the source text."""
    ingest_mod, libs_dir, raw_dir = _load_ingest(monkeypatch, tmp_path)

    text = "Our hero serum reduces visible lines in 14 days. Before/after science."
    label = "lumen-test-source"

    path_written = ingest_mod.ingest(text, label)

    assert path_written is not None
    written = (raw_dir / "lumen-test-source.md").read_text()
    assert text in written


def test_mine_appends_stamped_pattern_to_angle_library(monkeypatch, tmp_path):
    """
    After ingesting a source, mine() must:
    - append at least one pattern line stamped <!-- mined: 2026-06-21 -->
    - NOT copy the raw source block verbatim into the library
    """
    ingest_mod, libs_dir, raw_dir = _load_ingest(monkeypatch, tmp_path)

    source = "Clinical study: 94% of users saw improvement in 4 weeks. Cost of inaction: dull, uneven skin every morning."
    ingest_mod.ingest(source, "lumen-clinical")

    patterns = ingest_mod.mine(today="2026-06-21", library="angle-library")

    assert len(patterns) >= 1, "mine() must return at least one pattern"

    library_content = (libs_dir / "angle-library.md").read_text()

    # Every returned pattern must appear in the file with the stamp.
    for p in patterns:
        assert "<!-- mined: 2026-06-21 -->" in library_content, (
            "Library must contain the mined date stamp"
        )
        # Pattern text itself must appear in library.
        assert p.strip() in library_content or p.strip().lstrip("- ") in library_content

    # Raw source must NOT be pasted verbatim into the library.
    assert source not in library_content, (
        "Raw source block must not be copied into the angle library"
    )


def test_mine_offline_deterministic(monkeypatch, tmp_path):
    """
    With no API key, mine() must still return a non-empty, deterministic list.
    Running mine() twice on the same input must return the same patterns.
    """
    import os
    # Ensure no API key is present for this test.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    ingest_mod, libs_dir, raw_dir = _load_ingest(monkeypatch, tmp_path)

    source = "Skin texture transforms when you stop over-stripping. The hidden cost: redness and barrier damage."
    ingest_mod.ingest(source, "offline-test")

    # Seed a fresh angle-library for the second mine call (avoid double-appending confusion).
    first_patterns = ingest_mod.mine(today="2026-06-21", library="angle-library")
    assert len(first_patterns) >= 1

    # Reset the library and mine again — same source, same output.
    (libs_dir / "angle-library.md").write_text(
        "# Angle Library\n\n<!-- mined: (none yet) -->\n"
    )
    # Re-ingest the same content so raw-context is still present.
    ingest_mod.ingest(source, "offline-test")
    second_patterns = ingest_mod.mine(today="2026-06-21", library="angle-library")

    assert first_patterns == second_patterns, (
        "Offline extractor must be deterministic across calls"
    )
