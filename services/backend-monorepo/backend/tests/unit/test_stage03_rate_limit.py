from __future__ import annotations

import asyncio

import pytest

import app.stages.stage03_collect.node as collect_node


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
async def test_search_naver_retries_after_429(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(collect_node.settings, "naver_client_id", "test-id")
    monkeypatch.setattr(collect_node.settings, "naver_client_secret", "test-secret")
    monkeypatch.setattr(collect_node.settings, "external_api_retry_attempts", 3)
    monkeypatch.setattr(collect_node.settings, "external_api_backoff_seconds", 0.01)
    monkeypatch.setattr(collect_node.settings, "external_api_timeout_seconds", 1.0)
    _orig_sleep = asyncio.sleep

    async def _fast_sleep(*_args, **_kwargs):
        await _orig_sleep(0)

    monkeypatch.setattr(collect_node.asyncio, "sleep", _fast_sleep)

    calls = {"count": 0}

    def _fake_get(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse(429, text="too many requests")
        return _FakeResponse(
            200,
            payload={
                "items": [
                    {
                        "title": "<b>테스트</b> 제목",
                        "description": "<b>테스트</b> 설명",
                        "link": "https://example.com/news/1",
                        "pubDate": "Fri, 06 Feb 2026 10:00:00 +0900",
                    }
                ]
            },
        )

    monkeypatch.setattr(collect_node.requests, "get", _fake_get)

    results = await collect_node._search_naver("테스트", limiter=asyncio.Semaphore(1))
    assert calls["count"] == 2
    assert len(results) == 1
    assert results[0]["title"] == "테스트 제목"


@pytest.mark.asyncio
async def test_search_ddg_retries_after_rate_limit_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(collect_node.settings, "external_api_retry_attempts", 3)
    monkeypatch.setattr(collect_node.settings, "external_api_backoff_seconds", 0.01)
    monkeypatch.setattr(collect_node.settings, "external_api_timeout_seconds", 1.0)
    _orig_sleep = asyncio.sleep

    async def _fast_sleep(*_args, **_kwargs):
        await _orig_sleep(0)

    monkeypatch.setattr(collect_node.asyncio, "sleep", _fast_sleep)

    class _FakeDDGS:
        calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def text(self, _query: str, max_results: int = 10):  # noqa: ARG002
            type(self).calls += 1
            if type(self).calls == 1:
                raise RuntimeError("429 rate limit")
            return [{"title": "t", "href": "https://example.com", "body": "b"}]

    monkeypatch.setattr(collect_node, "DDGS", _FakeDDGS)

    results = await collect_node._search_duckduckgo("query", limiter=asyncio.Semaphore(1))
    assert _FakeDDGS.calls == 2
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"
