"""
Response Schemas
"""

from typing import Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """증거 스키마"""
    source: str = Field(..., description="출처 (예: wikipedia)")
    title: str = Field(..., description="문서 제목")
    content: str = Field(..., description="관련 내용")
    url: str | None = Field(None, description="원문 URL")


class VerifyResponse(BaseModel):
    """검증 응답 스키마"""
    request_id: str = Field(..., description="요청 ID")
    label: Literal["TRUE", "FALSE", "MIXED", "UNVERIFIED", "REFUSED"] = Field(
        ...,
        description="판정 라벨"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="신뢰도 (0~1)")
    summary: str = Field(..., description="판정 요약 설명")
    evidences: list[Evidence] = Field(default_factory=list, description="근거 목록")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request_id": "uuid-1234",
                    "label": "TRUE",
                    "confidence": 0.92,
                    "summary": "해당 주장은 사실로 확인됩니다.",
                    "evidences": [
                        {
                            "source": "wikipedia",
                            "title": "서울",
                            "content": "서울은 대한민국의 수도이다.",
                            "url": "https://ko.wikipedia.org/wiki/서울"
                        }
                    ]
                }
            ]
        }
    }
