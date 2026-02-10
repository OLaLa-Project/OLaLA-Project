import app.stages.stage04_score.node as score_node
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


def test_stage04_caps_high_score_when_overlap_is_low(monkeypatch):
    monkeypatch.setitem(score_node._SOURCE_PRIOR, "WEB_URL", 1.2)
    monkeypatch.setattr(score_node.settings, "stage4_low_overlap_threshold", 0.4)
    monkeypatch.setattr(score_node.settings, "stage5_threshold_rumor", 0.78)

    state = {
        "claim_text": "서울 매입임대 아파트",
        "claim_mode": "rumor",
        "evidence_candidates": [
            {
                "source_type": "WEB_URL",
                "title": "매입임대 정책 발표",
                "content": "정책 발표와 관련 없는 일반 브리핑 요약",
                "metadata": {
                    "intent": "official_statement",
                    "credibility_score": 1.0,
                    "source_trust_score": 1.0,
                    "html_signal_score": 1.0,
                },
            }
        ],
    }

    output = run(state)
    scored = output["scored_evidence"]
    assert len(scored) == 1
    assert scored[0]["score"] <= 0.78
    assert scored[0]["metadata"]["score_breakdown"]["overlap_cap_applied"] is True
    assert output["score_diagnostics"]["high_score_low_overlap_count"] == 1
