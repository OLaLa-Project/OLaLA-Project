import json
import logging
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple

from app.core.settings import settings
from app.stages._shared.guardrails import parse_json_safe
from app.stages._shared.slm_client import SLMError, call_slm1

logger = logging.getLogger(__name__)

# 프롬프트 파일 경로
PROMPT_FILE = Path(__file__).parent / "prompt_querygen.txt"

# 설정
MAX_CONTENT_LENGTH = 1500
DEFAULT_LANGUAGE = "ko"
YOUTUBE_QUERY_MAX_LEN = settings.youtube_query_max_len
_ALLOWED_QUERY_TYPES = {"wiki", "news", "web", "verification", "direct"}
_ALLOWED_INTENTS = {
    "direct",
    "entity_profile",
    "news_followup",
    "official_statement",
    "fact_check",
    "origin_trace",
    "verification",
}
_ALLOWED_STANCES = {"support", "skeptic", "neutral"}
_RUMOR_MODES = {"rumor", "mixed"}


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """시스템 프롬프트 로드 (캐싱)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


def _truncate_for_prompt(text: str, max_len: int = MAX_CONTENT_LENGTH) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


def _extract_claim_ref(item: dict, fallback_index: int) -> Tuple[str, str]:
    claim_id = str(item.get("claim_id") or f"C{fallback_index}").strip() or f"C{fallback_index}"
    claim_text = str(item.get("주장") or item.get("claim") or item.get("text") or "").strip()
    return claim_id, claim_text


def _normalize_claim_mode(value: Any) -> Literal["fact", "rumor", "mixed"]:
    mode = str(value or "fact").strip().lower()
    if mode in {"fact", "rumor", "mixed"}:
        return mode  # type: ignore[return-value]
    if "rumor" in mode and "fact" in mode:
        return "mixed"
    if "rumor" in mode:
        return "rumor"
    return "fact"


def _normalize_query_type(value: Any) -> str:
    qtype = str(value or "direct").strip().lower()
    if qtype == "contradictory":
        return "verification"
    if qtype in _ALLOWED_QUERY_TYPES:
        return qtype
    return "direct"


def _normalize_stance(value: Any) -> str:
    stance = str(value or "").strip().lower()
    if stance in _ALLOWED_STANCES:
        return stance
    return "neutral"


def _normalize_intent(value: Any, qtype: str, mode: str) -> str:
    intent = str(value or "").strip().lower()
    if intent in _ALLOWED_INTENTS:
        return intent
    if qtype == "wiki":
        return "entity_profile"
    if qtype == "verification":
        return "fact_check" if mode in _RUMOR_MODES else "verification"
    if qtype == "news":
        return "official_statement" if mode in _RUMOR_MODES else "news_followup"
    if qtype == "web" and mode in _RUMOR_MODES:
        return "origin_trace"
    return "direct"


def _copy_meta(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _standardize_variant(
    qtype: str,
    text: str,
    meta: Dict[str, Any],
    *,
    fallback_claim_id: str,
    claim_mode: str,
) -> Dict[str, Any]:
    normalized_meta = _copy_meta(meta)
    claim_id = str(normalized_meta.get("claim_id") or fallback_claim_id or "").strip()
    normalized_meta["claim_id"] = claim_id
    normalized_meta["mode"] = _normalize_claim_mode(normalized_meta.get("mode") or claim_mode)
    normalized_meta["intent"] = _normalize_intent(
        normalized_meta.get("intent"),
        qtype,
        normalized_meta["mode"],
    )
    normalized_meta["stance"] = _normalize_stance(normalized_meta.get("stance"))

    variant: Dict[str, Any] = {
        "type": _normalize_query_type(qtype),
        "text": str(text or "").strip(),
        "meta": normalized_meta,
    }
    return variant


def _primary_claim_id(normalized_claims: Any) -> str:
    if not isinstance(normalized_claims, list):
        return ""
    for idx, item in enumerate(normalized_claims, start=1):
        if not isinstance(item, dict):
            continue
        claim_id, claim_text = _extract_claim_ref(item, idx)
        if claim_text:
            return claim_id
    return ""


def _claim_id_set(normalized_claims: Any) -> set[str]:
    claim_ids: set[str] = set()
    if not isinstance(normalized_claims, list):
        return claim_ids
    for idx, item in enumerate(normalized_claims, start=1):
        if not isinstance(item, dict):
            continue
        claim_id, claim_text = _extract_claim_ref(item, idx)
        if claim_text and claim_id:
            claim_ids.add(claim_id)
    return claim_ids


def _sanitize_claim_refs(
    variants: List[Dict[str, Any]],
    normalized_claims: Any,
    fallback_claim_id: str,
    claim_mode: str,
) -> List[Dict[str, Any]]:
    allowed_claim_ids = _claim_id_set(normalized_claims)
    id_map: Dict[str, str] = {}
    if allowed_claim_ids:
        fallback = fallback_claim_id if fallback_claim_id in allowed_claim_ids else sorted(allowed_claim_ids)[0]
        for claim_id in sorted(allowed_claim_ids):
            id_map[claim_id] = claim_id
    else:
        fallback = "C1"
        id_map = {"C1": "C1", "C2": "C2"}
    sanitized: List[Dict[str, Any]] = []

    for variant in variants:
        if not isinstance(variant, dict):
            continue
        meta = _copy_meta(variant.get("meta"))
        claim_id = str(meta.get("claim_id") or "").strip()
        if claim_id:
            if claim_id in id_map:
                canonical_id = id_map[claim_id]
            else:
                canonical_id = "C2" if ("C1" in id_map and len(id_map) >= 2) else fallback
                id_map[claim_id] = canonical_id
            if canonical_id != claim_id:
                meta["claim_id_sanitized"] = True
            meta["claim_id"] = canonical_id
        else:
            meta["claim_id"] = fallback
            meta["claim_id_sanitized"] = True
        standardized = _standardize_variant(
            _normalize_query_type(variant.get("type", "direct")),
            str(variant.get("text", "") or "").strip(),
            meta,
            fallback_claim_id=str(meta.get("claim_id") or fallback),
            claim_mode=claim_mode,
        )
        sanitized.append(standardized)

    return sanitized


def _normalize_for_semantic_key(text: str) -> str:
    compact = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", compact)


def _semantic_similar(left: str, right: str) -> bool:
    left_norm = _normalize_for_semantic_key(left)
    right_norm = _normalize_for_semantic_key(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    return SequenceMatcher(None, left_norm, right_norm).ratio() >= 0.92


def _dedupe_query_variants(variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for variant in variants:
        if not isinstance(variant, dict):
            continue
        qtype = _normalize_query_type(variant.get("type", "direct"))
        text = str(variant.get("text", "") or "").strip()
        if not text:
            continue
        meta = _copy_meta(variant.get("meta"))
        claim_id = str(meta.get("claim_id") or "").strip()
        intent = str(meta.get("intent") or "").strip().lower()
        stance = _normalize_stance(meta.get("stance"))
        normalized_key = _normalize_for_semantic_key(text)
        key = (qtype, normalized_key, claim_id, f"{intent}:{stance}")
        if key in seen_keys:
            continue

        is_semantic_duplicate = False
        for existing in deduped:
            existing_type = _normalize_query_type(existing.get("type", "direct"))
            if existing_type != qtype:
                continue
            existing_meta = _copy_meta(existing.get("meta"))
            if str(existing_meta.get("intent") or "").strip().lower() != intent:
                continue
            if _normalize_stance(existing_meta.get("stance")) != stance:
                continue
            existing_claim = str(existing_meta.get("claim_id") or "").strip()
            if existing_claim and claim_id and existing_claim != claim_id:
                continue
            if _semantic_similar(str(existing.get("text", "")), text):
                is_semantic_duplicate = True
                break

        if is_semantic_duplicate:
            continue

        seen_keys.add(key)
        deduped.append(variant)

    return deduped


# ---------------------------------------------------------------------------
# LLM 기반 쿼리 생성
# ---------------------------------------------------------------------------

def build_querygen_user_prompt(
    claim: str,
    context: Dict[str, Any],
    claims: list[dict] | None = None,
    *,
    claim_mode: str = "fact",
    risk_markers: list[str] | None = None,
    verification_priority: str = "normal",
) -> str:
    fetched_content = context.get("fetched_content", "")
    has_article = bool(fetched_content)

    claims_block = ""
    if claims:
        lines = []
        for idx, item in enumerate(claims, start=1):
            if not isinstance(item, dict):
                continue
            claim_id, text = _extract_claim_ref(item, idx)
            if text:
                lines.append(f"- ({claim_id}) {text}")
        if lines:
            claims_block = "\n[핵심 주장 후보]\n" + "\n".join(lines)

    profile = {
        "claim_mode": _normalize_claim_mode(claim_mode),
        "risk_markers": [token for token in (risk_markers or []) if isinstance(token, str) and token.strip()],
        "verification_priority": str(verification_priority or "normal").strip().lower() or "normal",
    }
    profile_block = f"\n[CLAIM_PROFILE]\n{json.dumps(profile, ensure_ascii=False)}"

    if has_article:
        context_str = json.dumps(
            {k: v for k, v in context.items() if k != "fetched_content"},
            ensure_ascii=False,
        )
        article_excerpt = _truncate_for_prompt(str(fetched_content))
        return f"""Input User Text: "{claim}"
{claims_block}{profile_block}

