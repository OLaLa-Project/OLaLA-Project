"""
Orchestrator Unified Schemas.

파이프라인 전체에서 사용하는 통합 스키마 정의입니다.
스키마 불일치 문제를 해결하고 타입 안정성을 보장합니다.
"""

from .common import SourceType, Language
from .evidence import (
    EvidenceCandidate,
    ScoredEvidence,
    Citation,
    EvidenceMetadata,
)
from .verdict import (
    Stance,
    DraftVerdict,
    AggregatedVerdict,
    FinalVerdict,
    VerdictCitation,
)
from .transform import SchemaTransformer

__all__ = [
    # Common
    "SourceType",
    "Language",
    # Evidence
    "EvidenceCandidate",
    "ScoredEvidence",
    "Citation",
    "EvidenceMetadata",
    # Verdict
    "Stance",
    "DraftVerdict",
    "AggregatedVerdict",
    "FinalVerdict",
    "VerdictCitation",
    # Transform
    "SchemaTransformer",
]
