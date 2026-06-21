import os, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_no_duplicate_notion_sync():
    assert not os.path.exists(os.path.join(REPO, "scripts", "notion_sync.py"))


def test_cc_command_retired():
    assert not os.path.exists(os.path.join(REPO, ".claude", "commands", "ai-cmo-generate.md"))


def test_generate_mock_removed():
    assert not os.path.exists(os.path.join(REPO, "engine", "brain", "generate_mock.py"))


def test_api_key_name_exact():
    env = open(os.path.join(REPO, ".env.example")).read()
    assert "ANTHROPIC_API_KEY" in env


def test_env_preflight_lists_required_keys():
    from engine.env import preflight
    assert set(preflight()) == {"ANTHROPIC_API_KEY", "NOTION_TOKEN", "NOTION_PARENT_PAGE_ID"}
