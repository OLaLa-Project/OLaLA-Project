from sqlalchemy.orm import Session
from app.gateway.database.models import AnalysisResult

class AnalysisRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_analysis(self, analysis_data: dict) -> AnalysisResult:
        """
        Save analysis result.
        analysis_data should be a dictionary matching AnalysisResult model fields.
        """
        record = AnalysisResult(
            analysis_id=analysis_data.get("analysis_id"),
            label=analysis_data.get("label"),
            confidence=analysis_data.get("confidence"),
            summary=analysis_data.get("summary"),
            rationale=analysis_data.get("rationale") or [],
            citations=analysis_data.get("citations") or [],
            counter_evidence=analysis_data.get("counter_evidence") or [],
            limitations=analysis_data.get("limitations") or [],
            recommended_next_steps=analysis_data.get("recommended_next_steps") or [],
            risk_flags=analysis_data.get("risk_flags") or [],
            model_info=analysis_data.get("model_info") or {},
            latency_ms=analysis_data.get("latency_ms", 0),
            cost_usd=analysis_data.get("cost_usd", 0.0),
        )
        self.db.add(record)
        self.db.commit()
        return record
