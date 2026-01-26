"""
SLM2 파이프라인 데모 스크립트.

실제 vLLM 서버를 사용하여 Stage 6-8 파이프라인을 테스트합니다.

실행 전 준비:
1. vLLM 서버 실행 (docker-compose 또는 직접 실행)
2. 환경변수 설정 (선택):
   - SLM_BASE_URL (default: http://localhost:8001/v1)
   - SLM_API_KEY (default: local-slm-key)
   - SLM_MODEL (default: slm)

실행 방법:
    cd backend
    python -m tests.demo_slm2_pipeline

    # 또는 특정 테스트 케이스만
    python -m tests.demo_slm2_pipeline --case 1
"""

import sys
import json
import time
import argparse
import logging
import uuid
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# 테스트 케이스 정의
# ============================================================================

TEST_CASES = [
    {
        "id": 1,
        "name": "명확한 사실 (TRUE 예상)",
        "claim_text": "서울은 대한민국의 수도이다.",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "위키백과 - 서울",
                "url": "https://ko.wikipedia.org/wiki/서울",
                "snippet": "서울특별시는 대한민국의 수도이자 최대 도시이다. 한반도 중앙부에 위치하며, 인구는 약 950만 명이다.",
                "source_type": "WIKIPEDIA",
            },
            {
                "evid_id": "ev_2",
                "title": "대한민국 헌법",
                "url": "https://www.law.go.kr",
                "snippet": "대한민국의 수도는 서울특별시로 한다. 이는 헌법적 관행으로 인정되고 있다.",
                "source_type": "KB_DOC",
            },
        ],
        "expected_stance": "TRUE",
    },
    {
        "id": 2,
        "name": "명확한 거짓 (FALSE 예상)",
        "claim_text": "지구는 평평하다.",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "NASA 공식 발표",
                "url": "https://www.nasa.gov",
                "snippet": "지구는 구형이며, 약간 납작한 타원체 형태를 띠고 있다. 이는 수많은 우주 탐사와 과학적 관측으로 입증되었다.",
                "source_type": "KB_DOC",
            },
            {
                "evid_id": "ev_2",
                "title": "과학 교과서",
                "url": "https://example.com/science",
                "snippet": "지구의 둘레는 약 4만 km이며, 구형 행성으로서 자전과 공전을 한다.",
                "source_type": "WEB_URL",
            },
        ],
        "expected_stance": "FALSE",
    },
    {
        "id": 3,
        "name": "혼합된 정보 (MIXED 예상)",
        "claim_text": "커피는 건강에 좋다.",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "건강 연구 - 긍정적 효과",
                "url": "https://health.example.com/1",
                "snippet": "적당량의 커피 섭취는 심장 건강에 도움이 될 수 있으며, 항산화 물질이 풍부하다는 연구 결과가 있다.",
                "source_type": "NEWS",
            },
            {
                "evid_id": "ev_2",
                "title": "건강 연구 - 부정적 효과",
                "url": "https://health.example.com/2",
                "snippet": "과도한 카페인 섭취는 불안, 불면증, 심박수 증가 등의 부작용을 유발할 수 있다.",
                "source_type": "NEWS",
            },
        ],
        "expected_stance": "MIXED",
    },
    {
        "id": 4,
        "name": "증거 부족 (UNVERIFIED 예상)",
        "claim_text": "외계 생명체가 지구를 방문한 적이 있다.",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "UFO 목격담",
                "url": "https://ufo.example.com",
                "snippet": "일부 사람들은 미확인 비행물체를 목격했다고 주장하지만, 과학적으로 검증된 증거는 없다.",
                "source_type": "WEB_URL",
            },
        ],
        "expected_stance": "UNVERIFIED",
    },
    {
        "id": 5,
        "name": "증거 없음 (UNVERIFIED 강제)",
        "claim_text": "2050년에 한국 인구는 3천만 명이 될 것이다.",
        "evidence_topk": [],
        "expected_stance": "UNVERIFIED",
    },
]


# ============================================================================
# 파이프라인 실행
# ============================================================================