Context Hints: {context_str}
[ARTICLE_TEXT]
{article_excerpt}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. 기사 내용이 있다면 기사의 핵심 주장을 최우선으로 반영하세요. `text` 필드는 절대 비워두면 안 됩니다."""

    context_str = json.dumps(context, ensure_ascii=False, default=str)
    return f"""Input Text: "{claim}"
{claims_block}{profile_block}
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
    *,
    claim_mode: str = "fact",
    risk_markers: list[str] | None = None,
    verification_priority: str = "normal",
) -> tuple[Dict[str, Any], str]:
    """
    SLM을 사용해 검증용 쿼리를 생성합니다.

    Returns:
        core_fact, query_variants, keyword_bundles, search_constraints를 포함하는 dict.

    Raises:
        SLMError, ValueError: LLM 호출 또는 파싱 실패 시
    """
    system_prompt = load_system_prompt()

    user_prompt = build_querygen_user_prompt(
        claim,
        context,
        claims,
        claim_mode=claim_mode,
        risk_markers=risk_markers,
        verification_priority=verification_priority,
    )

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
    evidence = state.get("canonical_evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    
    user_request = state.get("user_request", "")
    title = evidence.get("article_title", "") or ""
    article_text = evidence.get("fetched_content", "") or evidence.get("snippet", "") or ""
    rendered = template
    rendered = rendered.replace("{{user_request}}", user_request)
    rendered = rendered.replace("{{title}}", title)
    rendered = rendered.replace("{{article_text}}", article_text)
    rendered = rendered.replace("{{claim_mode}}", str(state.get("claim_mode") or "fact"))
    rendered = rendered.replace(
        "{{risk_markers}}",
        json.dumps(state.get("risk_markers") or [], ensure_ascii=False),
    )
    rendered = rendered.replace(
        "{{verification_priority}}",
        str(state.get("verification_priority") or "normal"),
    )
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


def _query_variants_from_team_a(
    parsed: Dict[str, Any],
    claim_mode: str = "fact",
) -> List[Dict[str, Any]]:
    claims = parsed.get("claims") or parsed.get("주장들") or []
    variants: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    if not isinstance(claims, list):
        return variants

    normalized_mode = _normalize_claim_mode(claim_mode)
    for idx, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            continue
        claim_id, claim_text = _extract_claim_ref(claim, idx)
        if not claim_text:
            continue

        query_candidates = [
            (
                "wiki",
                claim.get("wiki_db") or claim.get("wiki_query") or claim.get("wiki"),
                "entity_profile",
            ),
            (
                "news",
                claim.get("news_search") or claim.get("news_query") or claim.get("news"),
                "official_statement" if normalized_mode in _RUMOR_MODES else "news_followup",
            ),
            (
                "verification",
                claim.get("verification_query")
                or claim.get("fact_check_query")
                or claim.get("contradictory_query"),
                "fact_check" if normalized_mode in _RUMOR_MODES else "verification",
            ),
            ("direct", claim_text, "direct"),
        ]

        for qtype, raw_text, intent in query_candidates:
            text = str(raw_text or "").strip()
            if not text:
                continue
            final_type = _normalize_query_type(qtype)
            key = (final_type, text, claim_id, intent)
            if key in seen:
                continue
            seen.add(key)
            variants.append(
                _standardize_variant(
                    final_type,
                    text,
                    {
                        "claim_id": claim_id,
                        "source": "querygen_claims",
                        "intent": intent,
                        "mode": normalized_mode,
                    },
                    fallback_claim_id=claim_id,
                    claim_mode=normalized_mode,
                )
            )

    return variants


def postprocess_queries(
    parsed: Dict[str, Any],
    claim: str,
    *,
    claim_mode: str = "fact",
) -> Dict[str, Any]:
    """
    LLM 출력 후처리: 빈 text 필드 보완, 기본 구조 보장.
    """
    core_fact = str(parsed.get("core_fact") or claim).strip() or claim

    # query_variants 보완
    raw_variants = parsed.get("query_variants", [])
    valid_variants: List[Dict[str, Any]] = []

    for idx, q in enumerate(raw_variants, start=1):
        if not isinstance(q, dict):
            continue
        text = str(q.get("text", "") or "").strip()
        qtype = _normalize_query_type(q.get("type", "direct"))
        meta = _copy_meta(q.get("meta"))

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

        # 2. Wiki 쿼리 검증 (벡터 검색을 위해 문장형 허용, 불필요한 특수문자만 제거)
        if qtype == "wiki":
            text = re.sub(r"\s+", " ", text).strip()
            # 특수문자 제거는 유지하되, 조사/어미 제거 로직은 삭제하여 문장형 보존
            text = re.sub(r"^[\"'“”‘’\[\](){}]+|[\"'“”‘’\[\](){}]+$", "", text).strip()
            # cleaned = re.sub(r"\s+(의|에\s*대한|관련|에\s*관한)\s+.*$", "", text).strip() -> 삭제

        variant = _standardize_variant(
            qtype,
            text,
            meta,
            fallback_claim_id=str(meta.get("claim_id") or f"C{idx}"),
            claim_mode=claim_mode,
        )
        valid_variants.append(variant)

    # 최소 1개 쿼리 보장
    if not valid_variants:
        valid_variants = [
            _standardize_variant(
                "direct",
                core_fact,
                {"intent": "direct", "mode": claim_mode},
                fallback_claim_id="",
                claim_mode=claim_mode,
            )
        ]

    return {
        "core_fact": core_fact,
        "query_variants": valid_variants,
        "keyword_bundles": parsed.get("keyword_bundles", {"primary": [], "secondary": []}),
        "search_constraints": parsed.get("search_constraints", {}),
    }


def _augment_with_normalized_claims(
    variants: List[Dict[str, Any]],
    normalized_claims: Any,
    claim_mode: str = "fact",
) -> List[Dict[str, Any]]:
    if not isinstance(normalized_claims, list):
        return variants

    merged: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for idx, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict):
            continue
        standardized = _standardize_variant(
            _normalize_query_type(variant.get("type", "direct")),
            str(variant.get("text", "") or "").strip(),
            _copy_meta(variant.get("meta")),
            fallback_claim_id=f"C{idx}",
            claim_mode=claim_mode,
        )
        qtype = standardized["type"]
        text = standardized["text"]
        meta = standardized.get("meta") if isinstance(standardized.get("meta"), dict) else {}
        claim_id = str(meta.get("claim_id") or "")
        intent = str(meta.get("intent") or "")
        stance = _normalize_stance(meta.get("stance"))
        key = (qtype, text, claim_id, f"{intent}:{stance}")
        if not text or key in seen:
            continue
        seen.add(key)
        merged.append(standardized)

    for idx, item in enumerate(normalized_claims, start=1):
        if not isinstance(item, dict):
            continue
        claim_id, claim_text = _extract_claim_ref(item, idx)
        if not claim_text:
            continue

        candidates = [
            ("direct", claim_text, "direct"),
            ("verification", f"{claim_text} 사실 확인", "fact_check"),
        ]
        for qtype, text, intent in candidates:
            standardized = _standardize_variant(
                qtype,
                text,
                {
                    "claim_id": claim_id,
                    "source": "normalize_claims",
                    "intent": intent,
                    "mode": claim_mode,
                },
                fallback_claim_id=claim_id,
                claim_mode=claim_mode,
            )
            final_type = standardized["type"]
            final_text = standardized["text"]
            meta = standardized.get("meta") if isinstance(standardized.get("meta"), dict) else {}
            final_claim_id = str(meta.get("claim_id") or "")
            final_intent = str(meta.get("intent") or "")
            final_stance = _normalize_stance(meta.get("stance"))
            key = (final_type, final_text, final_claim_id, f"{final_intent}:{final_stance}")
            if key in seen:
                continue
            seen.add(key)
            merged.append(standardized)

    return merged


