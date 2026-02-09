"""
Stage 9 - Judge (LLM 기반 최종 판정 + 사용자 친화적 결과 생성)

Stage6/7의 상반된 결과를 직접 비교하고,
별도 retrieval 근거를 함께 검토해 TRUE/FALSE 판결을 내립니다.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, Any, List, Optional
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.core.settings import settings
from app.db.session import SessionLocal
from app.services.rag_usecase import retrieve_wiki_context
from app.stages._shared.guardrails import (
    parse_judge_json_with_retry,
    validate_judge_output,
    JSONParseError,
)
from app.stages._shared.orchestrator_runtime import (
    OrchestratorRuntime,
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig,
    OrchestratorError,
    OrchestratorValidationError,
)

logger = logging.getLogger(__name__)

# Judge 프롬프트 경로 (Stage 단일 테스트)
PROMPT_FILE = Path(__file__).parent / "prompt_judge.txt"


@dataclass
class LLMConfig:
    """Stage9 LLM 호출 설정."""

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4.1"
    timeout_seconds: int = 60
    max_tokens: int = 1024
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """중앙 Settings에서 설정 로드."""
        return cls(
            base_url=settings.judge_base_url,
            api_key=settings.judge_api_key,
            model=settings.judge_model,
            timeout_seconds=settings.judge_timeout_seconds,
            max_tokens=settings.judge_max_tokens,
            temperature=settings.judge_temperature,
        )


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """Judge 시스템 프롬프트 로드."""
    return PROMPT_FILE.read_text(encoding="utf-8")


_llm_runtime: Optional[OrchestratorRuntime] = None
_llm_config: Optional[LLMConfig] = None


def _get_llm_config() -> LLMConfig:
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig.from_env()
    return _llm_config


def _get_llm_runtime() -> OrchestratorRuntime:
    """LLM 호출용 런타임(서킷브레이커+재시도) 반환."""
    global _llm_runtime
    if _llm_runtime is None:
        circuit_config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=60,
            success_threshold=2,
        )
        retry_config = RetryConfig(
            max_retries=2,
            base_delay=1.0,
            max_delay=10.0,
        )
        retry_policy = RetryPolicy(retry_config)
        retry_policy.add_retryable_exception(requests.exceptions.Timeout)
        retry_policy.add_retryable_exception(requests.exceptions.ConnectionError)
        _llm_runtime = OrchestratorRuntime(
            name="llm",
            circuit_breaker=CircuitBreaker(name="llm", config=circuit_config),
            retry_policy=retry_policy,
        )
    return _llm_runtime


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    **kwargs,
) -> str:
    """LLM 호출 (Shared Client 사용)."""
    config = _get_llm_config()
    from app.stages._shared.slm_client import SLMClient, SLMConfig

    api_key = (config.api_key or "").strip()
    if not api_key:
        base_url_lower = (config.base_url or "").lower()
        parsed = urlparse(config.base_url or "")
        host = (parsed.hostname or "").lower()
        if "ollama" in base_url_lower or host in {"localhost", "127.0.0.1"} or parsed.port == 11434:
            api_key = "ollama"
        else:
            raise OrchestratorValidationError("JUDGE_API_KEY is required for external judge provider")

    slm_config = SLMConfig(
        base_url=config.base_url,
        api_key=api_key,
        model=config.model,
        timeout=config.timeout_seconds,
        max_tokens=config.max_tokens,
        temperature=kwargs.get("temperature", config.temperature),
    )

    client = SLMClient(slm_config)
    return client.chat_completion(system_prompt, user_prompt, temperature=slm_config.temperature)


def _retrieve_judge_evidence(claim_text: str, search_mode: str) -> List[Dict[str, Any]]:
    """
    Judge 전용 retrieval.

    Stage9가 Stage6/7 외의 근거를 직접 확인하도록 별도 검색을 수행한다.
    """
    if not (claim_text or "").strip():
        return []

    try:
        with SessionLocal() as db:
            pack = retrieve_wiki_context(
                db=db,
                question=claim_text,
                top_k=5,
                page_limit=5,
                window=2,
                embed_missing=False,
                search_mode=search_mode or "auto",
            )
    except Exception as e:
        logger.warning(f"Judge retrieval 실패: {e}")
        return []

    sources = []
    for i, src in enumerate(pack.get("sources", []), start=1):
        evid_id = f"judge_wiki_{i}"
        sources.append(
            {
                "evid_id": evid_id,
                "source_type": "WIKIPEDIA",
                "title": src.get("title", ""),
                "url": f"wiki://page/{src.get('page_id')}" if src.get("page_id") else "",
                "snippet": src.get("snippet", ""),
            }
        )

    return sources


def _build_evidence_index(evidence_index: Dict[str, Any], retrieval_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Stage8의 evidence_index와 retrieval 근거를 합친다."""
    merged = dict(evidence_index or {})
    for src in retrieval_sources:
        evid_id = src.get("evid_id")
        if evid_id and evid_id not in merged:
            merged[evid_id] = {
                "evid_id": evid_id,
                "title": src.get("title", ""),
                "url": src.get("url", ""),
                "snippet": src.get("snippet", ""),
                "source_type": src.get("source_type", "WIKIPEDIA"),
            }
    return merged


