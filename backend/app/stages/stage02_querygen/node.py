import json
import logging
import os
import re
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
YOUTUBE_QUERY_MAX_LEN = int(os.getenv("YOUTUBE_QUERY_MAX_LEN", "80"))


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
    claims: list[dict] | None = None,
) -> str:
    fetched_content = context.get("fetched_content", "")
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
        context_str = json.dumps(
            {k: v for k, v in context.items() if k != "fetched_content"},
            ensure_ascii=False,
        )
        return f"""Input User Text: "{claim}"
{claims_block}

Context Hints: {context_str}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. 기사 내용이 있다면 기사의 핵심 주장을 최우선으로 반영하세요. `text` 필드는 절대 비워두면 안 됩니다."""

    context_str = json.dumps(context, ensure_ascii=False, default=str)
    return f"""Input Text: "{claim}"
{claims_block}
Context Hints: {context_str}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. `text` 필드는 절대 비워두면 안 됩니다."""


def _has_valid_query_variants(parsed: Dict[str, Any]) -> bool:
    if not isinstance(parsed, dict):
        return False
    variants = parsed.get("query_variants")
    if not isinstance(variants, list) or not variants:
        return False
    for item in variants:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "") or "").strip()
        if text:
            return True
    return False


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
    system_prompt = load_system_prompt()

    user_prompt = build_querygen_user_prompt(claim, context, claims)

    response = call_slm1(system_prompt, user_prompt)
    parsed = parse_json_safe(response)

    if parsed is None or not _has_valid_query_variants(parsed):
        # 1회 재시도 (JSON or schema mismatch)
        logger.info("JSON/스키마 불일치, 재시도")
        retry_prompt = (
            "이전 응답이 유효한 JSON이 아니거나 스키마가 틀렸습니다. "
            "반드시 유효한 JSON만 출력하고, 아래 스키마를 지키세요. "
            "query_variants는 필수이며 최소 1개 이상이어야 합니다."
        )
        response = call_slm1(retry_prompt, user_prompt)
        parsed = parse_json_safe(response)

    if parsed is None or not _has_valid_query_variants(parsed):
        raise ValueError(f"JSON/스키마 최종 실패: {response[:200]}")

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
        
        # 2. Wiki 쿼리 검증 및 정제 (문제 2 해결)
        if qtype in ["wiki", "WIKI"]:
            # 2-1. 너무 긴 쿼리 (복합어 가능성) - 경고 및 첫 단어만 추출
            if len(text) > 15:
                logger.warning(f"Wiki query seems compound: '{text}' - using first term")
                # 첫 번째 명사만 추출 (공백 기준)
                first_term = text.split()[0] if text.split() else text
                text = first_term
            
            # 2-2. 서술형 감지 ("~의", "~에 대한", "~관련" 등)
            if re.search(r"(의|에\s*대한|관련|에\s*관한)", text):
                logger.warning(f"Wiki query is descriptive: '{text}' - cleaning")
                # 조사 및 서술어 제거
                text = re.sub(r"(의|에\s*대한|관련|에\s*관한).*", "", text).strip()
        
        # 3. Type normalization
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


def _normalize_keywords(bundle: Dict[str, Any], claim: str, max_terms: int = 3) -> List[str]:
    keywords: List[str] = []
    for item in (bundle.get("primary") or []) + (bundle.get("secondary") or []):
        if not isinstance(item, str):
            continue
        token = item.strip()
        if len(token) < 2:
            continue
        if token not in keywords:
            keywords.append(token)
        if len(keywords) >= max_terms:
            return keywords
    if not keywords:
        for token in (claim or "").split():
            token = token.strip()
            if len(token) < 2:
                continue
            if token not in keywords:
                keywords.append(token)
            if len(keywords) >= max_terms:
                break
    return keywords


def _rebuild_query_text(qtype: str, keywords: List[str], max_len: int, original: str, claim: str) -> str:
    base = " ".join(keywords) if keywords else (original or claim)
    if qtype == "news" and base and len(base) + 3 <= max_len:
        base = f"{base} 뉴스"
    elif qtype == "verification" and base and len(base) + 5 <= max_len:
        base = f"{base} 팩트체크"
    return base[:max_len].strip()


def postprocess_youtube_queries(result: Dict[str, Any], claim: str, max_len: int) -> Dict[str, Any]:
    """
    유튜브 소스일 때 쿼리 길이 조정 (타입별 차등 적용).
    - wiki: 짧게 유지 (표제어)
    - news/verification: Naver 검색을 위해 더 여유롭게 (120자)
    - 기타: 기본값 사용
    """
    variants = result.get("query_variants", []) or []
    keywords = _normalize_keywords(result.get("keyword_bundles", {}), claim)
    
    for q in variants:
        if not isinstance(q, dict):
            continue
        text = (q.get("text") or "").strip()
        qtype = (q.get("type") or "direct").strip().lower()
        
        # 타입별 최대 길이 설정
        if qtype == "wiki":
            type_max_len = 30  # 위키는 짧게 (표제어 중심)
        elif qtype in ["news", "verification"]:
            type_max_len = 120  # 뉴스/검증은 길게 (Naver 검색 품질 유지)
        else:
            type_max_len = max_len  # 기본값
        
        # 길이 초과 시 단순 자르기 (더 aggressive)
        if not text:
            q["text"] = _rebuild_query_text(qtype, keywords, type_max_len, "", claim)
        elif len(text) > type_max_len:
            # 단순히 자르기
            q["text"] = text[:type_max_len].strip()
            logger.info(f"[YouTube] Truncated {qtype} query from {len(text)} to {len(q['text'])} chars")
        # 그 외에는 원본 유지 (중요!)
    
    result["query_variants"] = variants
    return result


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
            )
            state["prompt_querygen_system"] = system_prompt
            parsed, slm_raw = generate_queries_with_llm(
                claim_text,
                context,
                state.get("normalize_claims"),
            )
            result = postprocess_queries(parsed, claim_text)
            state["slm_raw_querygen"] = slm_raw

        source_type = (context or {}).get("source_type", "")
        if source_type == "youtube":
            result = postprocess_youtube_queries(result, claim_text, YOUTUBE_QUERY_MAX_LEN)
            logger.info(f"[{trace_id}] Stage2 YouTube postprocess applied (max_len={YOUTUBE_QUERY_MAX_LEN})")

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
