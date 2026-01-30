"""
Schema Transformer.

기존 스키마와 Gateway 스키마 간의 변환을 담당합니다.
스키마 불일치 문제를 해결하는 핵심 컴포넌트입니다.
"""

import logging
from typing import Dict, Any, List, Optional

from .common import SourceType
from .evidence import (
    EvidenceCandidate,
    ScoredEvidence,
    Citation,
    EvidenceMetadata,
    filter_top_k,
)
from .verdict import (
    Stance,
    DraftVerdict,
    AggregatedVerdict,
    FinalVerdict,
    VerdictCitation,
)

logger = logging.getLogger(__name__)


class SchemaTransformer:
    """
    스키마 변환기.

    기존 Stage 출력 형식을 Gateway 스키마로 변환하고,
    Gateway 스키마를 기존 형식으로 변환합니다.

    사용 예:
        transformer = SchemaTransformer()

        # Stage 3 raw → EvidenceCandidate
        candidates = transformer.transform_evidence_candidates(raw_list)

        # Stage 4 scoring 결과 적용
        scored = transformer.apply_scores(candidates, scores)

        # Stage 5 Top-K 선정
        citations = transformer.select_top_k(scored, threshold=0.7, top_k=6)
    """

    def __init__(self, snippet_max_length: int = 500):
        self.snippet_max_length = snippet_max_length

    # ─────────────────────────────────────────────
    # Evidence 변환 (Stage 3 → 4 → 5)
    # ─────────────────────────────────────────────

    def transform_evidence_candidates(
        self,
        raw_candidates: List[Dict[str, Any]],
    ) -> List[EvidenceCandidate]:
        """
        Stage 3 raw 출력을 EvidenceCandidate로 변환.

        기존 형식:
        {
            "source_type": "KNOWLEDGE_BASE" | "NEWS" | "WEB",
            "title": str,
            "url": str,
            "content": str,
            "metadata": {...}
        }

        변환 후:
        - evid_id 자동 생성
        - snippet 자동 생성
        - source_type 정규화
        """
        results = []

        for raw in raw_candidates:
            try:
                # EvidenceCandidate 생성 (자동 정규화됨)
                candidate = EvidenceCandidate(
                    source_type=raw.get("source_type", "WEB"),
                    title=raw.get("title", ""),
                    url=raw.get("url", ""),
                    content=raw.get("content", ""),
                    metadata=raw.get("metadata", {}),
                )
                results.append(candidate)

            except Exception as e:
                logger.warning(f"Failed to transform evidence candidate: {e}")
                continue

        logger.debug(f"Transformed {len(results)}/{len(raw_candidates)} candidates")
        return results

    def apply_scores(
        self,
        candidates: List[EvidenceCandidate],
        scores: List[float],
    ) -> List[ScoredEvidence]:
        """
        EvidenceCandidate에 점수를 적용하여 ScoredEvidence 생성.

        Stage 4 결과 적용용.
        """
        if len(candidates) != len(scores):
            logger.warning(
                f"Candidate/score count mismatch: {len(candidates)} vs {len(scores)}"
            )
            # 부족한 경우 0.0으로 채움
            scores = scores + [0.0] * (len(candidates) - len(scores))

        return [
            ScoredEvidence.from_candidate(c, s)
            for c, s in zip(candidates, scores)
        ]

    def select_top_k(
        self,
        scored_evidence: List[ScoredEvidence],
        threshold: float = 0.7,
        top_k: int = 6,
    ) -> List[Citation]:
        """
        Top-K 선정.

        Stage 5 로직.
        """
        return filter_top_k(scored_evidence, threshold, top_k)

    def citations_to_state(
        self,
        citations: List[Citation],
    ) -> List[Dict[str, Any]]:
        """
        Citation 리스트를 state 저장용 딕셔너리로 변환.

        Stage 5 출력 형식 (evidence_topk, citations 필드).
        """
        return [c.to_dict() for c in citations]

    # ─────────────────────────────────────────────
    # State 호환 변환
    # ─────────────────────────────────────────────

    def state_to_citations(
        self,
        state_citations: List[Dict[str, Any]],
    ) -> List[Citation]:
        """
        state의 citations/evidence_topk를 Citation 객체로 변환.

        기존 스키마 호환:
        - content → snippet (없으면 content 사용)
        - evid_id 자동 생성 (없으면)
        """
        results = []

        for i, raw in enumerate(state_citations):
            try:
                # content/snippet 호환
                content = raw.get("content", "")
                snippet = raw.get("snippet", "")
                if not snippet and content:
                    snippet = EvidenceCandidate.create_snippet(
                        content, self.snippet_max_length
                    )

                # evid_id 호환
                evid_id = raw.get("evid_id", "")
                if not evid_id:
                    evid_id = EvidenceCandidate.generate_evid_id(
                        raw.get("url", ""), raw.get("title", "")
                    )

                citation = Citation(
                    evid_id=evid_id,
                    source_type=raw.get("source_type", "WEB"),
                    title=raw.get("title", ""),
                    url=raw.get("url", ""),
                    content=content,
                    snippet=snippet,
                    quote=raw.get("quote"),
                    score=raw.get("score", 0.0),
                    relevance=raw.get("relevance"),
                    metadata=raw.get("metadata", {}),
                )
                results.append(citation)

            except Exception as e:
                logger.warning(f"Failed to convert state citation {i}: {e}")
                continue

        return results

    # ─────────────────────────────────────────────
    # Verdict 변환 (Stage 6 → 7 → 8 → 9)
    # ─────────────────────────────────────────────

    def parse_slm_verdict(
        self,
        raw_verdict: Dict[str, Any],
        available_citations: List[Citation],
        perspective: str = None,
    ) -> DraftVerdict:
        """
        SLM 출력을 DraftVerdict로 변환.

        Stage 6/7 결과 파싱용.
        citation 검증도 수행합니다.
        """
        # 기본 필드 추출
        stance = Stance.from_string(raw_verdict.get("stance", "UNVERIFIED"))
        confidence = max(0.0, min(1.0, float(raw_verdict.get("confidence", 0.0))))

        # Citation 검증
        validated_citations = self._validate_citations(
            raw_verdict.get("citations", []),
            available_citations,
        )

        verdict = DraftVerdict(
            stance=stance,
            confidence=confidence,
            reasoning_bullets=raw_verdict.get("reasoning_bullets", []),
            citations=validated_citations,
            weak_points=raw_verdict.get("weak_points", []),
            followup_queries=raw_verdict.get("followup_queries", []),
            perspective=perspective,
        )

        # citations가 없으면 UNVERIFIED 강제
        return verdict.enforce_unverified_if_no_citations()

    def _validate_citations(
        self,
        raw_citations: List[Dict[str, Any]],
        available_citations: List[Citation],
        min_quote_length: int = 10,
    ) -> List[VerdictCitation]:
        """
        SLM이 생성한 citation을 검증.

        evid_id가 available_citations에 있고,
        quote가 해당 증거의 content/snippet에 포함되어야 통과.
        """
        if not raw_citations:
            return []

        # evid_id → Citation 매핑
        citation_map = {c.evid_id: c for c in available_citations}

        validated = []
        for raw_cit in raw_citations:
            evid_id = raw_cit.get("evid_id", "")
            quote = raw_cit.get("quote", "")

            # 기본 검증
            if not evid_id or not quote:
                logger.debug(f"Citation missing required fields: evid_id={bool(evid_id)}, quote={bool(quote)}")
                continue

            if len(quote) < min_quote_length:
                logger.debug(f"Quote too short: {len(quote)} chars")
                continue

            # evid_id 존재 확인
            if evid_id not in citation_map:
                logger.debug(f"evid_id not found in available citations: {evid_id}")
                continue

            # quote 검증 (content 또는 snippet에 포함)
            source_cit = citation_map[evid_id]
            normalized_quote = self._normalize_text(quote)
            normalized_content = self._normalize_text(source_cit.content)
            normalized_snippet = self._normalize_text(source_cit.snippet)

            if normalized_quote not in normalized_content and normalized_quote not in normalized_snippet:
                logger.warning(f"Quote not found in evidence: evid_id={evid_id}")
                continue

            # 검증 통과
            validated.append(VerdictCitation(
                evid_id=evid_id,
                quote=quote,
                supports=raw_cit.get("supports", True),
            ))
            logger.debug(f"Citation validated: evid_id={evid_id}")

        logger.info(f"Citation validation: {len(validated)}/{len(raw_citations)} passed")
        return validated

    @staticmethod
    def _normalize_text(text: str) -> str:
        """텍스트 정규화 (공백, 대소문자)."""
        return " ".join((text or "").split()).lower()

    def aggregate_verdicts(
        self,
        support_verdict: DraftVerdict,
        skeptic_verdict: DraftVerdict,
    ) -> AggregatedVerdict:
        """
        지지/회의적 판정을 병합.

        Stage 8 로직.
        """
        return AggregatedVerdict.from_verdicts(support_verdict, skeptic_verdict)

    def finalize_verdict(
        self,
        aggregated: AggregatedVerdict,
        quality_threshold: int = 65,
    ) -> FinalVerdict:
        """
        최종 판정 생성.

        Stage 9 로직 (Quality Gate 적용).
        """
        return FinalVerdict.from_aggregated(aggregated, quality_threshold)

    # ─────────────────────────────────────────────
    # API 응답 변환
    # ─────────────────────────────────────────────

    def citations_to_api_format(
        self,
        citations: List[Citation],
    ) -> List[Dict[str, Any]]:
        """
        Citation을 API 응답 형식으로 변환.

        TruthCheckResponse.citations 형식.
        """
        return [c.to_api_dict() for c in citations]

    def verdict_to_api_format(
        self,
        verdict: FinalVerdict,
        citations: List[Citation],
    ) -> Dict[str, Any]:
        """
        FinalVerdict를 API 응답 형식으로 변환.
        """
        return {
            "label": verdict.stance.value,
            "confidence": verdict.confidence,
            "summary": verdict.summary,
            "rationale": verdict.reasoning_bullets,
            "citations": self.citations_to_api_format(citations),
            "quality_score": verdict.quality_score,
        }


# 전역 transformer 인스턴스
_default_transformer: Optional[SchemaTransformer] = None


def get_transformer() -> SchemaTransformer:
    """기본 SchemaTransformer 반환."""
    global _default_transformer
    if _default_transformer is None:
        _default_transformer = SchemaTransformer()
    return _default_transformer
