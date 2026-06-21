import os

LIB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "libraries")
_FILES = {
    "voice_os": "voice-os.md",
    "angles": "angle-library.md",
    "hooks": "hook-library.md",
    "stories": "story-structures.md",
    "strategy": "strategy.md",
}


def load_libraries() -> dict:
    out = {}
    for key, fname in _FILES.items():
        path = os.path.join(LIB_DIR, fname)
        with open(path, encoding="utf-8") as fh:
            out[key] = fh.read()
    return out
