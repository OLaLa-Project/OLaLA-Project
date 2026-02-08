"""
Request Schemas
"""

from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    """검증 요청 스키마"""
    claim: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="검증할 주장 텍스트"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"claim": "대한민국의 수도는 서울이다."}
            ]
        }
    }
