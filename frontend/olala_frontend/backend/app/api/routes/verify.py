from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.verify import verification_service

router = APIRouter(tags=["verify"])


class VerifyAnalyzeRequest(BaseModel):
    input: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="text", max_length=20)


@router.get("/verify/search")
async def verify_search(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=5, ge=1, le=10),
) -> dict[str, object]:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="q is required")

    evidence_cards = await verification_service.search(query, limit=limit)
    return {
        "query": query,
        "count": len(evidence_cards),
        "evidenceCards": evidence_cards,
        "evidence_cards": evidence_cards,
    }


@router.post("/verify/analyze")
async def verify_analyze(payload: VerifyAnalyzeRequest) -> dict[str, object]:
    raw_input = payload.input.strip()
    if not raw_input:
        raise HTTPException(status_code=400, detail="input is required")

    result = await verification_service.analyze(raw_input, mode=payload.mode)
    return result
