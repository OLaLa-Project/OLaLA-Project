"""
Pipeline Service - ML 파이프라인 연동
"""

from ..schemas.response import VerifyResponse, Evidence


class PipelineService:
    """ML 파이프라인을 호출하는 서비스"""

    async def run(self, request_id: str, claim: str) -> VerifyResponse:
        """
        ML 파이프라인 실행

        Args:
            request_id: 요청 ID
            claim: 검증할 주장

        Returns:
            VerifyResponse: 검증 결과
        """
        # TODO: 실제 ML 파이프라인 (LangGraph) 연동
        # from ml_pipeline.graph import run_pipeline
        # result = await run_pipeline(request_id, claim)

        # 임시 더미 응답
        return VerifyResponse(
            request_id=request_id,
            label="UNVERIFIED",
            confidence=0.0,
            summary="ML 파이프라인 연동 전입니다.",
            evidences=[]
        )
