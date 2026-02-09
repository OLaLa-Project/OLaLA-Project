from app.stages.stage04_score.node import run


def test_stage04_scores_and_sorts_web_candidates():
    state = {
        "claim_text": "코로나 백신 효과",
        "evidence_candidates": [
            {
                "source_type": "WEB_URL",
                "title": "코로나 백신 효과 분석",
                "content": "코로나 백신 효과 연구 결과를 정리한 기사입니다.",
            },
            {
                "source_type": "WEB_URL",
                "title": "무관한 기사",
                "content": "경제 뉴스 요약입니다.",
            },
        ],
    }

    output = run(state)

    assert output["evidence_candidates"] is None
    scored = output["scored_evidence"]
    assert len(scored) == 2
    assert all("score" in item for item in scored)
    assert scored[0]["score"] > scored[1]["score"]


def test_stage04_skips_non_dict_candidates():
    state = {
        "claim_text": "테스트 주장",
        "evidence_candidates": [
            None,
            "invalid",
            {"source_type": "WEB_URL", "title": "정상", "content": "테스트 주장 포함"},
        ],
    }

    output = run(state)

    assert len(output["scored_evidence"]) == 1
    assert output["scored_evidence"][0]["title"] == "정상"


def test_stage04_prefers_higher_credibility_when_relevance_similar():
    state = {
        "claim_text": "전혀다른 키워드",
        "evidence_candidates": [
            {
                "source_type": "NEWS",
                "title": "일반 정책 보도",
                "content": "정책 발표 내용을 정리한 기사 본문입니다.",
                "metadata": {
                    "intent": "official_statement",
                    "credibility_score": 0.9,
                    "source_trust_score": 0.9,
                    "html_signal_score": 0.8,
                    "source_tier": "major_news",
                },
            },
            {
                "source_type": "NEWS",
                "title": "일반 정책 보도",
                "content": "정책 발표 내용을 정리한 기사 본문입니다.",
                "metadata": {
                    "intent": "official_statement",
                    "credibility_score": 0.2,
                    "source_trust_score": 0.3,
                    "html_signal_score": 0.2,
                    "source_tier": "unknown",
                },
            },
        ],
    }

    output = run(state)
    scored = output["scored_evidence"]
    assert len(scored) == 2
    assert scored[0]["metadata"]["credibility_score"] > scored[1]["metadata"]["credibility_score"]
    assert scored[0]["score"] > scored[1]["score"]