def _ensure_rumor_intents(
    variants: List[Dict[str, Any]],
    core_fact: str,
    claim_mode: str,
    normalized_claims: Any,
) -> List[Dict[str, Any]]:
    mode = _normalize_claim_mode(claim_mode)
    if mode not in _RUMOR_MODES:
        return variants

    merged = list(variants)
    seen_intents: set[str] = set()
    seen_keys: set[tuple[str, str, str, str]] = set()

    for variant in merged:
        if not isinstance(variant, dict):
            continue
        qtype = _normalize_query_type(variant.get("type", "direct"))
        text = str(variant.get("text", "") or "").strip()
        meta = variant.get("meta") if isinstance(variant.get("meta"), dict) else {}
        claim_id = str(meta.get("claim_id") or "")
        intent = _normalize_intent(meta.get("intent"), qtype, mode)
        stance = _normalize_stance(meta.get("stance"))
        seen_intents.add(intent)
        seen_keys.add((qtype, text, claim_id, f"{intent}:{stance}"))

    primary_claim_id = _primary_claim_id(normalized_claims)
    base_text = core_fact.strip()
    if not base_text and isinstance(normalized_claims, list):
        for idx, item in enumerate(normalized_claims, start=1):
            if not isinstance(item, dict):
                continue
            _, claim_text = _extract_claim_ref(item, idx)
            if claim_text:
                base_text = claim_text
                break
    if not base_text:
        base_text = "핵심 주장"

    required = [
        ("news", "official_statement", f"{base_text} 공식입장 해명"),
        ("verification", "fact_check", f"{base_text} 팩트체크 사실확인"),
        ("web", "origin_trace", f"{base_text} 최초 유포 원출처"),
    ]

    for qtype, intent, text in required:
        if intent in seen_intents:
            continue
        standardized = _standardize_variant(
            qtype,
            text,
            {
                "claim_id": primary_claim_id,
                "source": "rumor_guardrail",
                "intent": intent,
                "mode": mode,
            },
            fallback_claim_id=primary_claim_id,
            claim_mode=mode,
        )
        final_qtype = standardized["type"]
        final_text = standardized["text"]
        meta = standardized.get("meta") if isinstance(standardized.get("meta"), dict) else {}
        final_claim_id = str(meta.get("claim_id") or "")
        final_intent = str(meta.get("intent") or "")
        final_stance = _normalize_stance(meta.get("stance"))
        key = (final_qtype, final_text, final_claim_id, f"{final_intent}:{final_stance}")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        seen_intents.add(final_intent)
        merged.append(standardized)

    return merged


