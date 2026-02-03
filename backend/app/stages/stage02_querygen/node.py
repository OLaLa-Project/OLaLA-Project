"""
Stage 2 - Query Generation (LLM-Enhanced)

정규화된 주장으로부터 다각도 검색 쿼리를 생성합니다.
LLM 실패 시 규칙 기반(rule-based) fallback을 적용합니다.

Input state keys:
    - trace_id: str
    - claim_text: str (Stage 1에서 정규화된 주장)
    - language: "ko" | "en"
    - canonical_evidence: dict (Stage 1 메타데이터)
    - entity_map: dict (Stage 1 엔티티)

Output state keys:
    - query_variants: list[dict] (type, text)
    - keyword_bundles: dict (primary, secondary)
    - search_constraints: dict
"""

import json
import logging
from pathlib import Path
from functools import lru_cache
from typing import Dict, Any, List

from app.stages._shared.slm_client import call_slm1, SLMError
from app.stages._shared.guardrails import parse_json_safe

logger = logging.getLogger(__name__)

# 프롬프트 파일 경로
PROMPT_FILE = Path(__file__).parent / "prompt_querygen.txt"

# 설정
MAX_CONTENT_LENGTH = 1500
DEFAULT_LANGUAGE = "ko"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """시스템 프롬프트 로드 (캐싱)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# LLM 기반 쿼리 생성
# ---------------------------------------------------------------------------

def build_querygen_user_prompt(
    claim: str,
    context: Dict[str, Any],
) -> str:
    fetched_content = context.get("fetched_content", "")
    has_article = bool(fetched_content)

    if has_article:
        truncated = fetched_content[:MAX_CONTENT_LENGTH]
        context_str = json.dumps(
            {k: v for k, v in context.items() if k != "fetched_content"},
            ensure_ascii=False,
        )
        return f"""Input User Text: "{claim}"
[첨부된 기사 내용 시작]
{truncated}
[첨부된 기사 내용 끝]

Context Hints: {context_str}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. 기사 내용이 있다면 기사의 핵심 주장을 최우선으로 반영하세요. `text` 필드는 절대 비워두면 안 됩니다."""

    context_str = json.dumps(context, ensure_ascii=False, default=str)
    return f"""Input Text: "{claim}"
Context Hints: {context_str}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. `text` 필드는 절대 비워두면 안 됩니다."""


def generate_queries_with_llm(
    claim: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    SLM을 사용해 검증용 쿼리를 생성합니다.

    Returns:
        core_fact, query_variants, keyword_bundles, search_constraints를 포함하는 dict.

    Raises:
        SLMError, ValueError: LLM 호출 또는 파싱 실패 시
    """
    system_prompt = load_system_prompt()

    user_prompt = build_querygen_user_prompt(claim, context)

    response = call_slm1(system_prompt, user_prompt)
    parsed = parse_json_safe(response)

    if parsed is None:
        # 1회 재시도
        logger.info("JSON 파싱 실패, 재시도")
        retry_prompt = (
            "이전 응답이 유효한 JSON이 아닙니다. "
            "반드시 유효한 JSON만 출력하세요. 다른 설명 없이 JSON만 출력하세요."
        )
        response = call_slm1(retry_prompt, user_prompt)
        parsed = parse_json_safe(response)

    if parsed is None:
        raise ValueError(f"JSON 파싱 최종 실패: {response[:200]}")

    return parsed


def _render_prompt_template(template: str, state: Dict[str, Any]) -> str:
    evidence = state.get("canonical_evidence", {}) or {}
    user_request = state.get("user_request", "")
    title = evidence.get("article_title", "") or ""
    article_text = evidence.get("fetched_content", "") or evidence.get("snippet", "") or ""
    rendered = template
    rendered = rendered.replace("{{user_request}}", user_request)
    rendered = rendered.replace("{{title}}", title)
    rendered = rendered.replace("{{article_text}}", article_text)
    return rendered


def generate_queries_with_prompt_override(
    state: Dict[str, Any],
    template: str,
) -> Dict[str, Any]:
    prompt = _render_prompt_template(template, state)
    response = call_slm1("", prompt)
    parsed = parse_json_safe(response)
    if parsed is None:
        retry_prompt = (
            "이전 응답이 유효한 JSON이 아닙니다. 반드시 유효한 JSON만 출력하세요. "
            "다른 설명 없이 JSON만 출력하세요."
        )
        response = call_slm1(retry_prompt, prompt)
        parsed = parse_json_safe(response)
    if parsed is None:
        raise ValueError(f"JSON 파싱 최종 실패: {response[:200]}")
    parsed["_prompt_used"] = prompt
    return parsed


from app.gateway.schemas.common import SearchQuery, SearchQueryType

