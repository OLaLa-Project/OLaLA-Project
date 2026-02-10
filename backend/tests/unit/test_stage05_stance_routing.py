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


def test_stage05_does_not_clone_support_into_skeptic_when_empty(monkeypatch):
    monkeypatch.setattr(topk_node.settings, "stage5_soft_split_enabled", True)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_rumor", 0.7)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_rumor", 3)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_support", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_skeptic", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_domain_cap", 0)
    monkeypatch.setattr(topk_node.settings, "stage5_shared_trust_min", 0.95)

    state = {
        "claim_mode": "rumor",
        "claim_text": "테스트 주장",
        "risk_flags": [],
        "scored_evidence": [
            _candidate("support-a", 0.95, "support", 0.80),
            _candidate("support-b", 0.92, "support", 0.75),
        ],
    }

    out = topk_node.run(state)
    assert [item["title"] for item in out["evidence_topk_skeptic"]] == []
    assert "NO_SKEPTIC_EVIDENCE" in out["risk_flags"]
    assert "UNBALANCED_STANCE_EVIDENCE" in out["risk_flags"]
    assert out["topk_diagnostics"]["skeptic_selected_k"] == 0


def test_stage05_balances_rumor_topk_from_support_and_skeptic(monkeypatch):
    monkeypatch.setattr(topk_node.settings, "stage5_soft_split_enabled", True)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_rumor", 0.7)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_rumor", 4)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_support", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_skeptic", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_domain_cap", 0)
    monkeypatch.setattr(topk_node.settings, "stage5_shared_trust_min", 0.68)

    state = {
        "claim_mode": "rumor",
        "claim_text": "테스트 주장",
        "risk_flags": [],
        "scored_evidence": [
            _candidate("support-a", 0.96, "support", 0.82),
            _candidate("support-b", 0.92, "support", 0.78),
            _candidate("skeptic-a", 0.95, "skeptic", 0.84),
            _candidate("skeptic-b", 0.90, "skeptic", 0.76),
        ],
    }

    out = topk_node.run(state)
    titles = [item["title"] for item in out["evidence_topk"]]
    assert "support-a" in titles
    assert "skeptic-a" in titles
    assert out["topk_diagnostics"]["balanced_selection_used"] is True


def test_stage05_mixed_threshold_backoff_prevents_empty_topk(monkeypatch):
    monkeypatch.setattr(topk_node.settings, "stage5_soft_split_enabled", False)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_mixed", 0.55)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_backoff_step", 0.05)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_backoff_target_min", 3)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_backoff_min_mixed", 0.45)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_rumor", 3)
    monkeypatch.setattr(topk_node.settings, "stage5_domain_cap", 0)

    state = {
        "claim_mode": "mixed",
        "claim_text": "테스트 주장",
        "risk_flags": [],
        "scored_evidence": [
            _candidate("support-a", 0.58, "support", 0.82),
            _candidate("support-b", 0.53, "support", 0.78),
            _candidate("skeptic-a", 0.49, "skeptic", 0.74),
            _candidate("neutral-a", 0.30, "neutral", 0.70),
        ],
    }

    out = topk_node.run(state)
    diag = out["topk_diagnostics"]

    assert diag["base_threshold"] == 0.55
    assert diag["threshold"] == 0.45
    assert diag["threshold_backoff_steps"] == 2
    assert diag["thresholded_count"] == 3
    assert diag["selected_k"] == 3
    assert out["evidence_topk"]


def test_stage05_skeptic_rescue_uses_subthreshold_skeptic(monkeypatch):
    monkeypatch.setattr(topk_node.settings, "stage5_soft_split_enabled", True)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_mixed", 0.60)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_backoff_step", 0.0)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_rumor", 4)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_support", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_skeptic", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_domain_cap", 0)
    monkeypatch.setattr(topk_node.settings, "stage5_shared_trust_min", 0.95)
    monkeypatch.setattr(topk_node.settings, "stage5_skeptic_rescue_enabled", True)
    monkeypatch.setattr(topk_node.settings, "stage5_skeptic_rescue_min_score", 0.40)
    monkeypatch.setattr(topk_node.settings, "stage5_skeptic_rescue_max_items", 2)

    state = {
        "claim_mode": "mixed",
        "claim_text": "테스트 주장",
        "risk_flags": [],
        "scored_evidence": [
            _candidate("support-a", 0.66, "support", 0.80),
            _candidate("support-b", 0.64, "support", 0.78),
            _candidate("neutral-a", 0.63, "neutral", 0.60),
            _candidate("skeptic-rescue", 0.44, "skeptic", 0.72),
        ],
    }

    out = topk_node.run(state)
    skeptic_titles = [item["title"] for item in out["evidence_topk_skeptic"]]

    assert "skeptic-rescue" in skeptic_titles
    assert out["topk_diagnostics"]["skeptic_rescued_count"] == 1
    assert "SKEPTIC_RESCUE_USED" in out["risk_flags"]
    assert "NO_SKEPTIC_EVIDENCE" not in out["risk_flags"]


def test_stage05_threshold_failopen_selects_candidates_for_rumor(monkeypatch):
    monkeypatch.setattr(topk_node.settings, "stage5_soft_split_enabled", False)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_rumor", 0.68)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_backoff_step", 0.05)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_backoff_target_min", 4)
    monkeypatch.setattr(topk_node.settings, "stage5_threshold_backoff_min_rumor", 0.50)
    monkeypatch.setattr(topk_node.settings, "stage5_topk_rumor", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_domain_cap", 0)
    monkeypatch.setattr(topk_node.settings, "stage5_failopen_enabled", True)
    monkeypatch.setattr(topk_node.settings, "stage5_failopen_min_items", 2)
    monkeypatch.setattr(topk_node.settings, "stage5_failopen_min_score", 0.08)

    state = {
        "claim_mode": "rumor",
        "claim_text": "테스트 주장",
        "risk_flags": [],
        "scored_evidence": [
            _candidate("low-a", 0.31, "support", 0.72),
            _candidate("low-b", 0.29, "skeptic", 0.70),
        ],
    }

    out = topk_node.run(state)
    assert len(out["evidence_topk"]) == 2
    assert out["topk_diagnostics"]["threshold_failopen_used"] is True
    assert out["topk_diagnostics"]["threshold_failopen_added"] == 2
    assert "THRESHOLD_FAILOPEN_USED" in out["risk_flags"]
