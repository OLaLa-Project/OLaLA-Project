from sqlalchemy import Column, DateTime, Float, Integer, String, JSON
from sqlalchemy.sql import func

from app.gateway.database.connection import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    analysis_id = Column(String, primary_key=True, index=True)
    label = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    summary = Column(String, nullable=False)
    rationale = Column(JSON, nullable=False, default=list)
    citations = Column(JSON, nullable=False, default=list)
    counter_evidence = Column(JSON, nullable=False, default=list)
    limitations = Column(JSON, nullable=False, default=list)
    recommended_next_steps = Column(JSON, nullable=False, default=list)
    risk_flags = Column(JSON, nullable=False, default=list)
    model_info = Column(JSON, nullable=False, default=dict)
    latency_ms = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