def _build_citation_index(
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    retrieval_sources: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """evid_id 기준으로 인용 정보를 통합한다."""
    index: Dict[str, Dict[str, Any]] = {}

    for cit in (support_pack.get("citations", []) or []) + (skeptic_pack.get("citations", []) or []):
        evid_id = cit.get("evid_id")
        if not evid_id:
            continue
        index[evid_id] = {
            "evid_id": evid_id,
            "title": cit.get("title", ""),
            "url": cit.get("url", ""),
            "quote": cit.get("quote", ""),
        }

    # retrieval은 quote 대신 snippet을 사용한다.
    for src in retrieval_sources:
        evid_id = src.get("evid_id")
        if not evid_id:
            continue
        index.setdefault(
            evid_id,
            {
                "evid_id": evid_id,
                "title": src.get("title", ""),
                "url": src.get("url", ""),
                "quote": src.get("snippet", ""),
            },
        )

    return index


def _build_judge_user_prompt(
    claim_text: str,
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    evidence_index: Dict[str, Any],
    retrieval_sources: List[Dict[str, Any]],
    language: str,
) -> str:
    """Judge 입력을 LLM user prompt로 구성."""
    support_str = json.dumps(support_pack, ensure_ascii=False, indent=2)
    skeptic_str = json.dumps(skeptic_pack, ensure_ascii=False, indent=2)
    evidence_str = json.dumps(evidence_index, ensure_ascii=False, indent=2)
    retrieval_str = json.dumps(retrieval_sources, ensure_ascii=False, indent=2)

    return f"""## 검증 대상 주장
{claim_text}

## Stage6 (지지) 결과
{support_str}

## Stage7 (회의) 결과
{skeptic_str}

## evidence_index (evid_id 기준 테이블)
{evidence_str}

## retrieval_evidence (Judge 별도 검색)
{retrieval_str}

## 요청
위 정보를 바탕으로 최종 판결을 TRUE 또는 FALSE 중 하나로 결정하고,
지정된 JSON 형식으로 결과를 출력하세요.
언어: {language}
"""


def _postprocess_judge_result(
    parsed: Dict[str, Any],
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    evidence_index: Dict[str, Any],
) -> Dict[str, Any]:
    """Judge raw 결과를 서비스 스키마에 맞게 후처리."""
    verdict_korean_map = {
        "TRUE": "사실입니다",
        "FALSE": "거짓입니다",
    }

    label = (parsed.get("verdict_label") or "").upper().strip()
    support_cits = support_pack.get("citations", []) or []
    skeptic_cits = skeptic_pack.get("citations", []) or []

    if label not in {"TRUE", "FALSE"}:
        # Stage9가 최종 판결을 맡으므로, 유효하지 않은 라벨은 근거량으로 강제 결정한다.
        label = "TRUE" if len(support_cits) >= len(skeptic_cits) else "FALSE"

    confidence_percent = parsed.get("confidence_percent")
    if not isinstance(confidence_percent, (int, float)):
        fallback_conf = support_pack.get("confidence", 0.0) if label == "TRUE" else skeptic_pack.get("confidence", 0.0)
        confidence_percent = int(max(0.0, min(1.0, float(fallback_conf))) * 100)

    selected_ids = parsed.get("selected_evidence_ids") or []
    if not isinstance(selected_ids, list):
        selected_ids = []
    # evidence_index에 존재하는 ID만 허용
    selected_ids = [eid for eid in selected_ids if eid in evidence_index]

    if not selected_ids:
        # LLM이 선택 ID를 주지 않은 경우, 선택된 라벨의 citations을 기본 근거로 사용한다.
        base_cits = support_cits if label == "TRUE" else skeptic_cits
        selected_ids = [c.get("evid_id") for c in base_cits if c.get("evid_id") in evidence_index]

    evaluation = parsed.get("evaluation", {}) or {}
    risk_flags = list(parsed.get("risk_flags", []))

    if len(selected_ids) < 2 and "LOW_EVIDENCE" not in risk_flags:
        risk_flags.append("LOW_EVIDENCE")
    if evaluation.get("hallucination_count", 0) >= 2 and "HALLUCINATION_DETECTED" not in risk_flags:
        risk_flags.append("HALLUCINATION_DETECTED")
    if evaluation.get("policy_violations") and "POLICY_RISK" not in risk_flags:
        risk_flags.append("POLICY_RISK")
    if confidence_percent < 50 and "LOW_CONFIDENCE" not in risk_flags:
        risk_flags.append("LOW_CONFIDENCE")

    evidence_summary = parsed.get("evidence_summary")
    if not evidence_summary:
        evidence_summary = _build_evidence_summary(selected_ids, evidence_index)

    return {
        "evaluation": {
            "hallucination_count": evaluation.get("hallucination_count", 0),
            "grounding_score": evaluation.get("grounding_score", 1.0),
            "is_consistent": evaluation.get("is_consistent", True),
            "policy_violations": evaluation.get("policy_violations", []),
        },
        "verdict_label": label,
        "verdict_korean": parsed.get("verdict_korean", verdict_korean_map.get(label, "확인이 어렵습니다")),
        "confidence_percent": int(confidence_percent),
        "headline": parsed.get(
            "headline",
            f"이 주장은 {int(confidence_percent)}% 확률로 {verdict_korean_map.get(label, '확인이 어렵습니다')}",
        ),
        "explanation": parsed.get("explanation", ""),
        "evidence_summary": evidence_summary,
        "cautions": parsed.get("cautions", []),
        "recommendation": parsed.get("recommendation", ""),
        "risk_flags": risk_flags,
        "selected_evidence_ids": selected_ids,
    }


def _build_evidence_summary(
    selected_ids: List[str],
    evidence_index: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """선택된 evid_id 기반으로 evidence_summary 구성."""
    summary = []
    for evid_id in selected_ids[:3]:
        ev = evidence_index.get(evid_id, {})
        summary.append(
            {
                "point": (ev.get("snippet", "") or "")[:100],
                "source_title": ev.get("title", ""),
                "source_url": ev.get("url", ""),
            }
        )
    return summary


def _build_final_verdict(
    judge_result: Dict[str, Any],
    evidence_index: Dict[str, Any],
    citation_index: Dict[str, Dict[str, Any]],
    trace_id: str,
) -> Dict[str, Any]:
    """PRD 스키마 + 사용자 친화적 필드를 포함한 최종 verdict."""
    selected_ids = judge_result.get("selected_evidence_ids", [])
    formatted_citations = _format_citations(selected_ids, evidence_index, citation_index)

    llm_config = _get_llm_config()
    provider = _infer_provider_name(llm_config.base_url)

    return {
        "analysis_id": trace_id,
        "label": judge_result.get("verdict_label", "FALSE"),
        "confidence": judge_result.get("confidence_percent", 0) / 100.0,
        "summary": judge_result.get("headline", ""),
        "rationale": [ev.get("point", "") for ev in judge_result.get("evidence_summary", [])],
        "citations": formatted_citations,
        "counter_evidence": [],
        "limitations": judge_result.get("cautions", []),
        "recommended_next_steps": [judge_result.get("recommendation", "")] if judge_result.get("recommendation") else [],
        "risk_flags": judge_result.get("risk_flags", []),
        "model_info": {
            "provider": provider,
            "model": llm_config.model,
            "version": "v1.0",
        },
        "latency_ms": 0,
        "cost_usd": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation": judge_result.get("evaluation", {}),
        "verdict_korean": judge_result.get("verdict_korean", "확인이 어렵습니다"),
        "confidence_percent": judge_result.get("confidence_percent", 0),
        "headline": judge_result.get("headline", ""),
        "explanation": judge_result.get("explanation", ""),
        "evidence_summary": judge_result.get("evidence_summary", []),
    }


def _infer_provider_name(base_url: str) -> str:
    host = (urlparse(base_url or "").netloc or "").lower()
    if "openai" in host:
        return "openai"
    if "perplexity" in host:
        return "perplexity"
    if "anthropic" in host:
        return "anthropic"
    if "ollama" in host:
        return "ollama"
    return "custom"


def _build_user_result(judge_result: Dict[str, Any], claim_text: str) -> Dict[str, Any]:
    """클라이언트 표시용 결과."""
    verdict_label = judge_result.get("verdict_label", "FALSE")
    confidence_percent = judge_result.get("confidence_percent", 0)

    verdict_style = {
        "TRUE": {"icon": "✅", "color": "green", "badge": "사실"},
        "FALSE": {"icon": "❌", "color": "red", "badge": "거짓"},
    }
    style = verdict_style.get(verdict_label, verdict_style["FALSE"])

    evidence_list = []
    for ev in judge_result.get("evidence_summary", []):
        evidence_list.append(
            {
                "text": ev.get("point", ""),
                "source": {
                    "title": ev.get("source_title", ""),
                    "url": ev.get("source_url", ""),
                },
            }
        )

    return {
        "claim": claim_text,
        "verdict": {
            "label": verdict_label,
            "korean": judge_result.get("verdict_korean", "확인이 어렵습니다"),
            "confidence_percent": confidence_percent,
            "icon": style["icon"],
            "color": style["color"],
            "badge": style["badge"],
        },
        "headline": judge_result.get("headline", ""),
        "explanation": judge_result.get("explanation", ""),
        "evidence": evidence_list,
        "cautions": judge_result.get("cautions", []),
        "recommendation": judge_result.get("recommendation", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _format_citations(
    selected_ids: List[str],
    evidence_index: Dict[str, Any],
    citation_index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """selected_evidence_ids를 PRD 스키마 citation으로 변환."""
    formatted = []
    for evid_id in selected_ids:
        ev = evidence_index.get(evid_id, {})
        cit = citation_index.get(evid_id, {})
        formatted.append(
            {
                "source_type": ev.get("source_type", "NEWS"),
                "title": cit.get("title") or ev.get("title", ""),
                "url": cit.get("url") or ev.get("url", ""),
                "doc_id": None,
                "doc_version_id": None,
                "locator": {},
                "quote": cit.get("quote") or ev.get("snippet", ""),
                "relevance": 0.0,
            }
        )
    return formatted


def _determine_risk_flags(
    judge_result: Dict[str, Any],
) -> List[str]:
    """risk_flags 결정 (LLM 결과 기반)."""
    flags = list(judge_result.get("risk_flags", []))

    if judge_result.get("confidence_percent", 0) < 50 and "LOW_CONFIDENCE" not in flags:
        flags.append("LOW_CONFIDENCE")

    evaluation = judge_result.get("evaluation", {})
    if evaluation.get("hallucination_count", 0) >= 2 and "HALLUCINATION_DETECTED" not in flags:
        flags.append("HALLUCINATION_DETECTED")

    if evaluation.get("policy_violations") and "POLICY_RISK" not in flags:
        flags.append("POLICY_RISK")

    if len(judge_result.get("selected_evidence_ids", [])) < 2 and "LOW_EVIDENCE" not in flags:
        flags.append("LOW_EVIDENCE")

    return flags


def _apply_rule_based_judge(
    claim_text: str,
    support_pack: Dict[str, Any],
    skeptic_pack: Dict[str, Any],
    evidence_index: Dict[str, Any],
) -> Dict[str, Any]:
    """LLM 실패 시 규칙 기반 판정."""
    support_cits = support_pack.get("citations", []) or []
    skeptic_cits = skeptic_pack.get("citations", []) or []

    label = "TRUE" if len(support_cits) >= len(skeptic_cits) else "FALSE"
    confidence_percent = 30

    selected_ids = [c.get("evid_id") for c in (support_cits if label == "TRUE" else skeptic_cits) if c.get("evid_id") in evidence_index]

    judge_result = {
        "evaluation": {
            "hallucination_count": -1,
            "grounding_score": -1.0,
            "is_consistent": None,
            "policy_violations": [],
        },
        "verdict_label": label,
        "verdict_korean": "사실입니다" if label == "TRUE" else "거짓입니다",
        "confidence_percent": confidence_percent,
        "headline": f"이 주장은 {confidence_percent}% 확률로 {'사실입니다' if label == 'TRUE' else '거짓입니다'}",
        "explanation": "LLM 판정 실패로 규칙 기반 판단을 적용했습니다.",
        "evidence_summary": _build_evidence_summary(selected_ids, evidence_index),
        "cautions": ["자동 판정 결과이므로 참고용으로만 활용해 주세요"],
        "recommendation": "추가 검증을 위해 공식 출처를 직접 확인해 보시기 바랍니다.",
        "risk_flags": ["LLM_JUDGE_FAILED"],
        "selected_evidence_ids": selected_ids,
    }

    return {
        "final_verdict": _build_final_verdict(judge_result, evidence_index, {}, ""),
        "user_result": _build_user_result(judge_result, claim_text),
    }


def _create_fallback_result(error_msg: str) -> Dict[str, Any]:
    """에러 시 fallback 결과 생성."""
    judge_result = {
        "verdict_label": "FALSE",
        "verdict_korean": "거짓입니다",
        "confidence_percent": 0,
        "headline": "이 주장은 현재 확인이 어렵습니다",
        "explanation": f"시스템 오류로 인해 검증을 완료할 수 없습니다. ({error_msg[:50]})",
        "evidence_summary": [],
        "cautions": ["자동 분석 결과이므로 참고용으로만 활용해 주세요"],
        "recommendation": "추가 검증을 위해 공식 출처를 직접 확인해 보시기 바랍니다.",
        "risk_flags": ["QUALITY_GATE_FAILED"],
        "selected_evidence_ids": [],
    }

    final_verdict = _build_final_verdict(judge_result, {}, {}, "")
    user_result = _build_user_result(judge_result, "")

    return {
        "final_verdict": final_verdict,
        "user_result": user_result,
    }


def run(state: dict) -> dict:
    """
    Stage 9 실행: TRUE/FALSE 최종 판정 + 사용자 친화 결과 생성.
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    language = state.get("language", "ko")

    support_pack = state.get("support_pack", {})
    skeptic_pack = state.get("skeptic_pack", {})
    evidence_index = state.get("evidence_index", {})

    logger.info(
        f"[{trace_id}] Stage9 시작: support_cits={len(support_pack.get('citations', []))}, "
        f"skeptic_cits={len(skeptic_pack.get('citations', []))}"
    )

    if not support_pack and not skeptic_pack:
        logger.warning(f"[{trace_id}] support/skeptic pack 없음, fallback 적용")
        fallback = _create_fallback_result("검증 데이터가 없습니다")
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = ["QUALITY_GATE_FAILED"]
        return state

    try:
        # Stage9에서 별도 retrieval을 수행해 Judge가 직접 근거를 비교하도록 한다.
        retrieval_sources = _retrieve_judge_evidence(claim_text, state.get("search_mode", "auto"))
        state["judge_retrieval"] = retrieval_sources

        merged_evidence_index = _build_evidence_index(evidence_index, retrieval_sources)
        citation_index = _build_citation_index(support_pack, skeptic_pack, retrieval_sources)

        system_prompt = load_system_prompt()
        user_prompt = _build_judge_user_prompt(
            claim_text, support_pack, skeptic_pack, merged_evidence_index, retrieval_sources, language
        )
        state["prompt_judge_user"] = user_prompt
        state["prompt_judge_system"] = system_prompt

        runtime = _get_llm_runtime()
        last_response: str = ""

        def operation():
            def call_fn():
                nonlocal last_response
                last_response = _call_llm(system_prompt, user_prompt)
                return last_response

            def retry_call_fn(retry_prompt: str):
                combined_prompt = f"{system_prompt}\n\n{retry_prompt}"
                nonlocal last_response
                last_response = _call_llm(combined_prompt, user_prompt)
                return last_response

            try:
                parsed = parse_judge_json_with_retry(
                    call_fn,
                    max_retries=2,
                    retry_call_fn=retry_call_fn,
                )
            except JSONParseError as e:
                state["slm_raw_judge"] = last_response
                raise OrchestratorValidationError(f"JSON parsing failed: {e}", cause=e)

            state["slm_raw_judge"] = last_response
            parsed = validate_judge_output(parsed)
            return _postprocess_judge_result(parsed, support_pack, skeptic_pack, merged_evidence_index)

        judge_result = runtime.execute(operation, "judge_verdict")

        final_verdict = _build_final_verdict(
            judge_result=judge_result,
            evidence_index=merged_evidence_index,
            citation_index=citation_index,
            trace_id=trace_id,
        )

        user_result = _build_user_result(judge_result, claim_text)

        existing_flags = state.get("risk_flags", [])
        new_flags = _determine_risk_flags(judge_result)
        merged_flags = list(set(existing_flags + new_flags))

        state["final_verdict"] = final_verdict
        state["user_result"] = user_result
        state["risk_flags"] = merged_flags

        evaluation = judge_result.get("evaluation", {})
        logger.info(
            f"[{trace_id}] Stage9 완료: label={judge_result.get('verdict_label')}, "
            f"confidence={judge_result.get('confidence_percent')}%, "
            f"hallucination={evaluation.get('hallucination_count', 'N/A')}, "
            f"grounding={evaluation.get('grounding_score', 'N/A')}"
        )

    except OrchestratorError as e:
        logger.error(f"[{trace_id}] LLM Judge 실패: {e}")
        fallback = _apply_rule_based_judge(claim_text, support_pack, skeptic_pack, evidence_index)
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = state.get("risk_flags", []) + ["LLM_JUDGE_FAILED"]

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage9 예상치 못한 오류: {e}")
        fallback = _create_fallback_result(str(e))
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = state.get("risk_flags", []) + ["QUALITY_GATE_FAILED"]

    return state
