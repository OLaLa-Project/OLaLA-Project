"""Truth check API."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.schemas import TruthCheckRequest, TruthCheckResponse
from app.db.session import get_db
from app.gateway.database.repos.analysis_repo import AnalysisRepository
from app.gateway.service import run_pipeline, run_pipeline_stream

router = APIRouter()


@router.post("/truth/check", response_model=TruthCheckResponse)
def truth_check(req: TruthCheckRequest, db: Session = Depends(get_db)) -> TruthCheckResponse:
    result = run_pipeline(req)
    AnalysisRepository(db).save_analysis(result.model_dump())
    return result


@router.post("/api/truth/check/stream")
async def truth_check_stream(req: TruthCheckRequest):
    """
    Streaming version of truth_check that yields stage completion events.
    Client receives JSON objects after each stage completes.
    Format: {"event": "stage_complete", "stage": "stage01_normalize", "data": {...}}
    """
    return StreamingResponse(
        run_pipeline_stream(req),
        media_type="application/x-ndjson"
    )

