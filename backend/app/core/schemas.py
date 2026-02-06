from pydantic import BaseModel, Field
from typing import List, Optional, Literal

from app.graph.state import PublicStageName


class TruthCheckRequest(BaseModel):
    input_type: Literal["url", "text", "image"] = "text"
    input_payload: str
    user_request: Optional[str] = None
    as_of: Optional[str] = None
    language: Optional[str] = "ko"
    start_stage: Optional[PublicStageName] = None
    end_stage: Optional[PublicStageName] = None
    querygen_prompt: Optional[str] = None
    normalize_mode: Optional[Literal["llm", "basic"]] = None
    stage_state: Optional[dict] = None
    include_full_outputs: Optional[bool] = False
    checkpoint_thread_id: Optional[str] = None
    checkpoint_resume: Optional[bool] = True


class Citation(BaseModel):
    source_type: Literal["KB_DOC", "WEB_URL", "NEWS", "WIKIPEDIA"] = "WEB_URL"
    title: str
    url: Optional[str] = None
    quote: Optional[str] = None
    relevance: Optional[float] = None
    evid_id: Optional[str] = None


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
    stage_logs: List[dict] = Field(default_factory=list)
    stage_outputs: dict = Field(default_factory=dict)
    stage_full_outputs: dict = Field(default_factory=dict)
    model_info: ModelInfo
    latency_ms: int
    cost_usd: float
    created_at: str
    checkpoint_thread_id: Optional[str] = None
    checkpoint_resumed: Optional[bool] = None
    checkpoint_expired: Optional[bool] = None

    model_config = {"protected_namespaces": ()}
