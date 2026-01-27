"""Truth check API."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.schemas import TruthCheckRequest, TruthCheckResponse
from app.db.session import get_db
from app.db.repos.analysis_repo import save_analysis
from app.graph.graph import run_pipeline

router = APIRouter()


@router.post("/truth/check", response_model=TruthCheckResponse)
def truth_check(req: TruthCheckRequest, db: Session = Depends(get_db)) -> TruthCheckResponse:
    result = run_pipeline(req)
    save_analysis(db, req, result)
    return result
