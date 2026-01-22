from pydantic import BaseModel
from typing import List, Optional

class Citation(BaseModel):
    source_type: str
    title: str
    url: Optional[str] = None
    quote: Optional[str] = None

class FinalResult(BaseModel):
    analysis_id: str
    label: str
    confidence: float
    summary: str
    citations: List[Citation]
    limitations: List[str]
    recommended_next_steps: List[str]
