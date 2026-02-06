from dataclasses import dataclass

from fastapi import HTTPException


@dataclass(frozen=True)
class APIErrorSpec:
    code: str
    message: str
    status_code: int = 500


PIPELINE_EXECUTION_FAILED = APIErrorSpec(
    code="PIPELINE_EXECUTION_FAILED",
    message="분석 파이프라인 실행 중 오류가 발생했습니다.",
)

PIPELINE_STREAM_INIT_FAILED = APIErrorSpec(
    code="PIPELINE_STREAM_INIT_FAILED",
    message="스트리밍 파이프라인 시작 중 오류가 발생했습니다.",
)


def to_http_exception(spec: APIErrorSpec) -> HTTPException:
    return HTTPException(
        status_code=spec.status_code,
        detail={
            "code": spec.code,
            "message": spec.message,
        },
    )

