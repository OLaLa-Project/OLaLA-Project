from __future__ import annotations

import app.graph.graph as graph_module


def test_build_queries_enforces_wiki_single_vector_and_claim_cap(monkeypatch):
    monkeypatch.setattr(graph_module.settings, "stage3_web_query_cap_per_claim", 3)

    state = {
        "claim_mode": "mixed",
        "claim_text": "테스트 주장",
        "entity_map": {"extracted": ["금융당국", "가상자산 거래소"]},
        "search_constraints": {"date_range": "recent"},
        "query_variants": [
            {
                "type": "wiki",
                "text": "첫 번째 위키 문장",
                "meta": {"claim_id": "C1", "intent": "entity_profile", "mode": "mixed", "stance": "neutral"},
            },
            {
                "type": "wiki",
                "text": "두 번째 위키 문장",
                "meta": {"claim_id": "C1", "intent": "entity_profile", "mode": "mixed", "stance": "neutral"},
            },
            {
                "type": "news",
                "text": "금융당국의 공식 입장을 확인해야 한다",
                "meta": {"claim_id": "C1", "intent": "official_statement", "mode": "mixed", "stance": "support"},
            },
            {
                "type": "verification",
                "text": "핵심 사실 여부를 검증해야 한다",
                "meta": {"claim_id": "C1", "intent": "fact_check", "mode": "mixed", "stance": "skeptic"},
            },
            {
                "type": "web",
                "text": "최초 유포 경로와 원출처를 찾는다",
                "meta": {"claim_id": "C1", "intent": "origin_trace", "mode": "mixed", "stance": "neutral"},
            },
            {
                "type": "direct",
                "text": "이 문장은 cap 때문에 제외되어야 한다",
                "meta": {"claim_id": "C1", "intent": "direct", "mode": "mixed", "stance": "neutral"},
            },
            {
                "type": "news",
                "text": "두 번째 주장 공식입장",
                "meta": {"claim_id": "C2", "intent": "official_statement", "mode": "mixed", "stance": "support"},
            },
            {
                "type": "verification",
                "text": "두 번째 주장 사실확인",
                "meta": {"claim_id": "C2", "intent": "fact_check", "mode": "mixed", "stance": "skeptic"},
            },
        ],
    }

    out = graph_module._build_queries(state)
    search_queries = out.get("search_queries", [])

    wiki_queries = [item for item in search_queries if item.get("type") == "wiki"]
    assert len(wiki_queries) == 1
    assert wiki_queries[0].get("search_mode") == "vector"
    assert wiki_queries[0].get("meta", {}).get("query_strategy") == "wiki_vector_single"
    assert wiki_queries[0].get("meta", {}).get("anchor_tokens")

    non_wiki = [item for item in search_queries if item.get("type") != "wiki"]
    grouped: dict[str, list[dict]] = {}
    for item in non_wiki:
        claim_id = str((item.get("meta") or {}).get("claim_id") or "__global__")
        grouped.setdefault(claim_id, []).append(item)

    assert len(grouped.get("C1", [])) <= 3
    intents_c1 = {str((item.get("meta") or {}).get("intent") or "") for item in grouped.get("C1", [])}
    assert {"official_statement", "fact_check", "origin_trace"} <= intents_c1

    for item in non_wiki:
        text = str(item.get("text") or "")
        meta = item.get("meta", {})
        assert meta.get("query_strategy") == "keyword_focus"
        assert isinstance(meta.get("keyword_tokens"), list)
        assert isinstance(meta.get("anchor_tokens"), list)
        assert isinstance(meta.get("dropped_tokens"), list)
        assert isinstance(meta.get("quality_flags"), list)
        assert len(text) <= 50
