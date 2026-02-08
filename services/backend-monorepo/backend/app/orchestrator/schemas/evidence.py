"""
Evidence Schemas.

Stage 3-5에서 사용하는 증거 관련 스키마입니다.

스키마 불일치 해결:
- content와 snippet 모두 포함
- evid_id 자동 생성
- source_type 통합
"""

import hashlib
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator

from .common import SourceType


class EvidenceMetadata(BaseModel):
    """증거 메타데이터."""

    origin: Optional[str] = None
    """출처 (naver, duckduckgo, wiki 등)"""

    page_id: Optional[int] = None
    """Wiki 페이지 ID"""

    chunk_id: Optional[int] = None
    """Wiki 청크 ID"""

    dist: Optional[float] = None
    """벡터 거리 (유사도)"""

    lex_score: Optional[float] = None
    """렉시컬 스코어"""

    pub_date: Optional[str] = None
    """발행일"""

    extra: Dict[str, Any] = Field(default_factory=dict)
    """추가 메타데이터"""


class EvidenceCandidate(BaseModel):
    """
    Stage 3 출력 스키마: 수집된 증거 후보.

    모든 증거는 이 스키마로 정규화됩니다.
    """

    evid_id: str = Field(..., description="고유 증거 ID")
    """고유 식별자 (자동 생성 가능)"""

    source_type: SourceType = Field(default=SourceType.WEB)
    """소스 타입"""

    title: str = Field(default="")
    """제목"""

    url: str = Field(default="")
    """URL"""

    content: str = Field(default="")
    """전체 내용"""

    snippet: str = Field(default="")
    """요약된 내용 (LLM 프롬프트용)"""

    metadata: EvidenceMetadata = Field(default_factory=EvidenceMetadata)
    """메타데이터"""

    @classmethod
    def generate_evid_id(cls, url: str, title: str) -> str:
        """URL과 제목으로 evid_id 생성."""
        key = f"{url}:{title}"
        return f"ev_{hashlib.md5(key.encode()).hexdigest()[:8]}"

    @classmethod
    def create_snippet(cls, content: str, max_length: int = 500) -> str:
        """content에서 snippet 생성."""
        content = (content or "").strip()
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."

    @model_validator(mode="before")
    @classmethod
    def auto_generate_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """evid_id와 snippet 자동 생성."""
        # evid_id 생성
        if not values.get("evid_id"):
            url = values.get("url", "")
            title = values.get("title", "")
            values["evid_id"] = cls.generate_evid_id(url, title)

        # snippet 생성 (content가 있고 snippet이 없으면)
        if values.get("content") and not values.get("snippet"):
            values["snippet"] = cls.create_snippet(values["content"])

        # source_type 정규화
        if isinstance(values.get("source_type"), str):
            values["source_type"] = SourceType.from_string(values["source_type"])

        # metadata 정규화
        if isinstance(values.get("metadata"), dict):
            values["metadata"] = EvidenceMetadata(**values["metadata"])

        return values

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (state 저장용)."""
        return {
            "evid_id": self.evid_id,
            "source_type": self.source_type.value,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "snippet": self.snippet,
            "metadata": self.metadata.model_dump(),
        }

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "EvidenceCandidate":
        """
        raw 딕셔너리에서 EvidenceCandidate 생성.

        Stage 3의 기존 출력 형식을 지원합니다.
        """
        return cls(
            evid_id=raw.get("evid_id", ""),
            source_type=raw.get("source_type", "WEB"),
            title=raw.get("title", ""),
            url=raw.get("url", ""),
            content=raw.get("content", ""),
            snippet=raw.get("snippet", ""),
            metadata=raw.get("metadata", {}),
        )


class ScoredEvidence(EvidenceCandidate):
    """
    Stage 4 출력 스키마: 점수가 매겨진 증거.

    EvidenceCandidate에 score 필드가 추가됩니다.
    """

    score: float = Field(default=0.0, ge=0.0, le=1.0)
    """관련성 점수 (0.0 ~ 1.0)"""

    @classmethod
    def from_candidate(
        cls,
        candidate: EvidenceCandidate,
        score: float,
    ) -> "ScoredEvidence":
        """EvidenceCandidate에 점수를 추가하여 생성."""
        return cls(
            evid_id=candidate.evid_id,
            source_type=candidate.source_type,
            title=candidate.title,
            url=candidate.url,
            content=candidate.content,
            snippet=candidate.snippet,
            metadata=candidate.metadata,
            score=score,
        )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        base = super().to_dict()
        base["score"] = self.score
        return base


class Citation(BaseModel):
    """
    Stage 5+ 출력 스키마: 인용 정보.

    Top-K 선정 후 사용되는 최종 인용 형식입니다.
    Stage 6/7에서 사용하는 모든 필드를 포함합니다.
    """

    evid_id: str = Field(..., description="고유 증거 ID")
    """고유 식별자"""

    source_type: SourceType = Field(default=SourceType.WEB)
    """소스 타입"""

    title: str = Field(default="")
    """제목"""

    url: str = Field(default="")
    """URL"""

    content: str = Field(default="")
    """전체 내용"""

    snippet: str = Field(default="")
    """요약된 내용 (LLM 프롬프트용)"""

    quote: Optional[str] = None
    """인용문 (SLM이 생성)"""

    score: float = Field(default=0.0, ge=0.0, le=1.0)
    """관련성 점수"""

    relevance: Optional[float] = None
    """관련성 (API 응답용, score의 별칭)"""

    metadata: EvidenceMetadata = Field(default_factory=EvidenceMetadata)
    """메타데이터"""

    @model_validator(mode="before")
    @classmethod
    def sync_relevance(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """score와 relevance 동기화."""
        if values.get("score") and not values.get("relevance"):
            values["relevance"] = values["score"]
        elif values.get("relevance") and not values.get("score"):
            values["score"] = values["relevance"]

        # source_type 정규화
        if isinstance(values.get("source_type"), str):
            values["source_type"] = SourceType.from_string(values["source_type"])

        return values

    @classmethod
    def from_scored_evidence(cls, scored: ScoredEvidence) -> "Citation":
        """ScoredEvidence에서 Citation 생성."""
        return cls(
            evid_id=scored.evid_id,
            source_type=scored.source_type,
            title=scored.title,
            url=scored.url,
            content=scored.content,
            snippet=scored.snippet,
            score=scored.score,
            relevance=scored.score,
            metadata=scored.metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "evid_id": self.evid_id,
            "source_type": self.source_type.value,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "snippet": self.snippet,
            "quote": self.quote,
            "score": self.score,
            "relevance": self.relevance,
            "metadata": self.metadata.model_dump(),
        }

    def to_api_dict(self) -> Dict[str, Any]:
        """API 응답용 딕셔너리."""
        return {
            "source_type": self.source_type.to_api_type(),
            "title": self.title,
            "url": self.url,
            "quote": self.quote or self.snippet[:500],
            "relevance": self.relevance or self.score,
        }

    def format_for_prompt(self, index: int = 1) -> str:
        """LLM 프롬프트용 텍스트 포맷."""
        lines = [
            f"[{self.evid_id}] ({self.source_type.value}) {self.title}",
        ]
        if self.url:
            lines.append(f"    URL: {self.url}")
        lines.append(f"    내용: {self.snippet}")
        return "\n".join(lines)


def filter_top_k(
    scored_evidence: List[ScoredEvidence],
    threshold: float = 0.7,
    top_k: int = 6,
) -> List[Citation]:
    """
    점수 기준으로 Top-K 선정.

    Args:
        scored_evidence: 점수가 매겨진 증거 리스트
        threshold: 최소 점수 임계값
        top_k: 최대 선정 개수

    Returns:
        Citation 리스트
    """
    # 임계값 필터링
    filtered = [e for e in scored_evidence if e.score >= threshold]

    # 점수순 정렬
    sorted_evidence = sorted(filtered, key=lambda x: x.score, reverse=True)

    # Top-K 선정
    top_evidence = sorted_evidence[:top_k]

    # Citation으로 변환
    return [Citation.from_scored_evidence(e) for e in top_evidence]
