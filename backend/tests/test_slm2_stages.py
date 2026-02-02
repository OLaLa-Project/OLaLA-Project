"""
SLM2 Stages (6-7) + Stage 8 Aggregator ?뚯뒪???ㅽ겕由쏀듃.

?ㅽ뻾 諛⑸쾿:
    cd backend
    python -m tests.test_slm2_stages

?꾩닔 ?뚯뒪????ぉ:
1. JSON ?뚯떛 ?ㅽ뙣 ???ъ슂泥??숈옉
2. quote 寃利??ㅽ뙣 citation ?쒓굅 + citations==0 ??UNVERIFIED 媛뺤젣
3. A/B 蹂묓빀 洹쒖튃 ?숈옉
"""

import sys
import json
import logging
from typing import Callable
from unittest.mock import patch, MagicMock

# 濡쒓퉭 ?ㅼ젙
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Test Utilities
# ============================================================================

class TestResult:
    """?뚯뒪??寃곌낵 異붿쟻."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def ok(self, name: str):
        self.passed += 1
        print(f"  ??{name}")

    def fail(self, name: str, reason: str):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  ??{name}: {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"寃곌낵: {self.passed}/{total} ?듦낵")
        if self.errors:
            print("\n?ㅽ뙣 紐⑸줉:")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        return self.failed == 0


# ============================================================================
# Test 1: JSON ?뚯떛 諛??ъ떆??
# ============================================================================

def test_json_parsing(results: TestResult):
    """JSON ?뚯떛 諛??ъ떆???뚯뒪??"""
    print("\n[Test 1] JSON parsing retry")

    from app.stages._shared.guardrails import (
        parse_json_safe,
        extract_json_from_text,
        parse_json_with_retry,
        JSONParseError,
    )

    # 1.1 ?뺤긽 JSON ?뚯떛
    valid_json = '{"stance": "TRUE", "confidence": 0.8}'
    result = parse_json_safe(valid_json)
    if result and result.get("stance") == "TRUE":
        results.ok("normalize whitespace")
    else:
        results.fail("unexpected error", f"{e}")

    # 1.2 留덊겕?ㅼ슫 肄붾뱶釉붾줉?먯꽌 JSON 異붿텧
    markdown_json = """
    Here is the analysis:
    ```json
    {"stance": "FALSE", "confidence": 0.9}
    ```
    """
    result = parse_json_safe(markdown_json)
    if result and result.get("stance") == "FALSE":
        results.ok("留덊겕?ㅼ슫 肄붾뱶釉붾줉?먯꽌 JSON 異붿텧")
    else:
        results.fail("留덊겕?ㅼ슫 肄붾뱶釉붾줉?먯꽌 JSON 異붿텧", f"寃곌낵: {result}")

    # 1.3 遺덉셿??JSON ??None 諛섑솚
    invalid_json = '{"stance": "TRUE", "confidence":'
    result = parse_json_safe(invalid_json)
    if result is None:
        results.ok("遺덉셿??JSON ??None 諛섑솚")
    else:
        results.fail("遺덉셿??JSON ??None 諛섑솚", f"寃곌낵: {result}")

    # 1.4 ?ъ떆??濡쒖쭅 ?뚯뒪??
    call_count = 0

    def mock_call_fn():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "This is not valid JSON"
        return '{"stance": "TRUE", "confidence": 0.7}'

    result = parse_json_with_retry(mock_call_fn)
    if call_count == 2 and result.get("stance") == "TRUE":
        results.ok("JSON parse retry")
    else:
        results.fail("JSON parse retry", f"call_count={call_count}, result={result}")

    # 1.5 ?ъ떆???꾩뿉???ㅽ뙣 ???덉쇅 諛쒖깮
    def always_fail_fn():
        return "Never valid JSON {"

    try:
        parse_json_with_retry(always_fail_fn)
        results.fail("unexpected error", f"{e}")
    except JSONParseError:
        results.ok("normalize whitespace")


# ============================================================================
# Test 2: Quote 寃利?諛?UNVERIFIED 媛뺤젣
# ============================================================================

def test_quote_validation(results: TestResult):
    """Quote 寃利?諛?UNVERIFIED 媛뺤젣 ?뚯뒪??"""
    print("\n[Test 2] Quote 寃利?諛?UNVERIFIED 媛뺤젣")

    from app.stages._shared.guardrails import (
        validate_citations,
        enforce_unverified_if_no_citations,
        build_draft_verdict,
    )

    # ?뚯뒪?몄슜 利앷굅
    evidence_topk = [
        {
            "evid_id": "ev_1",
            "title": "?댁뒪 湲곗궗 1",
            "url": "https://example.com/1",
            "snippet": "?쒖슱?쒕뒗 2024???덉궛??10議곗썝?쇰줈 ?뺤젙?덈떎怨?諛쒗몴?덈떎.",
            "source_type": "NEWS",
        },
        {
            "evid_id": "ev_2",
            "title": "怨듭떇 蹂대룄?먮즺",
            "url": "https://example.com/2",
            "snippet": "?뺣????덈줈???뺤콉???쒗뻾?쒕떎怨?諛앺삍??",
            "source_type": "WEB_URL",
        },
    ]

    # 2.1 valid quote should pass
    valid_citations = [
        {"evid_id": "ev_1", "quote": "서울"},
    ]
    validated = validate_citations(valid_citations, evidence_topk)
    if len(validated) == 1:
        results.ok("valid quote passes")
    else:
        results.fail("valid quote passes", f"passed={len(validated)}")

    # 2.2 invalid quote should be removed
    invalid_citations = [
        {"evid_id": "ev_1", "quote": "no match content"},
    ]
    validated = validate_citations(invalid_citations, evidence_topk)
    if len(validated) == 0:
        results.ok("invalid quote removed")
    else:
        results.fail("invalid quote removed", f"passed={len(validated)}")
    invalid_citations = [
        {"evid_id": "ev_1", "quote": "invalid quote with no snippet"},
    ]
    validated = validate_citations(invalid_citations, evidence_topk)
    if len(validated) == 0:
        results.ok("臾댄슚??quote ?쒓굅")
    else:
        results.fail("臾댄슚??quote ?쒓굅", f"?듦낵 ?? {len(validated)}")

    # 2.3 evid_id 遺덉씪移????쒓굅
    wrong_evid_citations = [
        {"evid_id": "ev_999", "quote": "?쒖슱?쒕뒗 2024???덉궛"},
    ]
    validated = validate_citations(wrong_evid_citations, evidence_topk)
    if len(validated) == 0:
        results.ok("evid_id 遺덉씪移??쒓굅")
    else:
        results.fail("evid_id 遺덉씪移??쒓굅", f"?듦낵 ?? {len(validated)}")

    # 2.4 citations=0 ??UNVERIFIED 媛뺤젣
    verdict_with_stance = {
        "stance": "TRUE",
        "confidence": 0.9,
        "citations": [],
    }
    enforced = enforce_unverified_if_no_citations(verdict_with_stance)
    if enforced["stance"] == "UNVERIFIED" and enforced["confidence"] == 0.0:
        results.ok("citations=0 ??UNVERIFIED 媛뺤젣")
    else:
        results.fail("citations=0 ??UNVERIFIED 媛뺤젣", f"stance: {enforced['stance']}")

    # 2.5 build_draft_verdict ?듯빀 ?뚯뒪??
    raw_verdict = {
        "stance": "TRUE",
        "confidence": 0.9,
        "reasoning_bullets": ["洹쇨굅 1"],
        "citations": [
        {"evid_id": "ev_1", "quote": "invalid quote with no snippet"},
        {"evid_id": "ev_1", "quote": "invalid quote with no snippet"},
        ],
        "weak_points": ["weak point"],
        "followup_queries": [],
    }
    built = build_draft_verdict(raw_verdict, evidence_topk)
    if len(built["citations"]) == 1 and built["stance"] == "TRUE":
        results.ok("build_draft_verdict ?듯빀 (?좏슚 citation ?좎?)")
    else:
        results.fail("build_draft_verdict ?듯빀", f"citations: {len(built['citations'])}")


# ============================================================================
# Test 3: A/B 蹂묓빀 洹쒖튃
# ============================================================================

def test_aggregate_rules(results: TestResult):
    """A/B 蹂묓빀 洹쒖튃 ?뚯뒪??"""
    print("\n[Test 3] A/B 蹂묓빀 洹쒖튃")

    from app.stages.stage08_aggregate.node import (
        determine_final_stance,
        calculate_final_confidence,
        merge_citations,
        run as aggregate_run,
    )

    # 3.1 ????UNVERIFIED ??UNVERIFIED
    stance = determine_final_stance("UNVERIFIED", "UNVERIFIED", has_citations=False)
    if stance == "UNVERIFIED":
        results.ok("UNVERIFIED + UNVERIFIED ??UNVERIFIED")
    else:
        results.fail("UNVERIFIED + UNVERIFIED ??UNVERIFIED", f"寃곌낵: {stance}")

    # 3.2 ?⑹쓽 (TRUE + TRUE) + citations ??TRUE
    stance = determine_final_stance("TRUE", "TRUE", has_citations=True)
    if stance == "TRUE":
        results.ok("TRUE + TRUE + citations ??TRUE")
    else:
        results.fail("TRUE + TRUE + citations ??TRUE", f"寃곌낵: {stance}")

    # 3.3 ?⑹쓽 (FALSE + FALSE) + citations ??FALSE
    stance = determine_final_stance("FALSE", "FALSE", has_citations=True)
    if stance == "FALSE":
        results.ok("FALSE + FALSE + citations ??FALSE")
    else:
        results.fail("FALSE + FALSE + citations ??FALSE", f"寃곌낵: {stance}")

    # 3.4 遺덊빀??(TRUE vs FALSE) ??MIXED
    stance = determine_final_stance("TRUE", "FALSE", has_citations=True)
    if stance == "MIXED":
        results.ok("TRUE vs FALSE ??MIXED")
    else:
        results.fail("TRUE vs FALSE ??MIXED", f"寃곌낵: {stance}")

    # 3.5 citations ?놁쑝硫???UNVERIFIED
    stance = determine_final_stance("TRUE", "TRUE", has_citations=False)
    if stance == "UNVERIFIED":
        results.ok("normalize whitespace")
    else:
        results.fail("unexpected error", f"{e}")

    # 3.6 ?쒖そ留?UNVERIFIED ???ㅻⅨ 履??곕씪媛?
    stance = determine_final_stance("TRUE", "UNVERIFIED", has_citations=True)
    if stance == "TRUE":
        results.ok("TRUE + UNVERIFIED ??TRUE")
    else:
        results.fail("TRUE + UNVERIFIED ??TRUE", f"寃곌낵: {stance}")

    # 3.7 confidence 怨꾩궛 - ?⑹쓽
    conf = calculate_final_confidence(0.8, 0.6, "TRUE", "TRUE", "TRUE")
    if abs(conf - 0.7) < 0.01:
        results.ok("confidence conflict penalty")
    else:
        results.fail("confidence conflict penalty", f"result={conf}")

    # 3.8 confidence 怨꾩궛 - 遺덊빀??(?섎꼸??
    conf = calculate_final_confidence(0.8, 0.8, "MIXED", "TRUE", "FALSE")
    if conf < 0.8:
        results.ok("confidence conflict penalty")
    else:
        results.fail("confidence conflict penalty", f"result={conf}")

    # 3.9 Stage8 ?듯빀 ?뚯뒪??
    state = {
        "trace_id": "test_001",
        "verdict_support": {
            "stance": "TRUE",
            "confidence": 0.8,
            "reasoning_bullets": ["support reason"],
            "citations": [{"evid_id": "ev_1", "quote": "sample quote"}],
            "weak_points": ["weak point"],
            "followup_queries": [],
        },
        "verdict_skeptic": {
            "stance": "TRUE",
            "confidence": 0.7,
            "reasoning_bullets": ["skeptic reason"],
            "citations": [{"evid_id": "ev_2", "quote": "other quote"}],
            "weak_points": ["weak point"],
            "followup_queries": [],
        },
    }
    result_state = aggregate_run(state)
    draft = result_state.get("draft_verdict", {})
    quality = result_state.get("quality_score", 0)

    if draft.get("stance") == "TRUE" and len(draft.get("citations", [])) == 2:
        results.ok("Stage8 ?듯빀 ?뚯뒪??(?⑹쓽 蹂묓빀)")
    else:
        results.fail("Stage8 aggregate test", f"stance={draft.get('stance')}, cits={len(draft.get('citations', []))}")

    if quality > 0:
        results.ok(f"quality_score 怨꾩궛: {quality}")
    else:
        results.fail("quality_score 怨꾩궛", f"寃곌낵: {quality}")


# ============================================================================
# Test 4: Stage6/7 ?몃뱶 ?뚯뒪??(Mock SLM)
# ============================================================================

def test_stage_nodes_with_mock(results: TestResult):
    """Stage 6/7 ?몃뱶 ?뚯뒪??(Mock SLM)."""
    print("\n[Test 4] Stage 6/7 ?몃뱶 ?뚯뒪??(Mock SLM)")

    # Mock SLM ?묐떟
    mock_slm_response = json.dumps({
        "stance": "TRUE",
        "confidence": 0.85,
        "reasoning_bullets": ["洹쇨굅 1", "洹쇨굅 2"],
        "citations": [
        {"evid_id": "ev_1", "quote": "invalid quote with no snippet"},
        ],
        "weak_points": ["weak point"],
        "followup_queries": ["異붽? 吏덈Ц"],
    })

    test_state = {
        "trace_id": "test_stage",
        "claim_text": "?쒖슱???덉궛??10議곗썝?대떎",
        "language": "ko",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "?댁뒪 湲곗궗",
                "url": "https://example.com",
                "snippet": "?쒖슱?쒕뒗 ?덉궛???뺤젙?덈떎怨?諛쒗몴?덈떎.",
                "source_type": "NEWS",
            }
        ],
    }

    # Stage 6 ?뚯뒪??
    with patch("app.stages._shared.slm_client.call_slm", return_value=mock_slm_response):
        from app.stages.stage06_verify_support.node import run as stage6_run
        result = stage6_run(test_state.copy())

        if "verdict_support" in result:
            verdict = result["verdict_support"]
            if verdict.get("stance") == "TRUE":
                results.ok("Stage6 ?ㅽ뻾 ?깃났")
            else:
                results.fail("Stage6 ?ㅽ뻾", f"stance: {verdict.get('stance')}")
        else:
            results.fail("Stage6 ?ㅽ뻾", "verdict_support ?놁쓬")

    # Stage 7 ?뚯뒪??
    mock_skeptic_response = json.dumps({
        "stance": "MIXED",
        "confidence": 0.6,
        "reasoning_bullets": ["諛섎컯 洹쇨굅"],
        "citations": [
        {"evid_id": "ev_1", "quote": "invalid quote with no snippet"},
        ],
        "weak_points": ["weak point"],
        "followup_queries": [],
    })

    with patch("app.stages._shared.slm_client.call_slm", return_value=mock_skeptic_response):
        from app.stages.stage07_verify_skeptic.node import run as stage7_run
        result = stage7_run(test_state.copy())

        if "verdict_skeptic" in result:
            verdict = result["verdict_skeptic"]
            if verdict.get("stance") in ["TRUE", "FALSE", "MIXED", "UNVERIFIED"]:
                results.ok("Stage7 ?ㅽ뻾 ?깃났")
            else:
                results.fail("Stage7 ?ㅽ뻾", f"stance: {verdict.get('stance')}")
        else:
            results.fail("Stage7 ?ㅽ뻾", "verdict_skeptic ?놁쓬")


# ============================================================================
# Test 5: ?먯? 耳?댁뒪
# ============================================================================

def test_edge_cases(results: TestResult):
    """?먯? 耳?댁뒪 ?뚯뒪??"""
    print("\n[Test 5] ?먯? 耳?댁뒪")

    from app.stages._shared.guardrails import (
        validate_stance,
        validate_confidence,
        normalize_whitespace,
    )
    from app.stages.stage08_aggregate.node import run as aggregate_run

    # 5.1 ?섎せ??stance ??UNVERIFIED
    stance = validate_stance("INVALID_STANCE")
    if stance == "UNVERIFIED":
        results.ok("normalize whitespace")
    else:
        results.fail("unexpected error", f"{e}")

    # 5.2 confidence 踰붿쐞 寃利?
    conf = validate_confidence(1.5)
    if conf == 1.0:
        results.ok("confidence conflict penalty")
    else:
        results.fail("confidence conflict penalty", f"result={conf}")

    conf = validate_confidence(-0.5)
    if conf == 0.0:
        results.ok("confidence conflict penalty")
    else:
        results.fail("confidence conflict penalty", f"result={conf}")

    conf = validate_confidence("invalid")
    if conf == 0.0:
        results.ok("confidence conflict penalty")
    else:
        results.fail("confidence conflict penalty", f"result={conf}")

    # 5.3 怨듬갚 ?뺢퇋??
    text = "  Hello   World  \n\t Test  "
    normalized = normalize_whitespace(text)
    if normalized == "hello world test":
        results.ok("normalize whitespace")
    else:
        results.fail("normalize whitespace", f"result=''{normalized}''")

    # 5.4 鍮??낅젰?쇰줈 Stage8 ?ㅽ뻾
    empty_state = {"trace_id": "empty_test"}
    result = aggregate_run(empty_state)
    if result.get("draft_verdict", {}).get("stance") == "UNVERIFIED":
        results.ok("鍮??낅젰 ??UNVERIFIED")
    else:
        results.fail("鍮??낅젰 ??UNVERIFIED", f"寃곌낵: {result.get('draft_verdict')}")


# ============================================================================
# Main
# ============================================================================

def main():
    """硫붿씤 ?뚯뒪???ㅽ뻾."""
    print("=" * 60)
    print("SLM2 Stages (6-7) + Stage 8 Aggregator tests")
    print("=" * 60)

    results = TestResult()

    try:
        test_json_parsing(results)
        test_quote_validation(results)
        test_aggregate_rules(results)
        test_stage_nodes_with_mock(results)
        test_edge_cases(results)
    except Exception as e:
        logger.exception(f"?뚯뒪??以??덉쇅 諛쒖깮: {e}")
        results.fail("unexpected error", f"{e}")

    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

