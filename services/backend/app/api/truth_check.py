"""Truth check API."""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.errors import (
    PIPELINE_EXECUTION_FAILED,
    PIPELINE_STREAM_INIT_FAILED,
    to_http_exception,
)
from app.core.schemas import TruthCheckRequest, TruthCheckResponse
from app.db.session import get_db
from app.orchestrator.database.repos.analysis_repo import AnalysisRepository
from app.orchestrator.service import run_pipeline, run_pipeline_stream

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/truth/check", response_model=TruthCheckResponse)
@router.post("/v1/truth/check", response_model=TruthCheckResponse)
def truth_check(req: TruthCheckRequest, db: Session = Depends(get_db)) -> TruthCheckResponse:
    try:
        result = run_pipeline(req)
    except Exception:
        logger.exception("Pipeline execution failed")
        raise to_http_exception(PIPELINE_EXECUTION_FAILED)

    try:
        AnalysisRepository(db).save_analysis(result.model_dump())
    except Exception:
        logger.exception("Analysis persistence failed")
        current_flags = list(result.risk_flags or [])
        if "PERSISTENCE_FAILED" not in current_flags:
            current_flags.append("PERSISTENCE_FAILED")
        result.risk_flags = current_flags

    return result


@router.post("/api/truth/check/stream")
@router.post("/v1/api/truth/check/stream")
async def truth_check_stream(req: TruthCheckRequest):
    """
    Streaming version of truth_check that yields stage completion events.
    Client receives JSON objects after each stage completes.
    Format: {"event": "stage_complete", "stage": "stage01_normalize", "data": {...}}
    """
    try:
        stream = run_pipeline_stream(req)
    except Exception:
        logger.exception("Pipeline stream initialization failed")
        raise to_http_exception(PIPELINE_STREAM_INIT_FAILED)

    return StreamingResponse(stream, media_type="application/x-ndjson")
