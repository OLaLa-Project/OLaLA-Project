"""
SLM2 Stages (6-8) 테스트 스크립트.

실행 방법:
    cd backend
    python -m tests.test_slm2_stages

필수 테스트 항목:
1. JSON 파싱 실패 → 재요청 동작
2. quote 검증 실패 citation 제거 + citations==0 → UNVERIFIED 강제
3. A/B 병합 규칙 동작
"""

import sys
import json
import logging
from typing import Callable
from unittest.mock import patch, MagicMock

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Test Utilities
# ============================================================================

class TestResult:
    """테스트 결과 추적."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str):
        self.passed += 1
        print(f"  ✓ {name}")

    def fail(self, name: str, reason: str):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  ✗ {name}: {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"결과: {self.passed}/{total} 통과")
        if self.errors:
            print("\n실패 목록:")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        return self.failed == 0


# ============================================================================
# Test 1: JSON 파싱 및 재시도
# ============================================================================

def test_json_parsing(results: TestResult):
    """JSON 파싱 및 재시도 테스트."""
    print("\n[Test 1] JSON 파싱 및 재시도")

    from app.stages._shared.guardrails import (
        parse_json_safe,
        extract_json_from_text,
        parse_json_with_retry,
        JSONParseError,
    )

    # 1.1 정상 JSON 파싱
    valid_json = '{"stance": "TRUE", "confidence": 0.8}'
    result = parse_json_safe(valid_json)
    if result and result.get("stance") == "TRUE":
        results.ok("정상 JSON 파싱")
    else:
        results.fail("정상 JSON 파싱", f"결과: {result}")

    # 1.2 마크다운 코드블록에서 JSON 추출
    markdown_json = """
    Here is the analysis:
    ```json
    {"stance": "FALSE", "confidence": 0.9}
    ```
    """
    result = parse_json_safe(markdown_json)
    if result and result.get("stance") == "FALSE":
        results.ok("마크다운 코드블록에서 JSON 추출")
    else:
        results.fail("마크다운 코드블록에서 JSON 추출", f"결과: {result}")

    # 1.3 불완전 JSON → None 반환
    invalid_json = '{"stance": "TRUE", "confidence":'
    result = parse_json_safe(invalid_json)
    if result is None:
        results.ok("불완전 JSON → None 반환")
    else:
        results.fail("불완전 JSON → None 반환", f"결과: {result}")

    # 1.4 재시도 로직 테스트
    call_count = 0

    def mock_call_fn():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "This is not valid JSON"
        return '{"stance": "TRUE", "confidence": 0.7}'

    result = parse_json_with_retry(mock_call_fn)
    if call_count == 2 and result.get("stance") == "TRUE":
        results.ok("JSON 파싱 실패 시 재시도")
    else:
        results.fail("JSON 파싱 실패 시 재시도", f"호출횟수: {call_count}, 결과: {result}")

    # 1.5 재시도 후에도 실패 → 예외 발생
    def always_fail_fn():
        return "Never valid JSON {"

    try:
        parse_json_with_retry(always_fail_fn)
        results.fail("재시도 후 실패 시 예외", "예외가 발생하지 않음")
    except JSONParseError:
        results.ok("재시도 후 실패 시 예외 발생")


# ============================================================================
# Test 2: Quote 검증 및 UNVERIFIED 강제
# ============================================================================

def test_quote_validation(results: TestResult):
    """Quote 검증 및 UNVERIFIED 강제 테스트."""
    print("\n[Test 2] Quote 검증 및 UNVERIFIED 강제")

    from app.stages._shared.guardrails import (
        validate_citations,
        enforce_unverified_if_no_citations,
        build_draft_verdict,
    )

    # 테스트용 증거
    evidence_topk = [
        {
            "evid_id": "ev_1",
            "title": "뉴스 기사 1",
            "url": "https://example.com/1",
            "snippet": "서울시는 2024년 예산을 10조원으로 확정했다고 발표했다.",
            "source_type": "NEWS",
        },
        {
            "evid_id": "ev_2",
            "title": "공식 보도자료",
            "url": "https://example.com/2",
            "snippet": "정부는 새로운 정책을 시행한다고 밝혔다.",
            "source_type": "WEB_URL",
        },
    ]

    # 2.1 유효한 quote → 통과
    valid_citations = [
        {"evid_id": "ev_1", "quote": "서울시는 2024년 예산을 10조원으로 확정했다"},
    ]
    validated = validate_citations(valid_citations, evidence_topk)
    if len(validated) == 1:
        results.ok("유효한 quote 검증 통과")
    else:
        results.fail("유효한 quote 검증 통과", f"통과 수: {len(validated)}")

    # 2.2 snippet에 없는 quote → 제거
    invalid_citations = [
        {"evid_id": "ev_1", "quote": "이것은 snippet에 없는 문장입니다"},
    ]
    validated = validate_citations(invalid_citations, evidence_topk)
    if len(validated) == 0:
        results.ok("무효한 quote 제거")
    else:
        results.fail("무효한 quote 제거", f"통과 수: {len(validated)}")

    # 2.3 evid_id 불일치 → 제거
    wrong_evid_citations = [
        {"evid_id": "ev_999", "quote": "서울시는 2024년 예산"},
    ]
    validated = validate_citations(wrong_evid_citations, evidence_topk)
    if len(validated) == 0:
        results.ok("evid_id 불일치 제거")
    else:
        results.fail("evid_id 불일치 제거", f"통과 수: {len(validated)}")

    # 2.4 citations=0 → UNVERIFIED 강제
    verdict_with_stance = {
        "stance": "TRUE",
        "confidence": 0.9,
        "citations": [],
    }
    enforced = enforce_unverified_if_no_citations(verdict_with_stance)
    if enforced["stance"] == "UNVERIFIED" and enforced["confidence"] == 0.0:
        results.ok("citations=0 → UNVERIFIED 강제")
    else:
        results.fail("citations=0 → UNVERIFIED 강제", f"stance: {enforced['stance']}")

    # 2.5 build_draft_verdict 통합 테스트
    raw_verdict = {
        "stance": "TRUE",
        "confidence": 0.9,
        "reasoning_bullets": ["근거 1"],
        "citations": [
            {"evid_id": "ev_1", "quote": "예산을 10조원으로 확정"},  # 유효
            {"evid_id": "ev_1", "quote": "이건 없는 내용"},  # 무효
        ],
        "weak_points": [],
        "followup_queries": [],
    }
    built = build_draft_verdict(raw_verdict, evidence_topk)
    if len(built["citations"]) == 1 and built["stance"] == "TRUE":
        results.ok("build_draft_verdict 통합 (유효 citation 유지)")
    else:
        results.fail("build_draft_verdict 통합", f"citations: {len(built['citations'])}")


# ============================================================================
# Test 3: A/B 병합 규칙
# ============================================================================

def test_aggregate_rules(results: TestResult):
    """A/B 병합 규칙 테스트."""
    print("\n[Test 3] A/B 병합 규칙")

    from app.stages.stage08_aggregate.node import (
        determine_final_stance,
        calculate_final_confidence,
        merge_citations,
        run as aggregate_run,
    )

    # 3.1 둘 다 UNVERIFIED → UNVERIFIED
    stance = determine_final_stance("UNVERIFIED", "UNVERIFIED", has_citations=False)
    if stance == "UNVERIFIED":
        results.ok("UNVERIFIED + UNVERIFIED → UNVERIFIED")
    else:
        results.fail("UNVERIFIED + UNVERIFIED → UNVERIFIED", f"결과: {stance}")

    # 3.2 합의 (TRUE + TRUE) + citations → TRUE
    stance = determine_final_stance("TRUE", "TRUE", has_citations=True)
    if stance == "TRUE":
        results.ok("TRUE + TRUE + citations → TRUE")
    else:
        results.fail("TRUE + TRUE + citations → TRUE", f"결과: {stance}")

    # 3.3 합의 (FALSE + FALSE) + citations → FALSE
    stance = determine_final_stance("FALSE", "FALSE", has_citations=True)
    if stance == "FALSE":
        results.ok("FALSE + FALSE + citations → FALSE")
    else:
        results.fail("FALSE + FALSE + citations → FALSE", f"결과: {stance}")

    # 3.4 불합의 (TRUE vs FALSE) → MIXED
    stance = determine_final_stance("TRUE", "FALSE", has_citations=True)
    if stance == "MIXED":
        results.ok("TRUE vs FALSE → MIXED")
    else:
        results.fail("TRUE vs FALSE → MIXED", f"결과: {stance}")

    # 3.5 citations 없으면 → UNVERIFIED
    stance = determine_final_stance("TRUE", "TRUE", has_citations=False)
    if stance == "UNVERIFIED":
        results.ok("합의해도 citations 없으면 → UNVERIFIED")
    else:
        results.fail("합의해도 citations 없으면 → UNVERIFIED", f"결과: {stance}")

    # 3.6 한쪽만 UNVERIFIED → 다른 쪽 따라감
    stance = determine_final_stance("TRUE", "UNVERIFIED", has_citations=True)
    if stance == "TRUE":
        results.ok("TRUE + UNVERIFIED → TRUE")
    else:
        results.fail("TRUE + UNVERIFIED → TRUE", f"결과: {stance}")

    # 3.7 confidence 계산 - 합의
    conf = calculate_final_confidence(0.8, 0.6, "TRUE", "TRUE", "TRUE")
    if abs(conf - 0.7) < 0.01:
        results.ok("confidence 합의 시 평균")
    else:
        results.fail("confidence 합의 시 평균", f"결과: {conf}")

    # 3.8 confidence 계산 - 불합의 (페널티)
    conf = calculate_final_confidence(0.8, 0.8, "MIXED", "TRUE", "FALSE")
    if conf < 0.8:
        results.ok("confidence 불합의 시 페널티")
    else:
        results.fail("confidence 불합의 시 페널티", f"결과: {conf}")

    # 3.9 Stage8 통합 테스트
    state = {
        "trace_id": "test_001",
        "verdict_support": {
            "stance": "TRUE",
            "confidence": 0.8,
            "reasoning_bullets": ["지지 근거"],
            "citations": [{"evid_id": "ev_1", "quote": "인용문"}],
            "weak_points": [],
            "followup_queries": [],
        },
        "verdict_skeptic": {
            "stance": "TRUE",
            "confidence": 0.7,
            "reasoning_bullets": ["반박 시도했으나 지지"],
            "citations": [{"evid_id": "ev_2", "quote": "다른 인용"}],
            "weak_points": [],
            "followup_queries": [],
        },
    }
    result_state = aggregate_run(state)
    draft = result_state.get("draft_verdict", {})
    quality = result_state.get("quality_score", 0)

    if draft.get("stance") == "TRUE" and len(draft.get("citations", [])) == 2:
        results.ok("Stage8 통합 테스트 (합의 병합)")
    else:
        results.fail("Stage8 통합 테스트", f"stance: {draft.get('stance')}, cits: {len(draft.get('citations', []))}")

    if quality > 0:
        results.ok(f"quality_score 계산: {quality}")
    else:
        results.fail("quality_score 계산", f"결과: {quality}")


# ============================================================================
# Test 4: Stage6/7 노드 테스트 (Mock SLM)
# ============================================================================

def test_stage_nodes_with_mock(results: TestResult):
    """Stage 6/7 노드 테스트 (Mock SLM)."""
    print("\n[Test 4] Stage 6/7 노드 테스트 (Mock SLM)")

    # Mock SLM 응답
    mock_slm_response = json.dumps({
        "stance": "TRUE",
        "confidence": 0.85,
        "reasoning_bullets": ["근거 1", "근거 2"],
        "citations": [
            {"evid_id": "ev_1", "quote": "서울시는 예산을 확정", "title": "뉴스", "url": "https://example.com"}
        ],
        "weak_points": ["한계점"],
        "followup_queries": ["추가 질문"],
    })

    test_state = {
        "trace_id": "test_stage",
        "claim_text": "서울시 예산이 10조원이다",
        "language": "ko",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "뉴스 기사",
                "url": "https://example.com",
                "snippet": "서울시는 예산을 확정했다고 발표했다.",
                "source_type": "NEWS",
            }
        ],
    }

    # Stage 6 테스트
    with patch("app.stages._shared.slm_client.call_slm", return_value=mock_slm_response):
        from app.stages.stage06_verify_support.node import run as stage6_run
        result = stage6_run(test_state.copy())

        if "verdict_support" in result:
            verdict = result["verdict_support"]
            if verdict.get("stance") == "TRUE":
                results.ok("Stage6 실행 성공")
            else:
                results.fail("Stage6 실행", f"stance: {verdict.get('stance')}")
        else:
            results.fail("Stage6 실행", "verdict_support 없음")

    # Stage 7 테스트
    mock_skeptic_response = json.dumps({
        "stance": "MIXED",
        "confidence": 0.6,
        "reasoning_bullets": ["반박 근거"],
        "citations": [
            {"evid_id": "ev_1", "quote": "예산을 확정", "title": "뉴스", "url": "https://example.com"}
        ],
        "weak_points": [],
        "followup_queries": [],
    })

    with patch("app.stages._shared.slm_client.call_slm", return_value=mock_skeptic_response):
        from app.stages.stage07_verify_skeptic.node import run as stage7_run
        result = stage7_run(test_state.copy())

        if "verdict_skeptic" in result:
            verdict = result["verdict_skeptic"]
            if verdict.get("stance") in ["TRUE", "FALSE", "MIXED", "UNVERIFIED"]:
                results.ok("Stage7 실행 성공")
            else:
                results.fail("Stage7 실행", f"stance: {verdict.get('stance')}")
        else:
            results.fail("Stage7 실행", "verdict_skeptic 없음")


# ============================================================================
# Test 5: 에지 케이스
# ============================================================================

def test_edge_cases(results: TestResult):
    """에지 케이스 테스트."""
    print("\n[Test 5] 에지 케이스")

    from app.stages._shared.guardrails import (
        validate_stance,
        validate_confidence,
        normalize_whitespace,
    )
    from app.stages.stage08_aggregate.node import run as aggregate_run

    # 5.1 잘못된 stance → UNVERIFIED
    stance = validate_stance("INVALID_STANCE")
    if stance == "UNVERIFIED":
        results.ok("잘못된 stance → UNVERIFIED")
    else:
        results.fail("잘못된 stance → UNVERIFIED", f"결과: {stance}")

    # 5.2 confidence 범위 검증
    conf = validate_confidence(1.5)
    if conf == 1.0:
        results.ok("confidence > 1.0 → 1.0")
    else:
        results.fail("confidence > 1.0 → 1.0", f"결과: {conf}")

    conf = validate_confidence(-0.5)
    if conf == 0.0:
        results.ok("confidence < 0.0 → 0.0")
    else:
        results.fail("confidence < 0.0 → 0.0", f"결과: {conf}")

    conf = validate_confidence("invalid")
    if conf == 0.0:
        results.ok("confidence 문자열 → 0.0")
    else:
        results.fail("confidence 문자열 → 0.0", f"결과: {conf}")

    # 5.3 공백 정규화
    text = "  Hello   World  \n\t Test  "
    normalized = normalize_whitespace(text)
    if normalized == "hello world test":
        results.ok("공백 정규화")
    else:
        results.fail("공백 정규화", f"결과: '{normalized}'")

    # 5.4 빈 입력으로 Stage8 실행
    empty_state = {"trace_id": "empty_test"}
    result = aggregate_run(empty_state)
    if result.get("draft_verdict", {}).get("stance") == "UNVERIFIED":
        results.ok("빈 입력 시 UNVERIFIED")
    else:
        results.fail("빈 입력 시 UNVERIFIED", f"결과: {result.get('draft_verdict')}")


# ============================================================================
# Main
# ============================================================================

def main():
    """메인 테스트 실행."""
    print("=" * 60)
    print("SLM2 Stages (6-8) 테스트")
    print("=" * 60)

    results = TestResult()

    try:
        test_json_parsing(results)
        test_quote_validation(results)
        test_aggregate_rules(results)
        test_stage_nodes_with_mock(results)
        test_edge_cases(results)
    except Exception as e:
        logger.exception(f"테스트 중 예외 발생: {e}")
        results.fail("테스트 실행", str(e))

    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
