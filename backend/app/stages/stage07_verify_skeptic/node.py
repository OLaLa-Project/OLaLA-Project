"""
Stage 7 - Skeptical Verification (회의적 관점 검증)

주장을 회의적인 관점에서 증거를 분석합니다.
SLM을 호출하여 DraftVerdict를 생성합니다.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.settings import settings
from app.stages._shared.guardrails import (
    build_draft_verdict,
    enrich_partial_citations_from_evidence,
    parse_json_with_retry,
    recover_partial_draft_verdict,
)
from app.stages._shared.slm_client import SLMError, call_slm2

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).parent / "prompt_skeptical.txt"
MAX_SNIPPET_LENGTH = 320
DEFAULT_LANGUAGE = "ko"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """시스템 프롬프트 로드 (캐싱)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


def _normalize_mode(value: Any) -> str:
    raw = str(value or "fact").strip().lower()
    if raw in {"fact", "rumor", "mixed"}:
        return raw
    if "rumor" in raw and "fact" in raw:
        return "mixed"
    if "rumor" in raw:
        return "rumor"
    return "fact"


def _required_intents() -> set[str]:
    raw = str(settings.stage6_rumor_required_intents_csv or "").strip()
    if not raw:
        return {"official_statement", "fact_check"}
    intents: set[str] = set()
    for token in raw.split(","):
        intent = token.strip().lower()
        if intent:
            intents.add(intent)
    return intents or {"official_statement", "fact_check"}


def _prompt_evidence_limit() -> int:
    return max(1, int(settings.stage67_prompt_evidence_limit))


def _snippet_max_chars() -> int:
    return max(120, int(settings.stage67_prompt_snippet_max_chars))


def _response_max_tokens() -> int:
    return max(128, int(settings.stage67_response_max_tokens))


def _json_retry_max_tokens() -> int:
    return max(128, int(settings.stage67_json_retry_max_tokens))


def _metadata(ev: dict[str, Any]) -> dict[str, Any]:
    return ev.get("metadata") if isinstance(ev.get("metadata"), dict) else {}


def _intent(ev: dict[str, Any]) -> str:
    return str(_metadata(ev).get("intent") or "").strip().lower()


def _claim_id(ev: dict[str, Any]) -> str:
    return str(_metadata(ev).get("claim_id") or "").strip()


def _mode(ev: dict[str, Any], fallback: str) -> str:
    value = _metadata(ev).get("mode")
    return _normalize_mode(value if value is not None else fallback)


