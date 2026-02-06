"""
Verification API - 가짜뉴스 검증 엔드포인트
"""

import uuid
from fastapi import APIRouter, HTTPException
from ..schemas.request import VerifyRequest
from ..schemas.response import VerifyResponse
from ..services.pipeline_service import PipelineService

router = APIRouter()
pipeline_service = PipelineService()


@router.post("/verify", response_model=VerifyResponse)
async def verify_claim(request: VerifyRequest):
    """
    주장을 검증하는 API

    - claim: 검증할 텍스트
    """
    request_id = str(uuid.uuid4())

    try:
        result = await pipeline_service.run(
            request_id=request_id,
            claim=request.claim
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
