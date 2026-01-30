"""
Verdict Schemas.

Stage 6-9에서 사용하는 판정 관련 스키마입니다.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator


class Stance(str, Enum):
    """판정 결과."""

    TRUE = "TRUE"
    """사실"""

    FALSE = "FALSE"
    """거짓"""

    MIXED = "MIXED"
    """혼합 (일부 사실, 일부 거짓)"""

    UNVERIFIED = "UNVERIFIED"
    """검증 불가"""

    REFUSED = "REFUSED"
    """거부됨 (부적절한 요청)"""

    @classmethod
    def from_string(cls, value: str) -> "Stance":
        """문자열에서 Stance로 변환."""
        value = (value or "UNVERIFIED").upper().strip()
        try:
            return cls(value)
        except ValueError:
            return cls.UNVERIFIED


class VerdictCitation(BaseModel):
    """
    판정에 사용된 인용.

    SLM이 생성한 인용 정보입니다.
    """

    evid_id: str = Field(..., description="증거 ID")
    """참조하는 증거 ID"""

    quote: str = Field(default="", description="인용문")
    """증거에서 발췌한 인용문"""

    supports: bool = Field(default=True)
    """지지 여부 (True: 지지, False: 반박)"""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evid_id": self.evid_id,
            "quote": self.quote,
            "supports": self.supports,
        }


class DraftVerdict(BaseModel):
    """
    Stage 6/7 출력 스키마: 초안 판정.

    지지/회의적 관점에서 생성된 개별 판정입니다.
    """

    stance: Stance = Field(default=Stance.UNVERIFIED)
    """판정 결과"""

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """확신도 (0.0 ~ 1.0)"""

    reasoning_bullets: List[str] = Field(default_factory=list)
    """판단 근거 (bullet point)"""

    citations: List[VerdictCitation] = Field(default_factory=list)
    """인용 정보"""

    weak_points: List[str] = Field(default_factory=list)
    """약점/한계"""

    followup_queries: List[str] = Field(default_factory=list)
    """후속 검증 질문"""

    perspective: Optional[str] = None
    """관점 (supportive/skeptical)"""

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """필드 정규화."""
        # stance 정규화
        if isinstance(values.get("stance"), str):
            values["stance"] = Stance.from_string(values["stance"])

        # confidence 범위 제한
        if values.get("confidence"):
            values["confidence"] = max(0.0, min(1.0, float(values["confidence"])))

        # citations 정규화
        if values.get("citations"):
            citations = []
            for cit in values["citations"]:
                if isinstance(cit, dict):
                    citations.append(VerdictCitation(**cit))
                elif isinstance(cit, VerdictCitation):
                    citations.append(cit)
            values["citations"] = citations

        return values

    @classmethod
    def create_fallback(cls, reason: str, perspective: str = None) -> "DraftVerdict":
        """오류 시 fallback verdict 생성."""
        return cls(
            stance=Stance.UNVERIFIED,
            confidence=0.0,
            reasoning_bullets=[f"[시스템 오류] {reason}"],
            citations=[],
            weak_points=["처리 중 오류 발생"],
            followup_queries=[],
            perspective=perspective,
        )

    def enforce_unverified_if_no_citations(self) -> "DraftVerdict":
        """citations가 없으면 UNVERIFIED로 강제."""
        if not self.citations and self.stance != Stance.UNVERIFIED:
            self.stance = Stance.UNVERIFIED
            self.confidence = 0.0
            self.reasoning_bullets.insert(
                0, "[시스템] 검증된 인용이 없어 UNVERIFIED로 처리됨"
            )
        return self

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "stance": self.stance.value,
            "confidence": self.confidence,
            "reasoning_bullets": self.reasoning_bullets,
            "citations": [c.to_dict() for c in self.citations],
            "weak_points": self.weak_points,
            "followup_queries": self.followup_queries,
            "perspective": self.perspective,
        }


class AggregatedVerdict(BaseModel):
    """
    Stage 8 출력 스키마: 병합된 판정.

    지지 + 회의적 판정을 병합한 결과입니다.
    """

    stance: Stance = Field(default=Stance.UNVERIFIED)
    """최종 판정"""

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """확신도"""

    reasoning_bullets: List[str] = Field(default_factory=list)
    """병합된 근거"""

    citations: List[VerdictCitation] = Field(default_factory=list)
    """병합된 인용"""

    weak_points: List[str] = Field(default_factory=list)
    """약점"""

    followup_queries: List[str] = Field(default_factory=list)
    """후속 질문"""

    support_stance: Optional[Stance] = None
    """지지 관점 판정"""

    skeptic_stance: Optional[Stance] = None
    """회의적 관점 판정"""

    agreement_level: float = Field(default=0.0, ge=0.0, le=1.0)
    """합의 수준 (1.0 = 완전 합의)"""

    quality_score: int = Field(default=0, ge=0, le=100)
    """품질 점수"""

    @classmethod
    def from_verdicts(
        cls,
        support: DraftVerdict,
        skeptic: DraftVerdict,
    ) -> "AggregatedVerdict":
        """두 판정을 병합."""
        # 최종 stance 결정
        final_stance = cls._determine_final_stance(
            support.stance, skeptic.stance, bool(support.citations or skeptic.citations)
        )

        # confidence 계산
        final_confidence = cls._calculate_confidence(
            support.confidence,
            skeptic.confidence,
            final_stance,
            support.stance,
            skeptic.stance,
        )

        # citations 병합
        merged_citations = cls._merge_citations(support.citations, skeptic.citations)

        # reasoning 병합
        merged_reasoning = cls._merge_reasoning(
            support.reasoning_bullets,
            skeptic.reasoning_bullets,
            final_stance,
        )

        # 합의 수준 계산
        agreement = 1.0 if support.stance == skeptic.stance else 0.5

        # 품질 점수 계산
        quality = cls._calculate_quality(
            final_stance,
            merged_citations,
            merged_reasoning,
            agreement,
        )

        return cls(
            stance=final_stance,
            confidence=final_confidence,
            reasoning_bullets=merged_reasoning,
            citations=merged_citations,
            weak_points=list(set(support.weak_points + skeptic.weak_points)),
            followup_queries=(support.followup_queries + skeptic.followup_queries)[:5],
            support_stance=support.stance,
            skeptic_stance=skeptic.stance,
            agreement_level=agreement,
            quality_score=quality,
        )

    @staticmethod
    def _determine_final_stance(
        support_stance: Stance,
        skeptic_stance: Stance,
        has_citations: bool,
    ) -> Stance:
        """최종 stance 결정."""
        # 둘 다 UNVERIFIED
        if support_stance == Stance.UNVERIFIED and skeptic_stance == Stance.UNVERIFIED:
            return Stance.UNVERIFIED

        # citations 없으면 UNVERIFIED
        if not has_citations:
            return Stance.UNVERIFIED

        # 합의
        if support_stance == skeptic_stance:
            return support_stance

        # 한쪽만 UNVERIFIED
        if support_stance == Stance.UNVERIFIED:
            return skeptic_stance
        if skeptic_stance == Stance.UNVERIFIED:
            return support_stance

        # TRUE vs FALSE → MIXED
        if {support_stance, skeptic_stance} == {Stance.TRUE, Stance.FALSE}:
            return Stance.MIXED

        return Stance.MIXED

    @staticmethod
    def _calculate_confidence(
        support_conf: float,
        skeptic_conf: float,
        final_stance: Stance,
        support_stance: Stance,
        skeptic_stance: Stance,
    ) -> float:
        """confidence 계산."""
        if final_stance == Stance.UNVERIFIED:
            return 0.0

        if support_stance == skeptic_stance:
            return (support_conf + skeptic_conf) / 2

        # 불합의 시 페널티
        avg = (support_conf + skeptic_conf) / 2
        return max(0.0, avg * 0.7)

    @staticmethod
    def _merge_citations(
        support_cits: List[VerdictCitation],
        skeptic_cits: List[VerdictCitation],
    ) -> List[VerdictCitation]:
        """citations 병합 (중복 제거)."""
        seen_ids = set()
        merged = []

        for cit in support_cits + skeptic_cits:
            if cit.evid_id and cit.evid_id not in seen_ids:
                seen_ids.add(cit.evid_id)
                merged.append(cit)

        return merged

    @staticmethod
    def _merge_reasoning(
        support_bullets: List[str],
        skeptic_bullets: List[str],
        final_stance: Stance,
    ) -> List[str]:
        """reasoning 병합."""
        bullets = []

        # 종합 설명 추가
        if final_stance == Stance.MIXED:
            bullets.append("[종합] 지지와 반박 증거가 모두 존재하여 MIXED로 판정")
        elif final_stance == Stance.UNVERIFIED:
            bullets.append("[종합] 충분한 근거가 없어 UNVERIFIED로 판정")

        # 지지 관점
        for bullet in support_bullets:
            if bullet and not bullet.startswith("[시스템"):
                bullets.append(f"[지지] {bullet}")

        # 회의적 관점
        for bullet in skeptic_bullets:
            if bullet and not bullet.startswith("[시스템"):
                bullets.append(f"[반박] {bullet}")

        return bullets

    @staticmethod
    def _calculate_quality(
        stance: Stance,
        citations: List[VerdictCitation],
        reasoning: List[str],
        agreement: float,
    ) -> int:
        """품질 점수 계산 (0-100)."""
        score = 0

        # 형식 점수 (40점)
        if stance:
            score += 10
        if citations:
            score += 10
        if reasoning:
            score += 10
        score += 10  # 기본 형식

        # 근거 점수 (40점)
        score += min(20, len(citations) * 4)
        score += min(20, len(reasoning) * 4)

        # 합의 점수 (20점)
        score += int(agreement * 20)

        return min(100, max(0, score))

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "stance": self.stance.value,
            "confidence": self.confidence,
            "reasoning_bullets": self.reasoning_bullets,
            "citations": [c.to_dict() for c in self.citations],
            "weak_points": self.weak_points,
            "followup_queries": self.followup_queries,
            "support_stance": self.support_stance.value if self.support_stance else None,
            "skeptic_stance": self.skeptic_stance.value if self.skeptic_stance else None,
            "agreement_level": self.agreement_level,
            "quality_score": self.quality_score,
        }


class FinalVerdict(BaseModel):
    """
    Stage 9 출력 스키마: 최종 판정.

    Quality Gate를 통과한 최종 결과입니다.
    """

    stance: Stance = Field(default=Stance.UNVERIFIED)
    """최종 판정"""

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    """확신도"""

    summary: str = Field(default="")
    """요약"""

    reasoning_bullets: List[str] = Field(default_factory=list)
    """근거"""

    citations: List[VerdictCitation] = Field(default_factory=list)
    """인용"""

    quality_score: int = Field(default=0, ge=0, le=100)
    """품질 점수"""

    passed_quality_gate: bool = Field(default=False)
    """품질 게이트 통과 여부"""

    @classmethod
    def from_aggregated(
        cls,
        aggregated: AggregatedVerdict,
        quality_threshold: int = 65,
    ) -> "FinalVerdict":
        """AggregatedVerdict에서 FinalVerdict 생성."""
        passed = aggregated.quality_score >= quality_threshold

        # Quality Gate 미통과 시 UNVERIFIED
        if not passed:
            return cls(
                stance=Stance.UNVERIFIED,
                confidence=0.0,
                summary=f"품질 점수({aggregated.quality_score})가 기준({quality_threshold}) 미달",
                reasoning_bullets=aggregated.reasoning_bullets,
                citations=aggregated.citations,
                quality_score=aggregated.quality_score,
                passed_quality_gate=False,
            )

        # 요약 생성
        summary = cls._generate_summary(aggregated)

        return cls(
            stance=aggregated.stance,
            confidence=aggregated.confidence,
            summary=summary,
            reasoning_bullets=aggregated.reasoning_bullets,
            citations=aggregated.citations,
            quality_score=aggregated.quality_score,
            passed_quality_gate=True,
        )

    @staticmethod
    def _generate_summary(aggregated: AggregatedVerdict) -> str:
        """요약 생성."""
        stance_desc = {
            Stance.TRUE: "사실로 확인됨",
            Stance.FALSE: "거짓으로 확인됨",
            Stance.MIXED: "일부 사실, 일부 거짓",
            Stance.UNVERIFIED: "검증 불가",
        }

        desc = stance_desc.get(aggregated.stance, "판정 불가")
        return f"본 주장에 대한 판정 결과는 '{aggregated.stance.value}'입니다. {desc}."

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "stance": self.stance.value,
            "confidence": self.confidence,
            "summary": self.summary,
            "reasoning_bullets": self.reasoning_bullets,
            "citations": [c.to_dict() for c in self.citations],
            "quality_score": self.quality_score,
            "passed_quality_gate": self.passed_quality_gate,
        }
