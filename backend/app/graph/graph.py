import uuid
from datetime import datetime, timezone

from app.core.schemas import TruthCheckRequest, TruthCheckResponse, Citation, ModelInfo

# Placeholder pipeline - replace with LangGraph implementation


def run_pipeline(req: TruthCheckRequest) -> TruthCheckResponse:
    return TruthCheckResponse(
        analysis_id=str(uuid.uuid4()),
        label="UNVERIFIED",
        confidence=0.0,
        summary="Pipeline skeleton. Replace with real output.",
        rationale=["Evidence pipeline is not connected yet."],
        citations=[],
        counter_evidence=[],
        limitations=["No evidence collected yet."],
        recommended_next_steps=["Connect stages and evidence pipeline."],
        risk_flags=["LOW_EVIDENCE"],
        model_info=ModelInfo(provider="local", model="stub", version="v0.0"),
        latency_ms=0,
        cost_usd=0.0,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