def _claim_text_map(normalized_claims: Any, core_fact: str) -> Dict[str, str]:
    claim_texts: Dict[str, str] = {}
    if isinstance(normalized_claims, list):
        for idx, item in enumerate(normalized_claims, start=1):
            if not isinstance(item, dict):
                continue
            claim_id, claim_text = _extract_claim_ref(item, idx)
            if claim_id and claim_text:
                claim_texts[claim_id] = claim_text
    if claim_texts:
        return claim_texts
    fallback = (core_fact or "핵심 주장").strip() or "핵심 주장"
    return {"C1": fallback}


def _stance_boost_text(text: str, qtype: str, stance: str) -> str:
    base = str(text or "").strip()
    if not base:
        return base
    if stance == "support":
        if qtype == "news" and "공식입장" not in base:
            return f"{base} 공식입장"
        if qtype == "verification" and "사실 확인" not in base:
            return f"{base} 사실 확인"
        return base
    if qtype == "news" and "반박" not in base and "해명" not in base:
        return f"{base} 반박"
    if qtype == "verification" and "허위" not in base and "쟁점" not in base:
        return f"{base} 허위 여부"
    return base


def _default_intent_for_type(qtype: str, mode: str) -> str:
    if qtype == "news":
        return "official_statement" if mode in _RUMOR_MODES else "news_followup"
    if qtype == "verification":
        return "fact_check" if mode in _RUMOR_MODES else "verification"
    return "direct"


