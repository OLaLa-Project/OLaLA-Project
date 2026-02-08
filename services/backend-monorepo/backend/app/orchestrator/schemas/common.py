"""
Common Schema Types.

파이프라인 전체에서 공유하는 기본 타입 정의입니다.
"""

from enum import Enum
from typing import Literal, Optional, Dict, Any


class SourceType(str, Enum):
    """
    증거 소스 타입.

    내부 파이프라인과 API 응답 모두에서 동일한 값을 사용합니다.
    """

    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"
    """내부 지식 베이스 (Wiki 문서)"""

    NEWS = "NEWS"
    """뉴스 기사 (Naver News 등)"""

    WEB = "WEB"
    """일반 웹 검색 결과 (DuckDuckGo 등)"""

    WIKIPEDIA = "WIKIPEDIA"
    """위키피디아 문서"""

    @classmethod
    def from_string(cls, value: str) -> "SourceType":
        """문자열에서 SourceType으로 변환."""
        value = (value or "").upper().strip()

        # 별칭 매핑
        aliases = {
            "KB_DOC": cls.KNOWLEDGE_BASE,
            "KB": cls.KNOWLEDGE_BASE,
            "WEB_URL": cls.WEB,
            "DUCKDUCKGO": cls.WEB,
            "DDG": cls.WEB,
            "NAVER": cls.NEWS,
            "NAVER_NEWS": cls.NEWS,
            "WIKI": cls.WIKIPEDIA,
        }

        if value in aliases:
            return aliases[value]

        try:
            return cls(value)
        except ValueError:
            return cls.WEB  # 기본값

    def to_api_type(self) -> str:
        """API 응답용 타입으로 변환."""
        mapping = {
            self.KNOWLEDGE_BASE: "WIKIPEDIA",
            self.NEWS: "NEWS",
            self.WEB: "WEB_URL",
            self.WIKIPEDIA: "WIKIPEDIA",
        }
        return mapping.get(self, "WEB_URL")


class Language(str, Enum):
    """지원 언어."""

    KO = "ko"
    """한국어"""

    EN = "en"
    """영어"""

    @classmethod
    def from_string(cls, value: str) -> "Language":
        """문자열에서 Language로 변환."""
        value = (value or "ko").lower().strip()
        try:
            return cls(value)
        except ValueError:
            return cls.KO  # 기본값


# 타입 별칭 (Literal 사용 시)
SourceTypeLiteral = Literal[
    "KNOWLEDGE_BASE", "NEWS", "WEB", "WIKIPEDIA",
    "KB_DOC", "WEB_URL"  # API 호환용
]

LanguageLiteral = Literal["ko", "en"]

StanceLiteral = Literal["TRUE", "FALSE", "MIXED", "UNVERIFIED", "REFUSED"]


class SearchQueryType(str, Enum):
    """
    검색 쿼리 의도/타입.
    Stage 2에서 생성하고 Stage 3에서 라우팅에 사용.
    """
    WIKI = "wiki"
    """지식백과/문서 검색 (정밀 검증)"""
    
    NEWS = "news"
    """뉴스/최신정보 검색 (시의성)"""
    
    WEB = "web"
    """일반 웹 검색 (보조)"""
    
    DIRECT = "direct"
    """직접/통합 검색 (기본)"""
    
    VERIFICATION = "verification"
    """팩트체크용 검색 (검증/반박)"""


from pydantic import BaseModel, Field

class SearchQuery(BaseModel):
    """
    구조화된 검색 쿼리.
    """
    text: str = Field(..., description="검색어")
    type: SearchQueryType = Field(default=SearchQueryType.DIRECT, description="쿼리 타입")
    search_mode: Optional[str] = Field(
        default=None,
        description="검색 모드 (auto|lexical|vector|fts 등)",
    )
    meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="정규화/디버그 힌트",
    )
    
    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"text": self.text, "type": self.type.value}
        if self.search_mode:
            data["search_mode"] = self.search_mode
        if self.meta:
            data["meta"] = self.meta
        return data