def _pre_score(ev: dict[str, Any]) -> float:
    try:
        return float(_metadata(ev).get("pre_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _evid_id(ev: dict[str, Any], idx: int) -> str:
    return str(ev.get("evid_id") or f"ev_{idx}")


def _rank_score(ev: dict[str, Any]) -> float:
    score_candidates = [ev.get("score"), ev.get("relevance"), _metadata(ev).get("pre_score")]
    for raw in score_candidates:
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0


def _trim_evidence_for_prompt(
    evidence_topk: list[dict[str, Any]],
    claim_mode: str,
    required_intents: set[str],
) -> list[dict[str, Any]]:
    if len(evidence_topk) <= _prompt_evidence_limit():
        return list(evidence_topk)

    ranked = sorted(evidence_topk, key=_rank_score, reverse=True)
    limit = _prompt_evidence_limit()
    if claim_mode not in {"rumor", "mixed"}:
        return ranked[:limit]

    required = [ev for ev in ranked if _intent(ev) in required_intents]
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    for idx, ev in enumerate(required, start=1):
        evid_id = _evid_id(ev, idx)
        if evid_id in selected_ids:
            continue
        selected.append(ev)
        selected_ids.add(evid_id)
        if len(selected) >= limit:
            return selected

    for idx, ev in enumerate(ranked, start=1):
        evid_id = _evid_id(ev, idx)
        if evid_id in selected_ids:
            continue
        selected.append(ev)
        selected_ids.add(evid_id)
        if len(selected) >= limit:
            break

    return selected


def truncate_snippet(snippet: str, max_length: int = MAX_SNIPPET_LENGTH) -> str:
    if len(snippet) <= max_length:
        return snippet
    return snippet[:max_length] + "..."


def format_evidence_for_prompt(evidence_topk: list[dict], claim_mode: str) -> str:
    if not evidence_topk:
        return "(증거 없음)"

    lines = []
    for idx, ev in enumerate(evidence_topk, 1):
        evid_id = _evid_id(ev, idx)
        title = ev.get("title", "제목 없음")
        url = ev.get("url", "")
        text_content = ev.get("snippet") or ev.get("content", "")
        snippet = truncate_snippet(str(text_content), _snippet_max_chars())
        source_type = ev.get("source_type", "WEB_URL")

        lines.append(f"[{evid_id}] ({source_type}) {title}")
        if url:
            lines.append(f"    URL: {url}")
        lines.append(
            "    메타: "
            f"intent={_intent(ev) or '-'}, "
            f"claim_id={_claim_id(ev) or '-'}, "
            f"mode={_mode(ev, claim_mode)}, "
            f"pre_score={_pre_score(ev):.4f}"
        )
        lines.append(f"    내용: {snippet}")
        lines.append("")

    return "\n".join(lines)


def build_user_prompt(
    claim_text: str,
    evidence_topk: list[dict],
    language: str,
    claim_mode: str,
    risk_markers: list[str],
    verification_priority: str,
) -> str:
    evidence_text = format_evidence_for_prompt(evidence_topk, claim_mode)
    return f"""## 검증할 주장
{claim_text}

## claim_profile
- claim_mode: {claim_mode}
- risk_markers: {risk_markers}
- verification_priority: {verification_priority}

## 수집된 증거
{evidence_text}

## 요청
위 증거를 바탕으로 주장을 **회의적인 관점**에서 분석하고, 지정된 JSON 형식으로 결과를 출력하세요.
언어: {language}
"""


def create_fallback_verdict(reason: str) -> dict:
    return {
        "stance": "UNVERIFIED",
        "confidence": 0.0,
        "reasoning_bullets": [f"[시스템 오류] {reason}"],
        "citations": [],
        "weak_points": ["SLM 호출 실패로 분석 불가"],
        "followup_queries": [],
    }


def _required_intent_evidence_ids(evidence_topk: list[dict], required_intents: set[str]) -> set[str]:
    ids: set[str] = set()
    for idx, ev in enumerate(evidence_topk, 1):
        if _intent(ev) in required_intents:
            ids.add(_evid_id(ev, idx))
    return ids


def _enforce_unverified(verdict: dict, reason: str) -> dict:
    normalized = dict(verdict)
    normalized["stance"] = "UNVERIFIED"
    normalized["confidence"] = 0.0
    bullets = normalized.get("reasoning_bullets")
    if not isinstance(bullets, list):
        bullets = []
    message = f"[시스템] {reason}"
    if message not in bullets:
        bullets.insert(0, message)
    normalized["reasoning_bullets"] = bullets
    return normalized


def _filter_citations_by_required_intents(
    verdict: dict,
    required_evid_ids: set[str],
) -> tuple[dict, int]:
    citations = verdict.get("citations") if isinstance(verdict.get("citations"), list) else []
    if not citations:
        return verdict, 0

    kept: list[dict[str, Any]] = []
    dropped = 0
    for citation in citations:
        if not isinstance(citation, dict):
            dropped += 1
            continue
        evid_id = str(citation.get("evid_id") or "").strip()
        if evid_id and evid_id in required_evid_ids:
            kept.append(citation)
        else:
            dropped += 1

    updated = dict(verdict)
    updated["citations"] = kept
    return updated, dropped


def _contradiction_signal_count(verdict: dict) -> int:
    bullets = verdict.get("reasoning_bullets") if isinstance(verdict.get("reasoning_bullets"), list) else []
    patterns = ("반박", "모순", "아니다", "허위", "오보", "부인", "거짓")
    count = 0
    for bullet in bullets:
        if not isinstance(bullet, str):
            continue
        text = bullet.strip()
        if not text:
            continue
        if any(pattern in text for pattern in patterns):
            count += 1

    citations = verdict.get("citations") if isinstance(verdict.get("citations"), list) else []
    if count == 0 and str(verdict.get("stance") or "").upper() == "FALSE" and citations:
        count = 1
    return count


def _apply_output_budget(verdict: dict) -> dict[str, Any]:
    normalized = dict(verdict)
    bullets = normalized.get("reasoning_bullets")
    if isinstance(bullets, list):
        normalized["reasoning_bullets"] = [str(item) for item in bullets if isinstance(item, str)][:2]

    citations = normalized.get("citations")
    if isinstance(citations, list):
        trimmed: list[dict[str, Any]] = []
        for item in citations:
            if not isinstance(item, dict):
                continue
            citation = dict(item)
            quote = str(citation.get("quote") or "")
            if len(quote) > 160:
                citation["quote"] = quote[:160]
            trimmed.append(citation)
            if len(trimmed) >= 1:
                break
        normalized["citations"] = trimmed
    return normalized


def _stage07_diagnostics(
    *,
    mode: str,
    input_pool_type: str,
    input_pool_avg_trust: float,
    contradiction_signal_count: int,
    used_citation_ids: list[str],
    has_required_intent: bool,
    prompt_evidence_count: int,
    total_evidence_count: int,
    parse_ok: bool,
    parse_retry_used: bool,
    raw_len: int,
    citation_input_count: int,
    citation_valid_count: int,
    partial_recovered: bool,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "input_pool_type": input_pool_type,
        "input_pool_avg_trust": input_pool_avg_trust,
        "contradiction_signal_count": contradiction_signal_count,
        "used_citation_ids": used_citation_ids,
        "has_required_intent": has_required_intent,
        "prompt_evidence_count": prompt_evidence_count,
        "total_evidence_count": total_evidence_count,
        "parse_ok": parse_ok,
        "parse_retry_used": parse_retry_used,
        "raw_len": raw_len,
        "citation_input_count": citation_input_count,
        "citation_valid_count": citation_valid_count,
        "partial_recovered": partial_recovered,
    }


def run(state: dict) -> dict:
    """Stage 7 실행: 회의적 관점 검증."""
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    language = state.get("language", DEFAULT_LANGUAGE)
    skeptic_pool = state.get("evidence_topk_skeptic", [])
    shared_pool = state.get("evidence_topk", [])
    if isinstance(skeptic_pool, list) and skeptic_pool:
        evidence_topk = skeptic_pool
        input_pool_type = "skeptic"
    else:
        evidence_topk = shared_pool if isinstance(shared_pool, list) else []
        input_pool_type = "shared_fallback"
    claim_mode = _normalize_mode(state.get("claim_mode"))
    risk_markers = state.get("risk_markers") if isinstance(state.get("risk_markers"), list) else []
    verification_priority = str(state.get("verification_priority") or "normal").strip().lower() or "normal"

    required_intents = _required_intents()
    required_evid_ids = _required_intent_evidence_ids(evidence_topk, required_intents)
    has_required_intent = bool(required_evid_ids)
    prompt_evidence = _trim_evidence_for_prompt(evidence_topk, claim_mode, required_intents)
    trust_values = []
    for evidence in evidence_topk:
        if not isinstance(evidence, dict):
            continue
        metadata = _metadata(evidence)
        try:
            trust_values.append(float(metadata.get("credibility_score")))
        except (TypeError, ValueError):
            continue
    input_pool_avg_trust = round(sum(trust_values) / len(trust_values), 4) if trust_values else 0.0

    logger.info(
        "[%s] Stage7 시작: claim=%s..., mode=%s, required_intents=%s",
        trace_id,
        claim_text[:50],
        claim_mode,
        sorted(required_intents),
    )

    if not evidence_topk:
        logger.warning("[%s] 증거 없음, UNVERIFIED 반환", trace_id)
        verdict = create_fallback_verdict("증거가 제공되지 않음")
        state["verdict_skeptic"] = verdict
        state["stage07_diagnostics"] = _stage07_diagnostics(
            mode=claim_mode,
            input_pool_type=input_pool_type,
            input_pool_avg_trust=input_pool_avg_trust,
            contradiction_signal_count=0,
            used_citation_ids=[],
            has_required_intent=False,
            prompt_evidence_count=0,
            total_evidence_count=0,
            parse_ok=False,
            parse_retry_used=False,
            raw_len=0,
            citation_input_count=0,
            citation_valid_count=0,
            partial_recovered=False,
        )
        return state

    if claim_mode in {"rumor", "mixed"} and not has_required_intent:
        logger.info("[%s] Stage7 단락: rumor/mixed 모드에서 required intent 근거 없음", trace_id)
        verdict = _enforce_unverified(
            create_fallback_verdict("루머 모드에서 공식입장/팩트체크 근거 부족"),
            "루머 모드에서 official_statement/fact_check 근거가 없어 UNVERIFIED 처리",
        )
        state["verdict_skeptic"] = verdict
        state["stage07_diagnostics"] = _stage07_diagnostics(
            mode=claim_mode,
            input_pool_type=input_pool_type,
            input_pool_avg_trust=input_pool_avg_trust,
            contradiction_signal_count=0,
            used_citation_ids=[],
            has_required_intent=False,
            prompt_evidence_count=0,
            total_evidence_count=len(evidence_topk),
            parse_ok=False,
            parse_retry_used=False,
            raw_len=0,
            citation_input_count=0,
            citation_valid_count=0,
            partial_recovered=False,
        )
        return state

    system_prompt = load_system_prompt()
    user_prompt = build_user_prompt(
        claim_text,
        prompt_evidence,
        language,
        claim_mode,
        [str(marker) for marker in risk_markers if isinstance(marker, str)],
        verification_priority,
    )
    state["prompt_skeptic_user"] = user_prompt
    state["prompt_skeptic_system"] = system_prompt

    last_response: str = ""

    def call_fn():
        nonlocal last_response
        last_response = call_slm2(system_prompt, user_prompt, max_tokens=_response_max_tokens())
        return last_response

    def retry_call_fn(retry_prompt: str):
        combined_prompt = f"{system_prompt}\n\n{retry_prompt}"
        nonlocal last_response
        last_response = call_slm2(combined_prompt, user_prompt, max_tokens=_json_retry_max_tokens())
        return last_response

    dropped_citation_count = 0
    parse_meta: dict[str, Any] = {}
    citation_input_count = 0
    citation_valid_count = 0

    try:
        raw_verdict = parse_json_with_retry(
            call_fn,
            retry_call_fn=retry_call_fn,
            retry_system_prompt=(
                "이전 응답이 JSON 스키마를 만족하지 못했습니다. "
                "아래 축약 스키마로 JSON만 출력하세요: "
                "{\"stance\":\"UNVERIFIED\",\"confidence\":0.0,"
                "\"reasoning_bullets\":[\"...\"],"
                "\"citations\":[{\"evid_id\":\"ev_x\",\"quote\":\"...\",\"url\":\"...\",\"title\":\"...\"}],"
                "\"weak_points\":[],\"followup_queries\":[]}"
            ),
            meta=parse_meta,
        )
        state["slm_raw_skeptic"] = last_response
        if (not raw_verdict) and (last_response or "").strip():
            recovered = recover_partial_draft_verdict(last_response)
            if recovered:
                parse_meta["partial_recovered"] = True
                raw_verdict = enrich_partial_citations_from_evidence(
                    recovered,
                    evidence_topk,
                    min_quote_length=10,
                    quote_max_chars=min(160, _snippet_max_chars()),
                )
                logger.warning(
                    "[%s] Stage7 partial JSON 복구 적용: keys=%s",
                    trace_id,
                    sorted(raw_verdict.keys()),
                )
        citation_input_count = len(raw_verdict.get("citations", []) or []) if isinstance(raw_verdict, dict) else 0

        verdict = build_draft_verdict(raw_verdict, evidence_topk)
        verdict = _apply_output_budget(verdict)
        citation_valid_count = len(verdict.get("citations", []) or [])

        if claim_mode in {"rumor", "mixed"}:
            verdict, dropped_citation_count = _filter_citations_by_required_intents(verdict, required_evid_ids)
            if not verdict.get("citations"):
                verdict = _enforce_unverified(
                    verdict,
                    "required intent(official_statement/fact_check) 인용이 없어 UNVERIFIED 처리",
                )

        logger.info(
            "[%s] Stage7 완료: stance=%s, confidence=%.2f, citations=%d",
            trace_id,
            verdict.get("stance"),
            float(verdict.get("confidence") or 0.0),
            len(verdict.get("citations") or []),
        )

    except SLMError as e:
        logger.error("[%s] SLM 호출 실패: %s", trace_id, e)
        state["slm_raw_skeptic"] = last_response
        verdict = create_fallback_verdict(f"SLM 호출 실패: {e}")

    except Exception as e:
        logger.exception("[%s] Stage7 예상치 못한 오류: %s", trace_id, e)
        state["slm_raw_skeptic"] = last_response
        verdict = create_fallback_verdict(f"내부 오류: {e}")

    verdict = _apply_output_budget(verdict)
    citation_valid_count = len(verdict.get("citations", []) or [])
    citations = verdict.get("citations") if isinstance(verdict.get("citations"), list) else []
    used_ids = [str(cit.get("evid_id") or "") for cit in citations if isinstance(cit, dict) and cit.get("evid_id")]
    contradiction_signal_count = _contradiction_signal_count(verdict)

    state["verdict_skeptic"] = verdict
    state["stage07_diagnostics"] = _stage07_diagnostics(
        mode=claim_mode,
        input_pool_type=input_pool_type,
        input_pool_avg_trust=input_pool_avg_trust,
        contradiction_signal_count=contradiction_signal_count,
        used_citation_ids=used_ids,
        has_required_intent=has_required_intent,
        prompt_evidence_count=len(prompt_evidence),
        total_evidence_count=len(evidence_topk),
        parse_ok=bool(parse_meta.get("parse_ok", False)),
        parse_retry_used=bool(parse_meta.get("parse_retry_used", False)),
        raw_len=int(parse_meta.get("raw_len", len(last_response or "")) or 0),
        citation_input_count=citation_input_count,
        citation_valid_count=citation_valid_count,
        partial_recovered=bool(parse_meta.get("partial_recovered", False)),
    )

    if dropped_citation_count:
        logger.info("[%s] Stage7 citation 재필터링으로 %d개 제거", trace_id, dropped_citation_count)

    return state
