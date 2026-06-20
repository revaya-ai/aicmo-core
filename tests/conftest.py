import os
import sys

import pytest

# Make repo root importable so `import db` works from tests/.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import db


@pytest.fixture
def fresh_db(tmp_path):
    """Point the frozen db at a throwaway file for the duration of one test."""
    original = db.DB_PATH
    db.DB_PATH = str(tmp_path / "test_aicmo.db")
    db.init_db()
    try:
        yield db
    finally:
        db.DB_PATH = original
