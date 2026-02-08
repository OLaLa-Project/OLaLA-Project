from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class NormalizedClaim(BaseModel):
    """
    Stage 1 정규화 결과 스키마.
    """
    claim_text: str = Field(..., description="정규화된 핵심 주장/사실 (평서문)")
    original_intent: Literal["verification", "exploration"] = Field(
        ..., 
        description="사용자의 의도 (verification: 팩트체크/검증, exploration: 단순 정보 탐색/설명 요청)"
    )
    key_entities: List[str] = Field(
        default_factory=list, 
        description="주장 검증에 필수적인 핵심 엔티티(인물, 조직, 사건 등)"
    )
    
    def to_dict(self) -> dict:
        return {
            "claim_text": self.claim_text,
            "original_intent": self.original_intent,
            "key_entities": self.key_entities
        }
