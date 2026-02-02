"""
SLM2 ?뚯씠?꾨씪???곕え ?ㅽ겕由쏀듃.

OpenAI-compatible SLM ?쒕쾭(vLLM ?먮뒗 Ollama)瑜??ъ슜?섏뿬 Stage 6-7 + Stage 8 Aggregator ?뚯씠?꾨씪?몄쓣 ?뚯뒪?명빀?덈떎.

?ㅽ뻾 ??以鍮?
1. SLM ?쒕쾭 ?ㅽ뻾:
   - Ollama: docker compose up -d ollama && docker exec olala-project-ollama-1 ollama pull llama3.2
   - vLLM: docker-compose?먯꽌 vllm ?쒕퉬??二쇱꽍 ?댁젣 ???ㅽ뻾
2. ?섍꼍蹂???ㅼ젙 (.env ?뚯씪 ?먮뒗 吏곸젒 export):
   - SLM_BASE_URL: Ollama??http://ollama:11434/v1, vLLM? http://localhost:8001/v1
   - SLM_API_KEY: Ollama??"ollama", vLLM? "local-slm-key"
   - SLM_MODEL: Ollama ?덉떆 "llama3.2", vLLM ?덉떆 "slm"

?ㅽ뻾 諛⑸쾿 (濡쒖뺄):
    cd backend
    python -m tests.demo_slm2_pipeline
    python -m tests.demo_slm2_pipeline --case 1

?ㅽ뻾 諛⑸쾿 (Docker):
    docker compose run --rm slm2-test
    docker compose run --rm slm2-test --case 1
    docker compose run --rm slm2-test --all
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
# ?뚯뒪??耳?댁뒪 ?뺤쓽
# ============================================================================

TEST_CASES = [
    {
        "id": 1,
        "name": "紐낇솗???ъ떎 (TRUE ?덉긽)",
        "claim_text": "?쒖슱? ??쒕?援?쓽 ?섎룄?대떎.",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "?꾪궎諛깃낵 - ?쒖슱",
                "url": "https://ko.wikipedia.org/wiki/?쒖슱",
                "snippet": "?쒖슱?밸퀎?쒕뒗 ??쒕?援?쓽 ?섎룄?댁옄 理쒕? ?꾩떆?대떎. ?쒕컲??以묒븰遺???꾩튂?섎ŉ, ?멸뎄????950留?紐낆씠??",
                "source_type": "WIKIPEDIA",
            },
            {
                "evid_id": "ev_2",
                "title": "??쒕?援??뚮쾿",
                "url": "https://www.law.go.kr",
                "snippet": "??쒕?援?쓽 ?섎룄???쒖슱?밸퀎?쒕줈 ?쒕떎. ?대뒗 ?뚮쾿??愿?됱쑝濡??몄젙?섍퀬 ?덈떎.",
                "source_type": "KB_DOC",
            },
        ],
        "expected_stance": "TRUE",
    },
    {
        "id": 2,
        "name": "紐낇솗??嫄곗쭞 (FALSE ?덉긽)",
        "claim_text": "吏援щ뒗 ?됲룊?섎떎.",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "NASA 怨듭떇 諛쒗몴",
                "url": "https://www.nasa.gov",
                "snippet": "吏援щ뒗 援ы삎?대ŉ, ?쎄컙 ?⑹옉????먯껜 ?뺥깭瑜??좉퀬 ?덈떎. ?대뒗 ?섎쭖? ?곗＜ ?먯궗? 怨쇳븰??愿痢≪쑝濡??낆쬆?섏뿀??",
                "source_type": "KB_DOC",
            },
            {
                "evid_id": "ev_2",
                "title": "怨쇳븰 援먭낵??,
                "url": "https://example.com/science",
                "snippet": "吏援ъ쓽 ?섎젅????4留?km?대ŉ, 援ы삎 ?됱꽦?쇰줈???먯쟾怨?怨듭쟾???쒕떎.",
                "source_type": "WEB_URL",
            },
        ],
        "expected_stance": "FALSE",
    },
    {
        "id": 3,
        "name": "?쇳빀???뺣낫 (MIXED ?덉긽)",
        "claim_text": "而ㅽ뵾??嫄닿컯??醫뗫떎.",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "嫄닿컯 ?곌뎄 - 湲띿젙???④낵",
                "url": "https://health.example.com/1",
                "snippet": "?곷떦?됱쓽 而ㅽ뵾 ??랬???ъ옣 嫄닿컯???꾩????????덉쑝硫? ??궛??臾쇱쭏???띾??섎떎???곌뎄 寃곌낵媛 ?덈떎.",
                "source_type": "NEWS",
            },
            {
                "evid_id": "ev_2",
                "title": "嫄닿컯 ?곌뎄 - 遺?뺤쟻 ?④낵",
                "url": "https://health.example.com/2",
                "snippet": "怨쇰룄??移댄럹????랬??遺덉븞, 遺덈㈃利? ?щ컯??利앷? ?깆쓽 遺?묒슜???좊컻?????덈떎.",
                "source_type": "NEWS",
            },
        ],
        "expected_stance": "MIXED",
    },
    {
        "id": 4,
        "name": "利앷굅 遺議?(UNVERIFIED ?덉긽)",
        "claim_text": "?멸퀎 ?앸챸泥닿? 吏援щ? 諛⑸Ц???곸씠 ?덈떎.",
        "evidence_topk": [
            {
                "evid_id": "ev_1",
                "title": "UFO 紐⑷꺽??,
                "url": "https://ufo.example.com",
                "snippet": "?쇰? ?щ엺?ㅼ? 誘명솗??鍮꾪뻾臾쇱껜瑜?紐⑷꺽?덈떎怨?二쇱옣?섏?留? 怨쇳븰?곸쑝濡?寃利앸맂 利앷굅???녿떎.",
                "source_type": "WEB_URL",
            },
        ],
        "expected_stance": "UNVERIFIED",
    },
    {
        "id": 5,
        "name": "利앷굅 ?놁쓬 (UNVERIFIED 媛뺤젣)",
        "claim_text": "2050?꾩뿉 ?쒓뎅 ?멸뎄??3泥쒕쭔 紐낆씠 ??寃껋씠??",
        "evidence_topk": [],
        "expected_stance": "UNVERIFIED",
    },
]


# ============================================================================
# ?뚯씠?꾨씪???ㅽ뻾
# ============================================================================

def run_slm2_pipeline(
    claim_text: str,
    evidence_topk: list,
    language: str = "ko",
) -> dict:
    """
    Stage 6-7 + Stage 8 Aggregator ?뚯씠?꾨씪???ㅽ뻾.

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
    logger.info(f"[{trace_id}] Stage 6 ?ㅽ뻾 以?..")
    state = stage6_run(state)

    # Stage 7: Skeptic
    logger.info(f"[{trace_id}] Stage 7 ?ㅽ뻾 以?..")
    state = stage7_run(state)

    # Stage 8: Aggregate
    logger.info(f"[{trace_id}] Stage 8 ?ㅽ뻾 以?..")
    state = stage8_run(state)

    elapsed_ms = int((time.time() - start_time) * 1000)
    state["latency_ms"] = elapsed_ms

    return state


