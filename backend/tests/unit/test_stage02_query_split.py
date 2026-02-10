import app.stages.stage02_querygen.node as stage02_node
from app.stages.stage02_querygen.node import _dedupe_query_variants, _finalize_query_variants


def test_finalize_query_variants_ensures_support_and_skeptic_for_news_and_verification():
    result = {
        "core_fact": "테스트 주장",
        "query_variants": [
            {
                "type": "news",
                "text": "테스트 주장 뉴스",
                "meta": {"claim_id": "C1", "intent": "official_statement", "mode": "rumor"},
            },
            {
                "type": "verification",
                "text": "테스트 주장 팩트체크",
                "meta": {"claim_id": "C1", "intent": "fact_check", "mode": "rumor"},
            },
        ],
    }

    variants = _finalize_query_variants(
        result,
        normalized_claims=[{"claim_id": "C1", "주장": "테스트 주장"}],
        claim_mode="rumor",
        claim_text="테스트 주장",
    )

    def _stances(qtype: str) -> set[str]:
        out: set[str] = set()
        for item in variants:
            if item.get("type") != qtype:
                continue
            meta = item.get("meta", {})
            if meta.get("claim_id") == "C1":
                out.add(str(meta.get("stance")))
        return out

    assert {"support", "skeptic"} <= _stances("news")
    assert {"support", "skeptic"} <= _stances("verification")


def test_dedupe_keeps_same_text_when_stance_differs():
    variants = [
        {
            "type": "verification",
            "text": "동일 텍스트",
            "meta": {"claim_id": "C1", "intent": "fact_check", "mode": "rumor", "stance": "support"},
        },
        {
            "type": "verification",
            "text": "동일 텍스트",
            "meta": {"claim_id": "C1", "intent": "fact_check", "mode": "rumor", "stance": "skeptic"},
        },
    ]

    deduped = _dedupe_query_variants(variants)
    assert len(deduped) == 2


def test_finalize_query_variants_enforces_single_wiki_and_keyword_queries(monkeypatch):
    monkeypatch.setattr(stage02_node.settings, "stage2_enable_stance_split", False)
    monkeypatch.setattr(stage02_node.settings, "stage2_wiki_vector_single_enabled", True)
    monkeypatch.setattr(stage02_node.settings, "stage2_web_keyword_rewrite_enabled", True)

    result = {
        "core_fact": "금융당국은 장부 시스템 점검 계획을 밝혔다",
        "query_variants": [
            {
                "type": "wiki",
                "text": "장부 시스템 오류와 거래소 리스크를 설명하는 위키 검색 문장",
                "meta": {"claim_id": "C1", "intent": "entity_profile", "mode": "fact", "stance": "neutral"},
            },
            {
                "type": "wiki",
                "text": "중복 위키 문장",
                "meta": {"claim_id": "C1", "intent": "entity_profile", "mode": "fact", "stance": "neutral"},
            },
            {
                "type": "news",
                "text": "금융당국은 이번 사태를 계기로 가상자산 거래소의 장부 시스템 규제를 강화하고 인허가 심사에 반영할 계획이다.",
                "meta": {"claim_id": "C1", "intent": "official_statement", "mode": "fact", "stance": "support"},
            },
            {
                "type": "verification",
                "text": "유령 코인 지급 사태의 원인 분석 및 거래소 내부통제 구조적 문제점에 대한 검증",
                "meta": {"claim_id": "C1", "intent": "fact_check", "mode": "fact", "stance": "skeptic"},
            },
            {
                "type": "web",
                "text": "거래소 장부 시스템 오류 사태의 최초 유포 경로와 원출처를 추적한다",
                "meta": {"claim_id": "C1", "intent": "origin_trace", "mode": "fact", "stance": "neutral"},
            },
        ],
    }

    variants = _finalize_query_variants(
        result,
        normalized_claims=[{"claim_id": "C1", "주장": "금융당국은 장부 시스템 점검 계획을 밝혔다"}],
        claim_mode="fact",
        claim_text="금융당국은 장부 시스템 점검 계획을 밝혔다",
        entity_map={"extracted": ["금융당국", "가상자산 거래소"]},
    )

    wiki_items = [item for item in variants if item.get("type") == "wiki"]
    assert len(wiki_items) == 1
    wiki_meta = wiki_items[0].get("meta", {})
    assert wiki_meta.get("intent") == "entity_profile"
    assert wiki_meta.get("stance") == "neutral"
    assert wiki_meta.get("query_strategy") == "wiki_vector_single"
    assert isinstance(wiki_meta.get("anchor_tokens"), list)
    assert wiki_meta.get("anchor_tokens")

    for qtype in ("news", "verification", "web"):
        typed = [item for item in variants if item.get("type") == qtype]
        assert typed
        for item in typed:
            text = str(item.get("text") or "")
            assert len(text.split()) >= 2
            assert ":" not in text and "," not in text and "." not in text
            meta = item.get("meta", {})
            assert meta.get("query_strategy") == "keyword_focus"
            assert isinstance(meta.get("keyword_tokens"), list)
            assert meta.get("keyword_tokens")
            assert isinstance(meta.get("quality_flags"), list)
            assert isinstance(meta.get("anchor_tokens"), list)
