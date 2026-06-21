import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

REQUIRED = ["ANTHROPIC_API_KEY", "NOTION_TOKEN", "NOTION_PARENT_PAGE_ID"]


def preflight() -> dict:
    """Report which required keys are present. Never prints values."""
    return {k: bool(os.environ.get(k)) for k in REQUIRED}