def print_result(case: dict, result: dict):
    """寃곌낵 異쒕젰."""
    print("\n" + "=" * 70)
    print(f"?뚯뒪??耳?댁뒪 #{case['id']}: {case['name']}")
    print("=" * 70)

    print(f"\n[二쇱옣] {case['claim_text']}")
    print(f"[利앷굅 ?? {len(case['evidence_topk'])}")
    print(f"[?덉긽 寃곌낵] {case['expected_stance']}")

    draft = result.get("draft_verdict", {})
    print(f"\n[?ㅼ젣 寃곌낵]")
    print(f"  - stance: {draft.get('stance')}")
    print(f"  - confidence: {draft.get('confidence', 0):.2f}")
    print(f"  - citations: {len(draft.get('citations', []))}媛?)
    print(f"  - quality_score: {result.get('quality_score', 0)}")
    print(f"  - latency: {result.get('latency_ms', 0)}ms")

    # ?곸꽭 ?뺣낫
    if draft.get("reasoning_bullets"):
        print(f"\n[異붾줎 洹쇨굅]")
        for bullet in draft["reasoning_bullets"][:5]:
            print(f"  ??{bullet}")

    if draft.get("citations"):
        print(f"\n[?몄슜]")
        for cit in draft["citations"][:3]:
            print(f"  ??[{cit.get('evid_id')}] {cit.get('quote', '')[:50]}...")

    # ?쇱튂 ?щ?
    match = draft.get("stance") == case["expected_stance"]
    status = "??PASS" if match else "??FAIL"
    print(f"\n[寃곌낵] {status}")

    return match


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="SLM2 ?뚯씠?꾨씪???곕え")
    parser.add_argument("--case", type=int, help="?뱀젙 ?뚯뒪??耳?댁뒪留??ㅽ뻾 (1-5)")
    parser.add_argument("--all", action="store_true", help="紐⑤뱺 ?뚯뒪??耳?댁뒪 ?ㅽ뻾")
    args = parser.parse_args()

    print("=" * 70)
    print("SLM2 ?뚯씠?꾨씪???곕え (Stage 6-7 + Stage 8 Aggregator)")
    print("=" * 70)

    # ?곌껐 ?뺤씤
    try:
        from app.stages._shared.slm_client import SLMConfig
        config = SLMConfig.from_env()
        print(f"\nSLM ?쒕쾭: {config.base_url}")
        print(f"紐⑤뜽: {config.model}")
        print(f"max_tokens: {config.max_tokens}")
    except Exception as e:
        logger.error(f"?ㅼ젙 濡쒕뱶 ?ㅽ뙣: {e}")
        sys.exit(1)

    # ?뚯뒪??耳?댁뒪 ?좏깮
    if args.case:
        cases = [c for c in TEST_CASES if c["id"] == args.case]
        if not cases:
            print(f"耳?댁뒪 #{args.case}瑜?李얠쓣 ???놁뒿?덈떎.")
            sys.exit(1)
    elif args.all:
        cases = TEST_CASES
    else:
        # 湲곕낯: 泥?踰덉㎏ 耳?댁뒪留?
        cases = TEST_CASES[:1]
        print("\n(湲곕낯: 耳?댁뒪 #1留??ㅽ뻾. --all ?듭뀡?쇰줈 ?꾩껜 ?ㅽ뻾)")

    # ?ㅽ뻾
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
            logger.exception(f"耳?댁뒪 #{case['id']} ?ㅽ뻾 ?ㅽ뙣: {e}")
            failed += 1

    # ?붿빟
    print("\n" + "=" * 70)
    print(f"寃곌낵 ?붿빟: {passed}/{passed + failed} ?듦낵")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

