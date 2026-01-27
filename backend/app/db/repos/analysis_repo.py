# backend/app/db/repos/analysis_repo.py
from sqlalchemy.orm import Session
from app.db.models import AnalysisResult
from app.core.schemas import TruthCheckRequest, TruthCheckResponse


def save_analysis(db: Session, req: TruthCheckRequest, res: TruthCheckResponse) -> None:
    record = AnalysisResult(
        analysis_id=res.analysis_id,
        label=res.label,
        confidence=res.confidence,
        summary=res.summary,
        rationale=res.rationale,
        citations=[c.model_dump() for c in res.citations],
        counter_evidence=res.counter_evidence,
        limitations=res.limitations,
        recommended_next_steps=res.recommended_next_steps,
        risk_flags=res.risk_flags,
        model_info=res.model_info.model_dump(),
        latency_ms=res.latency_ms,
        cost_usd=res.cost_usd,
    )
    db.add(record)
    db.commit()
