from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field


class WikiSearchRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=50)
    window: int = Field(2, ge=0, le=10)
    page_limit: int = Field(8, ge=1, le=50)
    embed_missing: bool = True


class CandidatePage(BaseModel):
    page_id: int
    title: str
    score: Optional[float] = None


class EvidenceBlock(BaseModel):
    title: str
    page_id: int
    chunk_id: int
    chunk_idx: int
    content: str
    snippet: str
    dist: Optional[float] = None
    lex_score: Optional[float] = None
    title_score: Optional[float] = None
    final_score: Optional[float] = None


class WikiSearchResponse(BaseModel):
    question: str
    candidates: List[CandidatePage]
    hits: List[EvidenceBlock]
    updated_embeddings: Optional[int] = None
    debug: Optional[Dict[str, Any]] = None
