from engine.brain.libraries import load_libraries


def test_load_libraries_returns_all_five():
    libs = load_libraries()
    assert set(libs) == {"voice_os", "angles", "hooks", "stories", "strategy"}
    assert all(isinstance(v, str) and v.strip() for v in libs.values())
