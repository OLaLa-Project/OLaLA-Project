from __future__ import annotations

import app.stages.stage09_judge.node as judge_node


def _base_parsed(label: str) -> dict:
    return {
        "verdict_label": label,
        "confidence_percent": 88,
        "evaluation": {
            "hallucination_count": 0,
            "grounding_score": 0.95,
            "is_consistent": True,
            "policy_violations": [],
        },
        "risk_flags": [],
        "selected_evidence_ids": ["ev1"],
        "evidence_summary": [
            {"point": "근거", "source_title": "출처", "source_url": "https://example.com"}
        ],
        "explanation": "설명",
    }


def test_postprocess_downgrades_to_unverified_when_trust_low(monkeypatch):
    monkeypatch.setattr(judge_node.settings, "stage9_min_evidence_trust", 0.58)
    monkeypatch.setattr(judge_node.settings, "stage9_unverified_confidence_cap", 35)

    parsed = _base_parsed("TRUE")
    support_pack = {"confidence": 0.9, "citations": [{"evid_id": "ev1"}]}
    skeptic_pack = {"confidence": 0.2, "citations": []}
    evidence_index = {"ev1": {"intent": "official_statement", "credibility_score": 0.2}}

    out = judge_node._postprocess_judge_result(parsed, support_pack, skeptic_pack, evidence_index, "fact")
    assert out["verdict_label"] == "UNVERIFIED"
    assert out["confidence_percent"] <= 35
    assert "LOW_TRUST_EVIDENCE" in out["risk_flags"]


def test_postprocess_keeps_label_when_trust_high(monkeypatch):
    monkeypatch.setattr(judge_node.settings, "stage9_min_evidence_trust", 0.58)

    parsed = _base_parsed("TRUE")
    support_pack = {"confidence": 0.9, "citations": [{"evid_id": "ev1"}]}
    skeptic_pack = {"confidence": 0.2, "citations": []}
    evidence_index = {"ev1": {"intent": "official_statement", "credibility_score": 0.92}}

    out = judge_node._postprocess_judge_result(parsed, support_pack, skeptic_pack, evidence_index, "fact")
    assert out["verdict_label"] == "TRUE"
    assert "LOW_TRUST_EVIDENCE" not in out["risk_flags"]


def test_build_judge_prompt_uses_stage_summary_only(monkeypatch):
    monkeypatch.setattr(judge_node.settings, "stage9_prompt_evidence_limit", 2)
    monkeypatch.setattr(judge_node.settings, "stage9_prompt_snippet_max_chars", 50)
    monkeypatch.setattr(judge_node.settings, "stage9_prompt_pack_citation_limit", 1)
    monkeypatch.setattr(judge_node.settings, "stage9_prompt_pack_text_max_chars", 60)
    monkeypatch.setattr(judge_node.settings, "stage9_prompt_retrieval_limit", 1)

    long_snippet = "A" * 400
    support_pack = {
        "stance": "TRUE",
        "confidence": 0.9,
        "reasoning_bullets": ["reason-1", "reason-2"],
        "weak_points": ["weak-1"],
        "citations": [{"evid_id": "ev1", "title": "title1", "url": "https://a", "quote": long_snippet}],
        "analysis_meta": {"mode": "fact", "citation_count": 1, "has_required_intent": True},
    }
    skeptic_pack = {
        "stance": "FALSE",
        "confidence": 0.3,
        "reasoning_bullets": ["reason-s"],
        "weak_points": [],
        "citations": [{"evid_id": "ev2", "title": "title2", "url": "https://b", "quote": long_snippet}],
        "analysis_meta": {"mode": "fact", "citation_count": 1, "has_required_intent": True},
    }
    evidence_index = {
        "ev1": {
            "evid_id": "ev1",
            "title": "evidence1",
            "url": "https://a",
            "snippet": long_snippet,
            "intent": "fact_check",
            "claim_id": "C1",
            "mode": "fact",
            "query_stance": "support",
            "pre_score": 0.95,
            "credibility_score": 0.82,
            "source_tier": "major_news",
            "source_domain": "a.com",
            "metadata": {"pre_score_breakdown": {"x": 1}},
        },
        "ev2": {
            "evid_id": "ev2",
            "title": "evidence2",
            "url": "https://b",
            "snippet": long_snippet,
            "intent": "fact_check",
            "claim_id": "C1",
            "mode": "fact",
            "query_stance": "skeptic",
            "pre_score": 0.91,
            "credibility_score": 0.73,
            "source_tier": "major_news",
            "source_domain": "b.com",
        },
        "ev3": {
            "evid_id": "ev3",
            "title": "evidence3",
            "url": "https://c",
            "snippet": "unused",
            "intent": "entity_profile",
            "claim_id": "C2",
            "mode": "fact",
            "query_stance": "neutral",
            "pre_score": 0.99,
            "credibility_score": 0.91,
        },
    }

    prompt = judge_node._build_judge_user_prompt(
        claim_text="테스트 주장",
        support_pack=support_pack,
        skeptic_pack=skeptic_pack,
        evidence_index=evidence_index,
        retrieval_sources=[],
        language="ko",
        claim_profile={"claim_mode": "fact", "risk_markers": [], "verification_priority": "normal"},
        judge_prep_meta={"support_citation_count": 1, "skeptic_citation_count": 1},
    )

    assert "\"ev1\"" in prompt
    assert "\"ev2\"" in prompt
    assert "\"ev3\"" not in prompt
    assert "pre_score_breakdown" not in prompt
    assert "A" * 120 not in prompt
    assert "## Stage8 (집계) 요약" in prompt
    assert "## evidence_index (evid_id 기준 테이블)" not in prompt
    assert "## retrieval_evidence (Judge 별도 검색)" not in prompt


