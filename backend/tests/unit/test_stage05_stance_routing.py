from __future__ import annotations

import app.stages.stage05_topk.node as topk_node


def _candidate(title: str, score: float, stance: str, credibility: float) -> dict:
    return {
        "source_type": "WIKIPEDIA",
        "title": title,
        "url": f"wiki://page/{title}",
        "content": f"{title} 내용",
        "score": score,
        "metadata": {
            "claim_id": "C1",
            "intent": "entity_profile",
            "mode": "fact",
            "stance": stance,
            "credibility_score": credibility,
        },
    }


def test_stage05_soft_routing_builds_support_and_skeptic_pools(monkeypatch):
    monkeypatch.setattr(topk_node.settings, "stage5_soft_split_enabled", True)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_standard", 0.7)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_standard", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_support", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_skeptic", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_domain_cap", 0)
    monkeypatch.setattr(topk_node.settings, "stage5_shared_trust_min", 0.68)

    state = {
        "claim_mode": "fact",
        "claim_text": "테스트 주장",
        "risk_flags": [],
        "scored_evidence": [
            _candidate("support", 0.95, "support", 0.70),
            _candidate("skeptic", 0.94, "skeptic", 0.72),
            _candidate("neutral-high", 0.93, "neutral", 0.90),
            _candidate("neutral-low", 0.92, "neutral", 0.30),
        ],
    }

    out = topk_node.run(state)
    support_titles = [item["title"] for item in out["evidence_topk_support"]]
    skeptic_titles = [item["title"] for item in out["evidence_topk_skeptic"]]

    assert "support" in support_titles
    assert "skeptic" in skeptic_titles
    assert "neutral-high" in support_titles
    assert "neutral-high" in skeptic_titles
    assert "neutral-low" not in support_titles
    assert "neutral-low" not in skeptic_titles
    assert len(out["evidence_topk_support"]) == 2
    assert len(out["evidence_topk_skeptic"]) == 2
    assert out["topk_diagnostics"]["soft_split_enabled"] is True


def test_stage05_support_skeptic_target_k_override(monkeypatch):
    monkeypatch.setattr(topk_node.settings, "stage5_soft_split_enabled", True)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_standard", 0.7)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_standard", 4)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_support", 1)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_skeptic", 1)
    monkeypatch.setattr(topk_node.settings, "stage5_domain_cap", 0)
    monkeypatch.setattr(topk_node.settings, "stage5_shared_trust_min", 0.68)

    state = {
        "claim_mode": "fact",
        "claim_text": "테스트 주장",
        "risk_flags": [],
        "scored_evidence": [
            _candidate("support", 0.95, "support", 0.70),
            _candidate("skeptic", 0.94, "skeptic", 0.72),
            _candidate("neutral-high", 0.93, "neutral", 0.90),
        ],
    }

    out = topk_node.run(state)
    assert len(out["evidence_topk_support"]) == 1
    assert len(out["evidence_topk_skeptic"]) == 1
    assert out["topk_diagnostics"]["support_target_k"] == 1
    assert out["topk_diagnostics"]["skeptic_target_k"] == 1