def _query_variants_from_team_a(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    claims = parsed.get("claims") or parsed.get("주장들") or []
    variants: List[Dict[str, Any]] = []
    
    # Legacy parser support if needed, but primary focus is extracting robust types
    for claim in claims:
        # Simplified for brevity as we are likely using the simpler format in updated prompt
        pass
        
    return variants

def _ensure_search_query_dict(q: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure dict conforms to SearchQuery structure."""
    text = q.get("text", "")
    qtype = q.get("type", "direct")
    
    # Normalize type string to Enum value if possible
    try:
        qtype_enum = SearchQueryType(qtype)
    except ValueError:
        # Fallback mapping
        if qtype == "contradictory":
            qtype_enum = SearchQueryType.VERIFICATION
        elif qtype == "direct":
            qtype_enum = SearchQueryType.DIRECT
        else:
            qtype_enum = SearchQueryType.DIRECT
            
    return {"text": text, "type": qtype_enum.value}



def postprocess_queries(
    parsed: Dict[str, Any],
    claim: str,
) -> Dict[str, Any]:
    """
    LLM 출력 후처리: 빈 text 필드 보완, 기본 구조 보장.
    """
    core_fact = parsed.get("core_fact") or claim

    # query_variants 보완
    raw_variants = parsed.get("query_variants", [])
    valid_variants = []
    
    for q in raw_variants:
        text = q.get("text", "").strip()
        qtype = q.get("type", "direct")
        
        # 1. Text fallback
        if not text:
            if qtype == "wiki":
                text = core_fact
            elif qtype == "news":
                text = f"{core_fact} 뉴스"
            elif qtype == "verification":
                text = f"{core_fact} 팩트체크"
            else:
                text = core_fact
        
        # 2. Type normalization
        # Map known types to SearchQueryType values
        if qtype in ["wiki", "WIKI"]:
            final_type = "wiki"
        elif qtype in ["news", "NEWS"]:
            final_type = "news"
        elif qtype in ["verification", "contradictory"]:
            final_type = "verification"
        else:
            final_type = "direct" # default
            
        valid_variants.append({"text": text, "type": final_type})

    # 최소 1개 쿼리 보장
    if not valid_variants:
        valid_variants = [{"type": "direct", "text": core_fact}]

    return {
        "query_variants": valid_variants,
        "keyword_bundles": parsed.get("keyword_bundles", {"primary": [], "secondary": []}),
        "search_constraints": parsed.get("search_constraints", {}),
    }


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

def generate_rule_based_fallback(claim: str) -> Dict[str, Any]:
    """LLM 실패 시 규칙 기반 쿼리 생성."""
    words = claim.split()
    keywords = [w for w in words if len(w) > 1]

    variants = [
        {"type": "direct", "text": claim},
        {"type": "verification", "text": f"{claim} 팩트체크"},
        {"type": "news", "text": f"{claim} 뉴스"},
    ]

    return {
        "query_variants": variants,
        "keyword_bundles": {
            "primary": keywords[:3],
            "secondary": keywords[3:6],
        },
        "search_constraints": {"note": "rule-based fallback"},
    }


# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------

def run(state: dict) -> dict:
    """
    Stage 2 실행: 검색 쿼리 생성.

    Stage 1의 출력(claim_text, canonical_evidence, entity_map)을 기반으로
    다각도 검색 쿼리를 생성합니다.
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    context = state.get("canonical_evidence", {})

    logger.info(f"[{trace_id}] Stage2 시작: claim={claim_text[:50]}...")

    if not claim_text:
        logger.warning(f"[{trace_id}] claim_text 비어있음, fallback 적용")
        result = generate_rule_based_fallback("")
        state["query_variants"] = result["query_variants"]
        state["keyword_bundles"] = result["keyword_bundles"]
        state["search_constraints"] = result["search_constraints"]
        return state

    try:
        # LLM 기반 쿼리 생성 (override prompt 지원)
        prompt_override = state.get("querygen_prompt") or ""
        if prompt_override.strip():
            parsed = generate_queries_with_prompt_override(state, prompt_override)
            variants = _query_variants_from_team_a(parsed)
            if variants:
                result = {
                    "query_variants": variants,
                    "keyword_bundles": parsed.get("keyword_bundles", {"primary": [], "secondary": []}),
                    "search_constraints": parsed.get("search_constraints", {}),
                }
                state["querygen_claims"] = parsed.get("claims") or parsed.get("주장들") or []
                state["querygen_prompt_used"] = parsed.get("_prompt_used")
            else:
                result = postprocess_queries(parsed, claim_text)
            state["prompt_querygen_user"] = parsed.get("_prompt_used")
        else:
            state["prompt_querygen_user"] = build_querygen_user_prompt(claim_text, context)
            parsed = generate_queries_with_llm(claim_text, context)
            result = postprocess_queries(parsed, claim_text)

        logger.info(
            f"[{trace_id}] Stage2 LLM 완료: "
            f"{len(result['query_variants'])} queries generated"
        )

    except (SLMError, ValueError) as e:
        logger.warning(f"[{trace_id}] LLM 쿼리 생성 실패, fallback 적용: {e}")
        result = generate_rule_based_fallback(claim_text)

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage2 예상치 못한 오류: {e}")
        result = generate_rule_based_fallback(claim_text)

    # State 업데이트
    state["query_variants"] = result["query_variants"]
    state["keyword_bundles"] = result["keyword_bundles"]
    state["search_constraints"] = result["search_constraints"]

    if result.get("query_variants"):
        logger.info(f"[{trace_id}] Stage2 완료: top_query={result['query_variants'][0]['text']}")
    else:
        logger.info(f"[{trace_id}] Stage2 완료: no queries generated")

    return state
