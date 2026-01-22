from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class TruthCheckRequest(BaseModel):
    input_type: Literal["url", "text", "image"] = "text"
    input_payload: str
    user_request: Optional[str] = None
    as_of: Optional[str] = None
    language: Optional[str] = "ko"


class Citation(BaseModel):
    source_type: Literal["KB_DOC", "WEB_URL", "NEWS", "WIKIPEDIA"] = "WEB_URL"
    title: str
    url: Optional[str] = None
    quote: Optional[str] = None
    relevance: Optional[float] = None


class ModelInfo(BaseModel):
    provider: str
    model: str
    version: str


class TruthCheckResponse(BaseModel):
    analysis_id: str
    label: Literal["TRUE", "FALSE", "MIXED", "UNVERIFIED", "REFUSED"]
    confidence: float
    summary: str
    rationale: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    counter_evidence: List[dict] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    model_info: ModelInfo
    latency_ms: int
    cost_usd: float
    created_at: str