def run_slm2_pipeline(
    claim_text: str,
    evidence_topk: list,
    language: str = "ko",
) -> dict:
    """
    Stage 6-8 파이프라인 실행.

    Returns:
        {
            "trace_id": str,
            "verdict_support": dict,
            "verdict_skeptic": dict,
            "draft_verdict": dict,
            "quality_score": int,
            "latency_ms": int,
        }
    """
    from app.stages.stage06_verify_support.node import run as stage6_run
    from app.stages.stage07_verify_skeptic.node import run as stage7_run
    from app.stages.stage08_aggregate.node import run as stage8_run

    trace_id = str(uuid.uuid4())[:8]

    state = {
        "trace_id": trace_id,
        "claim_text": claim_text,
        "language": language,
        "evidence_topk": evidence_topk,
    }

    start_time = time.time()

    # Stage 6: Supportive
    logger.info(f"[{trace_id}] Stage 6 실행 중...")
    state = stage6_run(state)

    # Stage 7: Skeptic
    logger.info(f"[{trace_id}] Stage 7 실행 중...")
    state = stage7_run(state)

    # Stage 8: Aggregate
    logger.info(f"[{trace_id}] Stage 8 실행 중...")
    state = stage8_run(state)

    elapsed_ms = int((time.time() - start_time) * 1000)
    state["latency_ms"] = elapsed_ms

    return state


def print_result(case: dict, result: dict):
    """결과 출력."""
    print("\n" + "=" * 70)
    print(f"테스트 케이스 #{case['id']}: {case['name']}")
    print("=" * 70)

    print(f"\n[주장] {case['claim_text']}")
    print(f"[증거 수] {len(case['evidence_topk'])}")
    print(f"[예상 결과] {case['expected_stance']}")

    draft = result.get("draft_verdict", {})
    print(f"\n[실제 결과]")
    print(f"  - stance: {draft.get('stance')}")
    print(f"  - confidence: {draft.get('confidence', 0):.2f}")
    print(f"  - citations: {len(draft.get('citations', []))}개")
    print(f"  - quality_score: {result.get('quality_score', 0)}")
    print(f"  - latency: {result.get('latency_ms', 0)}ms")

    # 상세 정보
    if draft.get("reasoning_bullets"):
        print(f"\n[추론 근거]")
        for bullet in draft["reasoning_bullets"][:5]:
            print(f"  • {bullet}")

    if draft.get("citations"):
        print(f"\n[인용]")
        for cit in draft["citations"][:3]:
            print(f"  • [{cit.get('evid_id')}] {cit.get('quote', '')[:50]}...")

    # 일치 여부
    match = draft.get("stance") == case["expected_stance"]
    status = "✓ PASS" if match else "✗ FAIL"
    print(f"\n[결과] {status}")

    return match


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="SLM2 파이프라인 데모")
    parser.add_argument("--case", type=int, help="특정 테스트 케이스만 실행 (1-5)")
    parser.add_argument("--all", action="store_true", help="모든 테스트 케이스 실행")
    args = parser.parse_args()

    print("=" * 70)
    print("SLM2 파이프라인 데모 (Stage 6-8)")
    print("=" * 70)

    # 연결 확인
    try:
        from app.stages._shared.slm_client import SLMConfig
        config = SLMConfig.from_env()
        print(f"\nSLM 서버: {config.base_url}")
        print(f"모델: {config.model}")
        print(f"max_tokens: {config.max_tokens}")
    except Exception as e:
        logger.error(f"설정 로드 실패: {e}")
        sys.exit(1)

    # 테스트 케이스 선택
    if args.case:
        cases = [c for c in TEST_CASES if c["id"] == args.case]
        if not cases:
            print(f"케이스 #{args.case}를 찾을 수 없습니다.")
            sys.exit(1)
    elif args.all:
        cases = TEST_CASES
    else:
        # 기본: 첫 번째 케이스만
        cases = TEST_CASES[:1]
        print("\n(기본: 케이스 #1만 실행. --all 옵션으로 전체 실행)")

    # 실행
    passed = 0
    failed = 0

    for case in cases:
        try:
            result = run_slm2_pipeline(
                claim_text=case["claim_text"],
                evidence_topk=case["evidence_topk"],
            )
            if print_result(case, result):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.exception(f"케이스 #{case['id']} 실행 실패: {e}")
            failed += 1

    # 요약
    print("\n" + "=" * 70)
    print(f"결과 요약: {passed}/{passed + failed} 통과")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