def test_postprocess_forces_unverified_when_no_verified_citations(monkeypatch):
    monkeypatch.setattr(judge_node.settings, "stage9_no_evidence_confidence_cap", 20)
    monkeypatch.setattr(judge_node.settings, "stage9_no_evidence_grounding_cap", 0.2)

    parsed = _base_parsed("TRUE")
    parsed["confidence_percent"] = 85
    parsed["selected_evidence_ids"] = ["ev_xxxxxxxx"]
    support_pack = {"confidence": 0.9, "citations": []}
    skeptic_pack = {"confidence": 0.1, "citations": []}
    evidence_index = {"ev1": {"intent": "official_statement", "credibility_score": 0.9}}

    out = judge_node._postprocess_judge_result(parsed, support_pack, skeptic_pack, evidence_index, "fact")
    assert out["verdict_label"] == "UNVERIFIED"
    assert out["confidence_percent"] <= 20
    assert out["evaluation"]["grounding_score"] <= 0.2
    assert "NO_VERIFIED_CITATIONS" in out["risk_flags"]


def test_postprocess_downgrades_when_label_explanation_conflict(monkeypatch):
    monkeypatch.setattr(judge_node.settings, "stage9_unverified_confidence_cap", 35)
    monkeypatch.setattr(judge_node.settings, "stage9_self_contradiction_grounding_cap", 0.4)

    parsed = _base_parsed("TRUE")
    parsed["confidence_percent"] = 85
    parsed["explanation"] = "해당 주장은 사실이 아닙니다."
    support_pack = {"confidence": 0.9, "citations": [{"evid_id": "ev1"}]}
    skeptic_pack = {"confidence": 0.2, "citations": []}
    evidence_index = {"ev1": {"intent": "official_statement", "credibility_score": 0.92}}

    out = judge_node._postprocess_judge_result(parsed, support_pack, skeptic_pack, evidence_index, "fact")
    assert out["verdict_label"] == "UNVERIFIED"
    assert out["confidence_percent"] <= 35
    assert out["evaluation"]["grounding_score"] <= 0.4
    assert "JUDGE_SELF_CONTRADICTION" in out["risk_flags"]


def test_run_skips_llm_when_no_verified_citations(monkeypatch):
    monkeypatch.setattr(judge_node.settings, "stage9_no_evidence_confidence_cap", 20)
    monkeypatch.setattr(judge_node.settings, "stage9_no_evidence_grounding_cap", 0.2)

    state = {
        "trace_id": "trace-no-citations",
        "claim_text": "테스트 주장",
        "language": "ko",
        "support_pack": {"stance": "UNVERIFIED", "confidence": 0.0, "citations": []},
        "skeptic_pack": {"stance": "UNVERIFIED", "confidence": 0.0, "citations": []},
        "evidence_index": {},
        "judge_prep_meta": {
            "claim_profile": {"claim_mode": "fact", "risk_markers": [], "verification_priority": "normal"},
            "support_citation_count": 0,
            "skeptic_citation_count": 0,
        },
        "risk_flags": [],
    }

    out = judge_node.run(state)
    assert out["final_verdict"]["label"] == "UNVERIFIED"
    assert out["user_result"]["verdict"]["label"] == "UNVERIFIED"
    assert out["stage09_diagnostics"]["fallback_reason"] == "no_verified_citations_skip_judge"
    assert out["stage09_diagnostics"]["final_confidence_percent"] <= 20
    assert "NO_VERIFIED_CITATIONS" in out["risk_flags"]
