from app.graph.state import normalize_stage_name


def test_normalize_stage_name_start_alias():
    assert normalize_stage_name("stage03_collect") == "stage03_wiki"


def test_normalize_stage_name_end_alias():
    assert normalize_stage_name("stage03_collect", for_end=True) == "stage03_merge"


def test_normalize_stage_name_invalid_returns_none():
    assert normalize_stage_name("unknown_stage") is None