def _ensure_stance_split(
    variants: List[Dict[str, Any]],
    *,
    core_fact: str,
    normalized_claims: Any,
    claim_mode: str,
) -> List[Dict[str, Any]]:
    if not bool(settings.stage2_enable_stance_split):
        return variants

    mode = _normalize_claim_mode(claim_mode)
    claim_texts = _claim_text_map(normalized_claims, core_fact)
    merged: List[Dict[str, Any]] = []

    for idx, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict):
            continue
        standardized = _standardize_variant(
            _normalize_query_type(variant.get("type", "direct")),
            str(variant.get("text", "") or "").strip(),
            _copy_meta(variant.get("meta")),
            fallback_claim_id=str((_copy_meta(variant.get("meta"))).get("claim_id") or f"C{idx}"),
            claim_mode=mode,
        )
        merged.append(standardized)

    def _add_variant(claim_id: str, qtype: str, stance: str, text_seed: str) -> None:
        meta = {
            "claim_id": claim_id,
            "source": "stance_guardrail",
            "intent": _default_intent_for_type(qtype, mode),
            "mode": mode,
            "stance": stance,
        }
        merged.append(
            _standardize_variant(
                qtype,
                _stance_boost_text(text_seed, qtype, stance),
                meta,
                fallback_claim_id=claim_id,
                claim_mode=mode,
            )
        )

    for claim_id, claim_text in claim_texts.items():
        for qtype in ("news", "verification"):
            group = []
            for variant in merged:
                if not isinstance(variant, dict):
                    continue
                if _normalize_query_type(variant.get("type", "direct")) != qtype:
                    continue
                meta = variant.get("meta") if isinstance(variant.get("meta"), dict) else {}
                if str(meta.get("claim_id") or "").strip() == claim_id:
                    group.append(variant)

            if not group:
                _add_variant(claim_id, qtype, "support", claim_text)
                _add_variant(claim_id, qtype, "skeptic", claim_text)
                continue

            has_support = any(
                _normalize_stance((variant.get("meta") or {}).get("stance")) == "support"
                for variant in group
            )
            has_skeptic = any(
                _normalize_stance((variant.get("meta") or {}).get("stance")) == "skeptic"
                for variant in group
            )

            seed = group[0]
            seed_text = str(seed.get("text") or "").strip() or claim_text
            seed_meta = seed.get("meta") if isinstance(seed.get("meta"), dict) else {}
            seed_intent = _default_intent_for_type(qtype, mode)
            if isinstance(seed_meta, dict) and seed_meta.get("intent"):
                seed_intent = str(seed_meta.get("intent"))

            if not has_support:
                _add_variant(claim_id, qtype, "support", seed_text)
                merged[-1]["meta"]["intent"] = seed_intent
            if not has_skeptic:
                _add_variant(claim_id, qtype, "skeptic", seed_text)
                merged[-1]["meta"]["intent"] = seed_intent

    return merged


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

        if not text:
            q["text"] = _rebuild_query_text(qtype, keywords, type_max_len, "", claim)
        elif len(text) > type_max_len:
            q["text"] = text[:type_max_len].strip()
            logger.info("[YouTube] Truncated %s query from %d to %d chars", qtype, len(text), len(q["text"]))

    result["query_variants"] = variants
    return result


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

