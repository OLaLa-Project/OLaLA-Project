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

