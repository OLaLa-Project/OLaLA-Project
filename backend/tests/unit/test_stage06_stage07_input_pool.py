from __future__ import annotations

from app.stages.stage06_verify_support.node import run as run_stage06
from app.stages.stage07_verify_skeptic.node import run as run_stage07


def _evidence(stance: str, credibility: float, intent: str = "direct") -> dict:
    return {
        "evid_id": f"ev_{stance}",
        "source_type": "NEWS",
        "title": f"{stance} evidence",
        "url": f"https://example.com/{stance}",
        "snippet": "snippet",
        "metadata": {
            "stance": stance,
            "credibility_score": credibility,
            "intent": intent,
            "claim_id": "C1",
            "mode": "rumor",
        },
    }


def test_stage06_uses_support_pool_first():
    state = {
        "trace_id": "t-06",
        "claim_text": "테스트 주장",
        "language": "ko",
        "claim_mode": "rumor",
        "risk_markers": [],
        "verification_priority": "high",
        "evidence_topk_support": [_evidence("support", 0.77)],
        "evidence_topk": [_evidence("neutral", 0.2), _evidence("neutral2", 0.3)],
    }
    out = run_stage06(state)
    diag = out["stage06_diagnostics"]
    assert diag["input_pool_type"] == "support"
    assert diag["total_evidence_count"] == 1
    assert diag["input_pool_avg_trust"] == 0.77


def test_stage07_uses_skeptic_pool_first():
    state = {
        "trace_id": "t-07",
        "claim_text": "테스트 주장",
        "language": "ko",
        "claim_mode": "rumor",
        "risk_markers": [],
        "verification_priority": "high",
        "evidence_topk_skeptic": [_evidence("skeptic", 0.81)],
        "evidence_topk": [_evidence("neutral", 0.2), _evidence("neutral2", 0.3)],
    }
    out = run_stage07(state)
    diag = out["stage07_diagnostics"]
    assert diag["input_pool_type"] == "skeptic"
    assert diag["total_evidence_count"] == 1
    assert diag["input_pool_avg_trust"] == 0.81

