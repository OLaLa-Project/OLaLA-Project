from __future__ import annotations

import pytest

import app.stages.stage03_collect.node as collect_node


@pytest.mark.asyncio
async def test_run_wiki_async_strict_mode_skips_direct_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(collect_node.settings, "stage3_wiki_strict_vector_only", True)

    calls = {"count": 0}

    async def _fake_search_wiki(_query: str, _mode: str):
        calls["count"] += 1
        return []

    monkeypatch.setattr(collect_node, "_search_wiki", _fake_search_wiki)

    state = {
        "claim_text": "테스트 주장",
        "search_queries": [{"type": "direct", "text": "직접 검색 문장"}],
    }

    out = await collect_node.run_wiki_async(state)
    assert out["wiki_candidates"] == []
    assert out["stage03_wiki_diagnostics"]["vector_only"] is True
    assert out["stage03_wiki_diagnostics"]["wiki_query_used"] == ""
    assert calls["count"] == 0


@pytest.mark.asyncio
async def test_run_web_async_dedupes_and_clips_queries(monkeypatch: pytest.MonkeyPatch):
    naver_calls: list[str] = []
    ddg_calls: list[str] = []

    async def _fake_search_naver(query: str, limiter=None):  # noqa: ARG001
        naver_calls.append(query)
        return []

    async def _fake_search_ddg(query: str, limiter=None):  # noqa: ARG001
        ddg_calls.append(query)
        return []

    monkeypatch.setattr(collect_node, "_search_naver", _fake_search_naver)
    monkeypatch.setattr(collect_node, "_search_duckduckgo", _fake_search_ddg)

    state = {
        "search_queries": [
            {
                "type": "news",
                "text": "김병현 11곳 폐업 광우병 일본 불매 코로나19 공식입장!!!!!!!!!!!!!!!!!!!!!!!!",
                "meta": {"claim_id": "C1", "intent": "official_statement", "mode": "mixed", "stance": "support"},
            },
            {
                "type": "verification",
                "text": "김병현,11곳-폐업 광우병 일본 불매 코로나19 공식입장",
                "meta": {"claim_id": "C1", "intent": "fact_check", "mode": "mixed", "stance": "skeptic"},
            },
            {
                "type": "web",
                "text": "김병현 11곳 폐업 원출처 최초유포",
                "meta": {"claim_id": "C1", "intent": "origin_trace", "mode": "mixed", "stance": "neutral"},
            },
        ]
    }

    out = await collect_node.run_web_async(state)
    diagnostics = out["stage03_web_diagnostics"]

    assert diagnostics["web_query_count"] == 3
    assert diagnostics["web_query_deduped_count"] == 2
    assert diagnostics["avg_query_len"] <= 50
    assert len(diagnostics["queries_used"]) == 2
    assert diagnostics["fallback_ddg_count"] == 1
    assert diagnostics["blocked_domain_count"] == 0
    assert diagnostics["blocked_pattern_count"] == 0
    assert diagnostics["blocked_language_count"] == 0
    assert len(naver_calls) == 1
    assert len(ddg_calls) == 2


@pytest.mark.asyncio
async def test_run_wiki_async_collects_embed_diagnostics(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(collect_node.settings, "stage3_wiki_strict_vector_only", True)

    async def _fake_search_wiki(_query: str, _mode: str):
        return {
            "items": [],
            "debug": {
                "embed_error": "No module named sentence_transformers",
                "candidates_count": 4,
                "query_used_normalized": "테스트 위키 쿼리",
            },
        }

    monkeypatch.setattr(collect_node, "_search_wiki", _fake_search_wiki)

    state = {
        "claim_text": "테스트 주장",
        "search_queries": [{"type": "wiki", "text": "테스트 위키 쿼리"}],
    }

    out = await collect_node.run_wiki_async(state)
    diagnostics = out["stage03_wiki_diagnostics"]

    assert out["wiki_candidates"] == []
    assert diagnostics["wiki_query_count"] == 1
    assert diagnostics["embed_error"] == "No module named sentence_transformers"
    assert diagnostics["candidates_count"] == 4
    assert diagnostics["query_used_normalized"] == "테스트 위키 쿼리"


@pytest.mark.asyncio
async def test_run_wiki_async_caps_wiki_results(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(collect_node.settings, "stage3_wiki_strict_vector_only", True)
    monkeypatch.setattr(collect_node.settings, "stage3_wiki_result_cap", 1)

    async def _fake_search_wiki(_query: str, _mode: str):
        return {
            "items": [
                {"title": "문서1", "content": "a", "metadata": {"page_id": 1}},
                {"title": "문서2", "content": "b", "metadata": {"page_id": 2}},
                {"title": "문서3", "content": "c", "metadata": {"page_id": 3}},
            ],
            "debug": {},
        }

    monkeypatch.setattr(collect_node, "_search_wiki", _fake_search_wiki)

    state = {
        "claim_text": "테스트 주장",
        "search_queries": [{"type": "wiki", "text": "테스트 위키 쿼리"}],
    }

    out = await collect_node.run_wiki_async(state)
    diagnostics = out["stage03_wiki_diagnostics"]

    assert len(out["wiki_candidates"]) == 1
    assert diagnostics["wiki_result_cap"] == 1
    assert diagnostics["wiki_result_count"] == 1


@pytest.mark.asyncio
async def test_run_web_async_filters_blocked_domain_pattern_and_language(monkeypatch: pytest.MonkeyPatch):
    async def _fake_search_naver(query: str, limiter=None):  # noqa: ARG001
        return []

    async def _fake_search_ddg(query: str, limiter=None):  # noqa: ARG001
        return [
            {
                "source_type": "WEB_URL",
                "title": "중국어 사전 단어 뜻 정리",
                "url": "https://baidu.com/s?wd=test",
                "content": "这是一个测试页面 这是一个测试页面",
                "metadata": {"origin": "duckduckgo"},
            },
            {
                "source_type": "WEB_URL",
                "title": "도움말 FAQ 사용법 안내",
                "url": "https://example.com/help",
                "content": "사용법 안내",
                "metadata": {"origin": "duckduckgo"},
            },
            {
                "source_type": "WEB_URL",
                "title": "정상 결과",
                "url": "https://example.com/article",
                "content": "서울 매입임대 아파트 정책 관련 보도 내용",
                "metadata": {"origin": "duckduckgo"},
            },
        ]

    monkeypatch.setattr(collect_node, "_search_naver", _fake_search_naver)
    monkeypatch.setattr(collect_node, "_search_duckduckgo", _fake_search_ddg)

    state = {
        "search_queries": [
            {
                "type": "verification",
                "text": "서울 매입임대 아파트 정책 사실확인",
                "meta": {"claim_id": "C1", "intent": "fact_check", "mode": "mixed", "stance": "support"},
            }
        ]
    }

    out = await collect_node.run_web_async(state)
    diagnostics = out["stage03_web_diagnostics"]

    assert diagnostics["blocked_domain_count"] == 1
    assert diagnostics["blocked_pattern_count"] == 1
    assert diagnostics["blocked_language_count"] == 0
    assert diagnostics["web_result_count"] == 1
    assert len(out["web_candidates"]) == 1
    assert out["web_candidates"][0]["url"] == "https://example.com/article"