def generate_rule_based_fallback(claim: str, claim_mode: str = "fact") -> Dict[str, Any]:
    """LLM 실패 시 규칙 기반 쿼리 생성."""
    words = claim.split()
    keywords = [w for w in words if len(w) > 1]
    mode = _normalize_claim_mode(claim_mode)

    variants = [
        {
            "type": "direct",
            "text": claim,
            "meta": {"intent": "direct", "mode": mode, "stance": "neutral"},
        },
        {
            "type": "verification",
            "text": f"{claim} 팩트체크",
            "meta": {
                "intent": "fact_check" if mode in _RUMOR_MODES else "verification",
                "mode": mode,
                "stance": "support",
            },
        },
        {
            "type": "verification",
            "text": f"{claim} 허위 여부",
            "meta": {
                "intent": "fact_check" if mode in _RUMOR_MODES else "verification",
                "mode": mode,
                "stance": "skeptic",
            },
        },
        {
            "type": "news",
            "text": f"{claim} 뉴스",
            "meta": {
                "intent": "official_statement" if mode in _RUMOR_MODES else "news_followup",
                "mode": mode,
                "stance": "support",
            },
        },
        {
            "type": "news",
            "text": f"{claim} 반박",
            "meta": {
                "intent": "official_statement" if mode in _RUMOR_MODES else "news_followup",
                "mode": mode,
                "stance": "skeptic",
            },
        },
    ]

    return {
        "core_fact": claim,
        "query_variants": variants,
        "keyword_bundles": {
            "primary": keywords[:3],
            "secondary": keywords[3:6],
        },
        "search_constraints": {"note": "rule-based fallback"},
    }


