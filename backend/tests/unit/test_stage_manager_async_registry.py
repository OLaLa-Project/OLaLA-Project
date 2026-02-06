from __future__ import annotations

from app.orchestrator.stage_manager import get_async


def test_async_registry_exposes_io_stages() -> None:
    assert get_async("stage03_wiki") is not None
    assert get_async("stage03_web") is not None
    assert get_async("stage05_topk") is not None


def test_async_registry_returns_none_for_sync_only_stage() -> None:
    assert get_async("stage01_normalize") is None
