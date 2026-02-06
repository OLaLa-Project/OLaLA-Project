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
# 프롬프트 파일 경로
PROMPT_FILE = Path(__file__).parent / "prompt_querygen.txt"
PROMPT_FILE_YOUTUBE = Path(__file__).parent / "prompt_querygen_youtube.txt"

# 설정
MAX_CONTENT_LENGTH = 1500
DEFAULT_LANGUAGE = "ko"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """시스템 프롬프트 로드 (캐싱)."""
    return PROMPT_FILE.read_text(encoding="utf-8")

@lru_cache(maxsize=1)
def load_youtube_prompt() -> str:
    """유튜브 전용 시스템 프롬프트 로드 (캐싱)."""
    return PROMPT_FILE_YOUTUBE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# LLM 기반 쿼리 생성
# ---------------------------------------------------------------------------

def build_querygen_user_prompt(
    claim: str,
    context: Dict[str, Any],
    claims: list[dict] | None = None,
    is_youtube: bool = False,
) -> str:
    fetched_content = context.get("fetched_content", "") or context.get("transcript", "")
    
    if is_youtube and fetched_content:
        # 유튜브 전용 프롬프트 포맷
        return f"""[YouTube Script]
{fetched_content}

[핵심 주장 (Claim)]
{claim}

위 내용을 바탕으로 JSON 포맷의 출력을 생성하세요."""

    has_article = bool(fetched_content)

    claims_block = ""
    if claims:
        lines = []
        for item in claims:
            text = item.get("주장") or item.get("claim") or ""
            if text:
                lines.append(f"- {text}")
        if lines:
            claims_block = "\n[핵심 주장 후보]\n" + "\n".join(lines)

    if has_article:
        # fetched_content를 제외한 나머지 메타데이터만 JSON으로 변환
        context_str = json.dumps(
            {k: v for k, v in context.items() if k != "fetched_content"},
            ensure_ascii=False,
        )
        # 중요: 기사 본문(fetched_content)을 프롬프트에 포함시킴
        return f"""Input User Text: "{claim}"
{claims_block}

Context Hints: {context_str}

[Provided Content]
{fetched_content}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. 기사 내용(Provided Content)이 있다면 그 내용을 최우선으로 반영하여 검색어를 생성하세요. `text` 필드는 절대 비워두면 안 됩니다."""

    context_str = json.dumps(context, ensure_ascii=False, default=str)
    return f"""Input Text: "{claim}"
{claims_block}
Context Hints: {context_str}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. `text` 필드는 절대 비워두면 안 됩니다."""


def generate_queries_with_llm(
    claim: str,
    context: Dict[str, Any],
    claims: list[dict] | None = None,
) -> tuple[Dict[str, Any], str]:
    """
    SLM을 사용해 검증용 쿼리를 생성합니다.

    Returns:
        core_fact, query_variants, keyword_bundles, search_constraints를 포함하는 dict.

    Raises:
        SLMError, ValueError: LLM 호출 또는 파싱 실패 시
    """
    # 유튜브 여부 확인 (Stage 1에서 transcript가 있으면 유튜브로 간주)
    is_youtube = bool(context.get("transcript"))

    if is_youtube:
        system_prompt = load_youtube_prompt()
    else:
        system_prompt = load_system_prompt()

    user_prompt = build_querygen_user_prompt(claim, context, claims, is_youtube=is_youtube)

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

    return parsed, response


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
) -> tuple[Dict[str, Any], str]:
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
    return parsed, response


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
    print("DEBUG: Stage 2 node.run called!")
    """
    Stage 2 실행: 검색 쿼리 생성.

    Stage 1의 출력(claim_text, canonical_evidence, entity_map)을 기반으로
    다각도 검색 쿼리를 생성합니다.
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    context = state.get("canonical_evidence", {})
    logger.info(f"[{trace_id}] Stage2 Debug: keys in state: {list(state.keys())}")
    logger.info(f"[{trace_id}] Stage2 Debug: transcript in state? {'transcript' in state}")
    print(f"DEBUG: Stage 2 context keys: {list(context.keys())}")
    if 'transcript' in state:
         logger.info(f"[{trace_id}] Stage2 Debug: transcript len: {len(state['transcript'])}")

    # Stage 1에서 transcript를 root state에 저장하므로, Stage 2 context에 주입
    if state.get("transcript"):
        context["transcript"] = state.get("transcript")
        
    # Robust Detection for YouTube
    domain = context.get("domain", "") or ""
    source_url = context.get("source_url", "") or ""
    is_youtube_url = "youtube.com" in domain or "youtu.be" in domain or "youtube.com" in source_url or "youtu.be" in source_url
    
    # Check content
    has_transcript = bool(context.get("transcript"))
    has_content = bool(context.get("transcript") or context.get("fetched_content"))
    
    # Determine is_youtube: URL match + Content available
    is_youtube = (is_youtube_url and has_content) or has_transcript
    
    # Force context['transcript'] if it's youtube but missing key
    if is_youtube and not context.get("transcript") and context.get("fetched_content"):
        context["transcript"] = context.get("fetched_content")

    print(f"DEBUG: Stage 2 is_youtube: {is_youtube} (URL: {is_youtube_url}, HasTranscript: {has_transcript})")
    logger.info(f"[{trace_id}] Stage2 Debug: is_youtube determined as: {is_youtube}")

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
        system_prompt = load_system_prompt()
        if prompt_override.strip():
            parsed, slm_raw = generate_queries_with_prompt_override(state, prompt_override)
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
            state["prompt_querygen_system"] = ""
            state["slm_raw_querygen"] = slm_raw
        else:
            state["prompt_querygen_user"] = build_querygen_user_prompt(
                claim_text,
                context,
                state.get("normalize_claims"),
                is_youtube=is_youtube,
            )
            state["prompt_querygen_system"] = system_prompt
            parsed, slm_raw = generate_queries_with_llm(
                claim_text,
                context,
                state.get("normalize_claims"),
            )
            result = postprocess_queries(parsed, claim_text)
            state["slm_raw_querygen"] = slm_raw

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
    state["query_variants"] = result.get("query_variants") or []
    state["keyword_bundles"] = result.get("keyword_bundles") or {"primary": [], "secondary": []}
    state["search_constraints"] = result.get("search_constraints") or {}
    
    print(f"DEBUG: Stage 2 returning state. query_variants len: {len(state['query_variants'])}")

    if result.get("query_variants"):
        logger.info(f"[{trace_id}] Stage2 완료: top_query={result['query_variants'][0]['text']}")
    else:
        logger.info(f"[{trace_id}] Stage2 완료: no queries generated")

    return state