def _finalize_query_variants(
    result: Dict[str, Any],
    *,
    normalized_claims: Any,
    claim_mode: str,
    claim_text: str,
) -> List[Dict[str, Any]]:
    variants = result.get("query_variants", [])
    core_fact = str(result.get("core_fact") or claim_text).strip() or claim_text
    fallback_claim_id = _primary_claim_id(normalized_claims)

    variants = _augment_with_normalized_claims(variants, normalized_claims, claim_mode)
    variants = _sanitize_claim_refs(variants, normalized_claims, fallback_claim_id, claim_mode)
    variants = _dedupe_query_variants(variants)
    variants = _ensure_rumor_intents(variants, core_fact, claim_mode, normalized_claims)
    variants = _ensure_stance_split(
        variants,
        core_fact=core_fact,
        normalized_claims=normalized_claims,
        claim_mode=claim_mode,
    )
    variants = _sanitize_claim_refs(variants, normalized_claims, fallback_claim_id, claim_mode)
    variants = _dedupe_query_variants(variants)
    return variants


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
    
    try:
        claim_text = state.get("claim_text", "")
        context = state.get("canonical_evidence", {})
        if not isinstance(context, dict):
            context = {}
        normalize_claims = state.get("normalize_claims")
        claim_mode = _normalize_claim_mode(state.get("claim_mode"))
        risk_markers = state.get("risk_markers") if isinstance(state.get("risk_markers"), list) else []
        verification_priority = str(state.get("verification_priority") or "normal").strip().lower() or "normal"
        state["querygen_claims"] = []

        logger.info(
            "[%s] Stage2 시작: claim=%s..., mode=%s, verification_priority=%s",
            trace_id,
            claim_text[:50],
            claim_mode,
            verification_priority,
        )

        if not claim_text:
            logger.warning("[%s] claim_text 비어있음, fallback 적용", trace_id)
            result = generate_rule_based_fallback("", claim_mode)
            result["query_variants"] = _finalize_query_variants(
                result,
                normalized_claims=normalize_claims,
                claim_mode=claim_mode,
                claim_text=claim_text,
            )
            state["query_variants"] = result["query_variants"]
            state["keyword_bundles"] = result["keyword_bundles"]
            state["search_constraints"] = result["search_constraints"]
            state["query_core_fact"] = result.get("core_fact", "")
            if isinstance(normalize_claims, list):
                state["querygen_claims"] = normalize_claims
            return state

        try:
            # LLM 기반 쿼리 생성 (override prompt 지원)
            prompt_override = state.get("querygen_prompt") or ""
            system_prompt = load_system_prompt()
            if prompt_override.strip():
                parsed, slm_raw = generate_queries_with_prompt_override(state, prompt_override)
                variants = _query_variants_from_team_a(parsed, claim_mode=claim_mode)
                if variants:
                    result = {
                        "core_fact": parsed.get("core_fact") or claim_text,
                        "query_variants": variants,
                        "keyword_bundles": parsed.get("keyword_bundles", {"primary": [], "secondary": []}),
                        "search_constraints": parsed.get("search_constraints", {}),
                    }
                    state["querygen_claims"] = parsed.get("claims") or parsed.get("주장들") or []
                    state["querygen_prompt_used"] = parsed.get("_prompt_used")
                else:
                    result = postprocess_queries(parsed, claim_text, claim_mode=claim_mode)
                state["prompt_querygen_user"] = parsed.get("_prompt_used")
                state["prompt_querygen_system"] = ""
                state["slm_raw_querygen"] = slm_raw
            else:
                state["prompt_querygen_user"] = build_querygen_user_prompt(
                    claim_text,
                    context,
                    normalize_claims,
                    claim_mode=claim_mode,
                    risk_markers=risk_markers,
                    verification_priority=verification_priority,
                )
                state["prompt_querygen_system"] = system_prompt
                parsed, slm_raw = generate_queries_with_llm(
                    claim_text,
                    context,
                    normalize_claims,
                    claim_mode=claim_mode,
                    risk_markers=risk_markers,
                    verification_priority=verification_priority,
                )
                result = postprocess_queries(parsed, claim_text, claim_mode=claim_mode)
                state["slm_raw_querygen"] = slm_raw
                state["querygen_claims"] = normalize_claims if isinstance(normalize_claims, list) else []

            source_type = (context or {}).get("source_type", "")
            if source_type == "youtube":
                result = postprocess_youtube_queries(result, claim_text, YOUTUBE_QUERY_MAX_LEN)
                logger.info("[%s] Stage2 YouTube postprocess applied (max_len=%d)", trace_id, YOUTUBE_QUERY_MAX_LEN)

            logger.info(
                "[%s] Stage2 LLM 완료: %d queries generated",
                trace_id,
                len(result["query_variants"]),
            )

        except (SLMError, ValueError) as e:
            logger.warning("[%s] LLM 쿼리 생성 실패, fallback 적용: %s", trace_id, e)
            result = generate_rule_based_fallback(claim_text, claim_mode)

        except Exception as e:
            logger.exception("[%s] Stage2 예상치 못한 오류: %s", trace_id, e)
            result = generate_rule_based_fallback(claim_text, claim_mode)

        result["query_variants"] = _finalize_query_variants(
            result,
            normalized_claims=normalize_claims,
            claim_mode=claim_mode,
            claim_text=claim_text,
        )

        # State 업데이트
        state["query_variants"] = result["query_variants"]
        state["keyword_bundles"] = result["keyword_bundles"]
        state["search_constraints"] = result["search_constraints"]
        state["query_core_fact"] = result.get("core_fact", claim_text)
        if not state.get("querygen_claims") and isinstance(normalize_claims, list):
            state["querygen_claims"] = normalize_claims

        if result.get("query_variants"):
            logger.info("[%s] Stage2 완료: top_query=%s", trace_id, result["query_variants"][0]["text"])
        else:
            logger.info("[%s] Stage2 완료: no queries generated", trace_id)

        return state
    
    except Exception as e:
        logger.exception(f"[{trace_id}] CRITICAL ERROR in stage02_querygen run function: {e}")
        logger.exception(f"[{trace_id}] State keys: {list(state.keys()) if isinstance(state, dict) else type(state)}")
        raise
