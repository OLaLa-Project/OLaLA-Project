from __future__ import annotations

import app.stages.stage03_collect.node as collect_node
from app.stages._shared import html_signals
from app.stages._shared.source_trust import build_source_trust


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def test_source_tier_classification_for_government_domain():
    trust = build_source_trust(url="https://www.mois.go.kr/example", source_type="NEWS")
    assert trust["source_tier"] == "government"
    assert float(trust["source_trust_score"]) > 0.9


def test_html_signal_fetch_failure_returns_neutral(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(html_signals.requests, "get", _raise)
    result = html_signals.analyze_html_signals(
        url="https://example.com/news/1",
        title="일반 기사",
        snippet="본문",
        timeout_seconds=0.1,
    )
    assert result["fetch_ok"] is False
    assert float(result["html_signal_score"]) == 0.5


def test_html_signal_detects_byline_date_reference(monkeypatch):
    html = """
    <html>
      <head>
        <meta name="author" content="홍길동 기자">
        <meta property="article:published_time" content="2026-02-08T12:00:00+09:00">
      </head>
      <body>
        <p>정정: 일부 표현을 수정합니다.</p>
        <a href="https://www.kostat.go.kr/statistics">통계 원문</a>
        <p>정부 발표에 따르면 ...</p>
      </body>
    </html>
    """

    monkeypatch.setattr(
        html_signals.requests,
        "get",
        lambda *_args, **_kwargs: _FakeResponse(html, status_code=200),
    )
    result = html_signals.analyze_html_signals(
        url="https://example.com/news/2",
        title="정책 브리핑",
        snippet="근거가 충분한 기사입니다.",
        timeout_seconds=0.1,
    )

    assert result["fetch_ok"] is True
    assert result["byline_present"] is True
    assert result["date_present"] is True
    assert result["correction_notice_present"] is True
    assert result["reference_link_count"] >= 1
    assert float(result["html_signal_score"]) > 0.6


def test_run_merge_populates_credibility_and_stats(monkeypatch):
    monkeypatch.setattr(collect_node.settings, "stage3_html_signal_enabled", True)
    monkeypatch.setattr(collect_node.settings, "stage3_html_signal_top_n", 5)
    monkeypatch.setattr(
        collect_node,
        "analyze_html_signals",
        lambda **_kwargs: {
            "fetch_ok": True,
            "html_signal_score": 0.8,
            "breakdown": {"stub": 1.0},
        },
    )

    state = {
        "claim_text": "테스트 주장",
        "canonical_evidence": {"source_url": "", "article_title": ""},
        "wiki_candidates": [],
        "web_candidates": [
            {
                "source_type": "NEWS",
                "title": "테스트 기사 제목",
                "url": "https://www.yna.co.kr/view/AKR20260208000100001",
                "content": "충분히 긴 기사 본문입니다. 신뢰도 평가를 위한 테스트 텍스트가 포함되어 있습니다.",
                "metadata": {"intent": "official_statement", "claim_id": "C1", "mode": "fact", "stance": "support"},
            }
        ],
    }

    out = collect_node.run_merge(state)
    assert out["evidence_candidates"]
    item = out["evidence_candidates"][0]
    meta = item["metadata"]
    assert "source_tier" in meta
    assert "source_trust_score" in meta
    assert "html_signal_score" in meta
    assert "credibility_score" in meta
    stats = out["stage03_merge_stats"]
    assert "html_enriched_count" in stats
    assert "html_fetch_fail_count" in stats
    assert "tier_distribution" in stats

