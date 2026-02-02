"""
Stage 9 - Judge (LLM 湲곕컲 ?덉쭏 ?됯? + ?ъ슜??移쒗솕??理쒖쥌 寃곌낵 ?앹꽦)

LLM???ъ슜?섏뿬 draft_verdict???덉쭏???됯??섍퀬,
?ъ슜?먭? ?댄빐?섍린 ?ъ슫 ?뺥깭??理쒖쥌 寃곌낵臾쇱쓣 ?앹꽦?⑸땲??

??븷 (2?④퀎):
1. ?덉쭏 ?됯? (Quality Evaluation)
   - Hallucination 寃?? reasoning_bullet??citations濡??룸컺移⑤릺?붿?
   - Grounding Precision 寃?? quote媛 二쇱옣怨?愿?⑥엳?붿?
   - Consistency 寃?? stance媛 reasoning怨??쇱튂?섎뒗吏
   - Policy 寃?? PII ?몄텧, ?꾪뿕 肄섑뀗痢??щ?

2. ?ъ슜??移쒗솕??寃곌낵 ?앹꽦 (User-Friendly Output)
   - "XX% ?뺣쪧濡??ъ떎?낅땲?? ?뺥깭???ㅻ뱶?쇱씤
   - ?듭떖 洹쇨굅? 異쒖쿂 ?뺣━
   - 二쇱쓽?ы빆 諛?異붽? ?뺤씤 沅뚯옣 ?ы빆

Input state keys:
    - trace_id: str
    - claim_text: str (寃利????二쇱옣)
    - draft_verdict: dict (Stage 8 寃곌낵)
    - quality_score: int (Stage 8 ?덉쭏 ?먯닔)
    - evidence_topk: list[dict] (Stage 5 利앷굅/異쒖쿂)
    - language: str

Output state keys:
    - final_verdict: dict (PRD ?ㅽ궎留?+ ?덉쭏 ?됯? + ?ъ슜??移쒗솕???꾨뱶)
    - user_result: dict (?대씪?댁뼵???쒖떆??寃곌낵)
    - risk_flags: list[str]
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, Any, List, Optional
from pathlib import Path

import requests

from app.stages._shared.guardrails import (
    parse_judge_json_with_retry,
    validate_judge_output,
    JSONParseError,
)
from app.stages._shared.gateway_runtime import (
    GatewayRuntime,
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryPolicy,
    RetryConfig,
    GatewayError,
    GatewayTimeoutError,
    GatewayValidationError,
)

logger = logging.getLogger(__name__)

# ?덉쭏 寃뚯씠???꾧퀎移?QUALITY_SCORE_CUTOFF = 65

# Judge ?꾨＼?꾪듃 寃쎈줈 (Stage ?⑥씪 ?뚯뒪)
PROMPT_FILE = Path(__file__).parent / "prompt_judge.txt"


@dataclass
class LLMConfig:
    """LLM ?ㅼ젙."""

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4.1"
    timeout_seconds: int = 60
    max_tokens: int = 1024
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """?섍꼍 蹂?섏뿉???ㅼ젙 濡쒕뱶."""
        return cls(
            base_url=os.getenv("JUDGE_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("JUDGE_API_KEY", ""),
            model=os.getenv("JUDGE_MODEL", "gpt-4.1"),
            timeout_seconds=int(os.getenv("JUDGE_TIMEOUT_SECONDS", "60")),
            max_tokens=int(os.getenv("JUDGE_MAX_TOKENS", "1024")),
            temperature=float(os.getenv("JUDGE_TEMPERATURE", "0.2")),
        )


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """Judge ?쒖뒪???꾨＼?꾪듃 濡쒕뱶 (罹먯떛)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


_llm_runtime: Optional[GatewayRuntime] = None
_llm_config: Optional[LLMConfig] = None


def _get_llm_config() -> LLMConfig:
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig.from_env()
    return _llm_config


def _get_llm_runtime() -> GatewayRuntime:
    """LLMGateway.execute ?먮쫫???숈씪?섍쾶 ?ы쁽?섎뒗 ?고???"""
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
        _llm_runtime = GatewayRuntime(
            name="llm",
            circuit_breaker=CircuitBreaker(name="llm", config=circuit_config),
            retry_policy=retry_policy,
        )
    return _llm_runtime


def _call_openai_compatible(
    system_prompt: str,
    user_prompt: str,
    config: LLMConfig,
    **kwargs,
) -> str:
    """OpenAI ?명솚 API ?몄텧."""
    url = f"{config.base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": kwargs.get("max_tokens", config.max_tokens),
        "temperature": kwargs.get("temperature", config.temperature),
    }

    headers = {"Content-Type": "application/json"}
    if config.api_key and config.api_key != "ollama":
        headers["Authorization"] = f"Bearer {config.api_key}"

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        raise GatewayTimeoutError(
            f"LLM request timeout after {config.timeout_seconds}s"
        )
    except requests.exceptions.RequestException as e:
        raise GatewayError(f"LLM request failed: {e}", cause=e)
    except (KeyError, IndexError) as e:
        raise GatewayError(f"Invalid LLM response format: {e}", cause=e)


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    **kwargs,
) -> str:
    """LLM 호출 (OpenAI 호환 전용)."""
    config = _get_llm_config()
    return _call_openai_compatible(system_prompt, user_prompt, config, **kwargs)

def _build_judge_user_prompt(
    claim_text: str,
    draft_verdict: Dict[str, Any],
    evidence_topk: List[Dict[str, Any]],
    quality_score: int,
    language: str,
) -> str:
    """Judge ?ъ슜???꾨＼?꾪듃 ?앹꽦 (LLMGateway? ?숈씪)."""
    verdict_str = json.dumps(draft_verdict, ensure_ascii=False, indent=2)

    evidence_lines = []
    for ev in evidence_topk[:5]:
        evid_id = ev.get("evid_id", "unknown")
        title = ev.get("title", "")
        snippet = (ev.get("snippet") or ev.get("content", ""))[:300]
        evidence_lines.append(f"[{evid_id}] {title}")
        evidence_lines.append(f"  ?댁슜: {snippet}")
        evidence_lines.append("")
    evidence_str = "\n".join(evidence_lines) if evidence_lines else "(利앷굅 ?놁쓬)"

    return f"""## 寃利????二쇱옣
{claim_text}

## ?댁쟾 ?④퀎 ?먯젙 寃곌낵 (draft_verdict)
{verdict_str}

## ?먮낯 利앷굅 (evidence_topk)
{evidence_str}

## ?덉쭏 ?먯닔 (Stage 8)
{quality_score}/100

## ?붿껌
???뺣낫瑜?諛뷀깢?쇰줈 理쒖쥌 ?먯젙???됯??섍퀬, 吏?뺣맂 JSON ?뺤떇?쇰줈 寃곌낵瑜?異쒕젰?섏꽭??
?몄뼱: {language}
"""


def _postprocess_judge_result(
    parsed: Dict[str, Any],
    draft_verdict: Dict[str, Any],
    evidence_topk: List[Dict[str, Any]],
    quality_score: int,
) -> Dict[str, Any]:
    """Judge 寃곌낵 ?꾩쿂由?- ?덉쭏 ?됯? + ?ъ슜??移쒗솕???뺤떇 蹂댁옣."""
    stance = draft_verdict.get("stance", "UNVERIFIED")
    confidence = draft_verdict.get("confidence", 0.0)
    citations_count = len(draft_verdict.get("citations", []))

    evaluation = parsed.get("evaluation", {})
    hallucination_count = evaluation.get("hallucination_count", 0)
    grounding_score = evaluation.get("grounding_score", 1.0)
    is_consistent = evaluation.get("is_consistent", True)
    policy_violations = evaluation.get("policy_violations", [])

    verdict_korean_map = {
        "TRUE": "?ъ떎?낅땲??,
        "FALSE": "嫄곗쭞?낅땲??,
        "MIXED": "?쇰? ?ъ떎?낅땲??,
        "UNVERIFIED": "?뺤씤???대졄?듬땲??,
    }

    verdict_label = parsed.get("verdict_label", stance)

    if quality_score < 65 or citations_count == 0:
        verdict_label = "UNVERIFIED"
        confidence = 0.0
    elif hallucination_count >= 2 or grounding_score < 0.5:
        verdict_label = "UNVERIFIED"
        confidence = max(0.0, confidence * 0.5)
    elif not is_consistent:
        confidence = max(0.0, confidence * 0.7)

    confidence_percent = parsed.get("confidence_percent", int(confidence * 100))

    risk_flags = list(parsed.get("risk_flags", []))
    if quality_score < 65:
        if "QUALITY_GATE_FAILED" not in risk_flags:
            risk_flags.append("QUALITY_GATE_FAILED")
    if citations_count < 2 or grounding_score < 0.7:
        if "LOW_EVIDENCE" not in risk_flags:
            risk_flags.append("LOW_EVIDENCE")
    if policy_violations:
        if "POLICY_RISK" not in risk_flags:
            risk_flags.append("POLICY_RISK")

    evidence_summary = parsed.get("evidence_summary", [])
    if not evidence_summary:
        evidence_summary = _build_evidence_summary(draft_verdict, evidence_topk)

    return {
        "evaluation": {
            "hallucination_count": hallucination_count,
            "grounding_score": grounding_score,
            "is_consistent": is_consistent,
            "policy_violations": policy_violations,
        },
        "verdict_label": verdict_label,
        "verdict_korean": parsed.get("verdict_korean", verdict_korean_map.get(verdict_label, "?뺤씤???대졄?듬땲??)),
        "confidence_percent": confidence_percent,
        "headline": parsed.get(
            "headline",
            f"??二쇱옣? {confidence_percent}% ?뺣쪧濡?{verdict_korean_map.get(verdict_label, '?뺤씤???대졄?듬땲??)}",
        ),
        "explanation": parsed.get("explanation", ""),
        "evidence_summary": evidence_summary,
        "cautions": parsed.get("cautions", draft_verdict.get("weak_points", [])),
        "recommendation": parsed.get("recommendation", ""),
        "risk_flags": risk_flags,
        "_quality_score": quality_score,
        "_original_stance": stance,
        "_original_confidence": confidence,
    }


def _build_evidence_summary(
    draft_verdict: Dict[str, Any],
    evidence_topk: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """draft_verdict?먯꽌 evidence_summary ?앹꽦."""
    evidence_map = {ev.get("evid_id", ""): ev for ev in evidence_topk}
    citations = draft_verdict.get("citations", [])
    reasoning = draft_verdict.get("reasoning_bullets", [])

    summary = []
    for i, cit in enumerate(citations[:3]):
        evid_id = cit.get("evid_id", "")
        source_ev = evidence_map.get(evid_id, {})

        point = ""
        for r in reasoning:
            if evid_id in r or (i == 0 and not point):
                point = r.replace("[吏吏]", "").replace("[諛섎컯]", "").strip()
                break

        if not point and cit.get("quote"):
            point = cit.get("quote", "")[:100]

        summary.append({
            "point": point or f"利앷굅 {i+1}",
            "source_title": source_ev.get("title", cit.get("title", "")),
            "source_url": source_ev.get("url", cit.get("url", "")),
        })

    return summary


def run(state: dict) -> dict:
    """
    Stage 9 ?ㅽ뻾: ?ъ슜??移쒗솕??理쒖쥌 寃곌낵 ?앹꽦.

    Args:
        state: ?뚯씠?꾨씪???곹깭 dict

    Returns:
        final_verdict? user_result媛 異붽???state
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    draft_verdict = state.get("draft_verdict", {})
    quality_score = state.get("quality_score", 0)
    evidence_topk = state.get("evidence_topk", [])
    language = state.get("language", "ko")

    logger.info(
        f"[{trace_id}] Stage9 ?쒖옉: "
        f"quality_score={quality_score}, "
        f"draft_stance={draft_verdict.get('stance', 'UNKNOWN')}"
    )

    # ?낅젰 寃利?
    if not draft_verdict:
        logger.warning(f"[{trace_id}] draft_verdict ?놁쓬, fallback ?곸슜")
        fallback = _create_fallback_result("寃利??곗씠?곌? ?놁뒿?덈떎")
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = ["QUALITY_GATE_FAILED"]
        return state

    try:
        # LLMGateway.judge_verdict? ?숈씪 ?먮쫫?쇰줈 Judge 寃곌낵 ?앹꽦
        system_prompt = load_system_prompt()
        user_prompt = _build_judge_user_prompt(
            claim_text, draft_verdict, evidence_topk, quality_score, language
        )

        runtime = _get_llm_runtime()

        def operation():
            def call_fn():
                return _call_llm(system_prompt, user_prompt)

            def retry_call_fn(retry_prompt: str):
                combined_prompt = f"{system_prompt}\n\n{retry_prompt}"
                return _call_llm(combined_prompt, user_prompt)

            try:
                parsed = parse_judge_json_with_retry(
                    call_fn,
                    max_retries=0,
                    retry_call_fn=retry_call_fn,
                )
            except JSONParseError as e:
                raise GatewayValidationError(f"JSON parsing failed: {e}", cause=e)

            parsed = validate_judge_output(parsed)
            return _postprocess_judge_result(parsed, draft_verdict, evidence_topk, quality_score)

        judge_result = runtime.execute(operation, "judge_verdict")

        # 理쒖쥌 寃곌낵 援ъ꽦
        final_verdict = _build_final_verdict(
            judge_result=judge_result,
            draft_verdict=draft_verdict,
            evidence_topk=evidence_topk,
            trace_id=trace_id,
        )

        # ?ъ슜???쒖떆??寃곌낵 (?대씪?댁뼵??吏곸젒 ?ъ슜)
        user_result = _build_user_result(judge_result, claim_text)

        # risk_flags 蹂묓빀
        existing_flags = state.get("risk_flags", [])
        new_flags = _determine_risk_flags(judge_result, quality_score, draft_verdict)
        merged_flags = list(set(existing_flags + new_flags))

        state["final_verdict"] = final_verdict
        state["user_result"] = user_result
        state["risk_flags"] = merged_flags

        # evaluation 寃곌낵 濡쒓퉭
        evaluation = judge_result.get("evaluation", {})
        logger.info(
            f"[{trace_id}] Stage9 ?꾨즺: "
            f"label={judge_result.get('verdict_label')}, "
            f"confidence={judge_result.get('confidence_percent')}%, "
            f"hallucination={evaluation.get('hallucination_count', 'N/A')}, "
            f"grounding={evaluation.get('grounding_score', 'N/A')}"
        )

    except GatewayError as e:
        logger.error(f"[{trace_id}] LLM Judge ?ㅽ뙣: {e}")
        fallback = _apply_rule_based_judge(draft_verdict, evidence_topk, quality_score, claim_text)
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = state.get("risk_flags", []) + ["LLM_JUDGE_FAILED"]

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage9 ?덉긽移?紐삵븳 ?ㅻ쪟: {e}")
        fallback = _create_fallback_result(str(e))
        state["final_verdict"] = fallback["final_verdict"]
        state["user_result"] = fallback["user_result"]
        state["risk_flags"] = state.get("risk_flags", []) + ["QUALITY_GATE_FAILED"]

    return state


def _build_final_verdict(
    judge_result: Dict[str, Any],
    draft_verdict: Dict[str, Any],
    evidence_topk: List[Dict[str, Any]],
    trace_id: str,
) -> Dict[str, Any]:
    """PRD ?ㅽ궎留?+ ?덉쭏 ?됯? + ?ъ슜??移쒗솕???꾨뱶瑜??ы븿??理쒖쥌 verdict."""
    # citations 蹂??
    raw_citations = draft_verdict.get("citations", [])
    formatted_citations = _format_citations(raw_citations, evidence_topk)

    # evaluation 異붿텧
    evaluation = judge_result.get("evaluation", {})

    llm_config = _get_llm_config()

    return {
        # PRD ?쒖? ?꾨뱶
        "analysis_id": trace_id,
        "label": judge_result.get("verdict_label", "UNVERIFIED"),
        "confidence": judge_result.get("confidence_percent", 0) / 100.0,
        "summary": judge_result.get("headline", ""),
        "rationale": [ev.get("point", "") for ev in judge_result.get("evidence_summary", [])],
        "citations": formatted_citations,
        "counter_evidence": [],
        "limitations": judge_result.get("cautions", []),
        "recommended_next_steps": [judge_result.get("recommendation", "")] if judge_result.get("recommendation") else [],
        "risk_flags": judge_result.get("risk_flags", []),
        "model_info": {
            "provider": "openai",
            "model": llm_config.model,
            "version": "v1.0",
        },
        "latency_ms": 0,
        "cost_usd": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),

        # ?덉쭏 ?됯? ?꾨뱶 (LLM Judge 寃곌낵)
        "evaluation": {
            "hallucination_count": evaluation.get("hallucination_count", -1),
            "grounding_score": evaluation.get("grounding_score", -1.0),
            "is_consistent": evaluation.get("is_consistent"),
            "policy_violations": evaluation.get("policy_violations", []),
        },

        # ?ъ슜??移쒗솕???뺤옣 ?꾨뱶
        "verdict_korean": judge_result.get("verdict_korean", "?뺤씤???대졄?듬땲??),
        "confidence_percent": judge_result.get("confidence_percent", 0),
        "headline": judge_result.get("headline", ""),
        "explanation": judge_result.get("explanation", ""),
        "evidence_summary": judge_result.get("evidence_summary", []),
    }


def _build_user_result(judge_result: Dict[str, Any], claim_text: str) -> Dict[str, Any]:
    """
    ?대씪?댁뼵?몄뿉??吏곸젒 ?쒖떆?????덈뒗 ?ъ슜??移쒗솕??寃곌낵.

    ??寃곌낵瑜?洹몃?濡?UI???뚮뜑留곹븷 ???덉뒿?덈떎.
    """
    verdict_label = judge_result.get("verdict_label", "UNVERIFIED")
    confidence_percent = judge_result.get("confidence_percent", 0)

    # 寃곌낵 ?꾩씠肄??됱긽 留ㅽ븨
    verdict_style = {
        "TRUE": {"icon": "??, "color": "green", "badge": "?ъ떎"},
        "FALSE": {"icon": "??, "color": "red", "badge": "嫄곗쭞"},
        "MIXED": {"icon": "?좑툘", "color": "orange", "badge": "?쇰? ?ъ떎"},
        "UNVERIFIED": {"icon": "??, "color": "gray", "badge": "?뺤씤 遺덇?"},
    }
    style = verdict_style.get(verdict_label, verdict_style["UNVERIFIED"])

    # 洹쇨굅 紐⑸줉 (異쒖쿂 ?ы븿)
    evidence_list = []
    for ev in judge_result.get("evidence_summary", []):
        evidence_list.append({
            "text": ev.get("point", ""),
            "source": {
                "title": ev.get("source_title", ""),
                "url": ev.get("source_url", ""),
            }
        })

    return {
        # ?ㅻ뜑 ?곸뿭
        "claim": claim_text,
        "verdict": {
            "label": verdict_label,
            "korean": judge_result.get("verdict_korean", "?뺤씤???대졄?듬땲??),
            "confidence_percent": confidence_percent,
            "icon": style["icon"],
            "color": style["color"],
            "badge": style["badge"],
        },

        # 硫붿씤 肄섑뀗痢?
        "headline": judge_result.get("headline", ""),
        "explanation": judge_result.get("explanation", ""),

        # 洹쇨굅 ?뱀뀡
        "evidence": evidence_list,

        # 二쇱쓽?ы빆
        "cautions": judge_result.get("cautions", []),

        # 異붽? ?덈궡
        "recommendation": judge_result.get("recommendation", ""),

        # 硫뷀??곗씠??
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _format_citations(
    raw_citations: List[Dict[str, Any]],
    evidence_topk: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """citations瑜?PRD ?ㅽ궎留덉뿉 留욊쾶 蹂??"""
    evidence_map = {ev.get("evid_id", ""): ev for ev in evidence_topk}

    formatted = []
    for cit in raw_citations:
        evid_id = cit.get("evid_id", "")
        source_ev = evidence_map.get(evid_id, {})

        formatted.append({
            "source_type": source_ev.get("source_type", "NEWS"),
            "title": cit.get("title") or source_ev.get("title", ""),
            "url": cit.get("url") or source_ev.get("url", ""),
            "doc_id": None,
            "doc_version_id": None,
            "locator": {},
            "quote": cit.get("quote", ""),
            "relevance": source_ev.get("score", 0.0),
        })

    return formatted


def _determine_risk_flags(
    judge_result: Dict[str, Any],
    quality_score: int,
    draft_verdict: Dict[str, Any],
) -> List[str]:
    """risk_flags 寃곗젙 (LLM 寃곌낵 + 洹쒖튃 湲곕컲 蹂묓빀)."""
    # LLM??諛섑솚??risk_flags 癒쇱? ?ъ슜
    flags = list(judge_result.get("risk_flags", []))

    # 洹쒖튃 湲곕컲 異붽? 寃??
    # ?덉쭏 ?먯닔 誘몃떖
    if quality_score < QUALITY_SCORE_CUTOFF:
        if "QUALITY_GATE_FAILED" not in flags:
            flags.append("QUALITY_GATE_FAILED")

    # ??? ?좊ː??
    if judge_result.get("confidence_percent", 0) < 50:
        if "LOW_CONFIDENCE" not in flags:
            flags.append("LOW_CONFIDENCE")

    # ?몄슜 遺議?
    citations_count = len(draft_verdict.get("citations", []))
    if citations_count < 2:
        if "LOW_EVIDENCE" not in flags:
            flags.append("LOW_EVIDENCE")

    # UNVERIFIED 寃곌낵
    if judge_result.get("verdict_label") == "UNVERIFIED":
        if "LOW_EVIDENCE" not in flags:
            flags.append("LOW_EVIDENCE")

    # evaluation 湲곕컲 異붽? 寃??
    evaluation = judge_result.get("evaluation", {})

    llm_config = _get_llm_config()
    if evaluation.get("hallucination_count", 0) >= 2:
        if "HALLUCINATION_DETECTED" not in flags:
            flags.append("HALLUCINATION_DETECTED")

    if evaluation.get("policy_violations"):
        if "POLICY_RISK" not in flags:
            flags.append("POLICY_RISK")

    return flags


def _apply_rule_based_judge(
    draft_verdict: Dict[str, Any],
    evidence_topk: List[Dict[str, Any]],
    quality_score: int,
    claim_text: str,
) -> Dict[str, Any]:
    """LLM ?ㅽ뙣 ??洹쒖튃 湲곕컲 ?먯젙."""
    stance = draft_verdict.get("stance", "UNVERIFIED")
    confidence = draft_verdict.get("confidence", 0.0)
    citations = draft_verdict.get("citations", [])

    # ?덉쭏 寃뚯씠??
    if quality_score < QUALITY_SCORE_CUTOFF or not citations:
        stance = "UNVERIFIED"
        confidence = 0.0

    verdict_korean_map = {
        "TRUE": "?ъ떎?낅땲??,
        "FALSE": "嫄곗쭞?낅땲??,
        "MIXED": "?쇰? ?ъ떎?낅땲??,
        "UNVERIFIED": "?뺤씤???대졄?듬땲??,
    }

    confidence_percent = int(confidence * 100)
    verdict_korean = verdict_korean_map.get(stance, "?뺤씤???대졄?듬땲??)

    # evidence_summary ?앹꽦
    evidence_map = {ev.get("evid_id", ""): ev for ev in evidence_topk}
    evidence_summary = []
    for cit in citations[:3]:
        evid_id = cit.get("evid_id", "")
        source_ev = evidence_map.get(evid_id, {})
        evidence_summary.append({
            "point": cit.get("quote", "")[:100] or "洹쇨굅 ?뺤씤 ?꾩슂",
            "source_title": source_ev.get("title", ""),
            "source_url": source_ev.get("url", ""),
        })

    judge_result = {
        # ?덉쭏 ?됯? (洹쒖튃 湲곕컲 - LLM ?놁쓬)
        "evaluation": {
            "hallucination_count": -1,  # -1: ?됯? 遺덇?
            "grounding_score": -1.0,
            "is_consistent": None,
            "policy_violations": [],
        },
        # ?ъ슜??移쒗솕??寃곌낵
        "verdict_label": stance,
        "verdict_korean": verdict_korean,
        "confidence_percent": confidence_percent,
        "headline": f"??二쇱옣? {confidence_percent}% ?뺣쪧濡?{verdict_korean}" if stance != "UNVERIFIED" else "??二쇱옣? ?꾩옱 ?뺤씤???대졄?듬땲??,
        "explanation": "?먮룞 遺꾩꽍 ?쒖뒪?쒖쓣 ?듯빐 寃利앸릺?덉뒿?덈떎." if stance != "UNVERIFIED" else "異⑸텇??洹쇨굅瑜??뺣낫?섏? 紐삵빐 ?뺤씤???대졄?듬땲??",
        "evidence_summary": evidence_summary,
        "cautions": ["?먮룞 遺꾩꽍 寃곌낵?대?濡?李멸퀬?⑹쑝濡쒕쭔 ?쒖슜??二쇱꽭??],
        "recommendation": "異붽? 寃利앹쓣 ?꾪빐 怨듭떇 異쒖쿂瑜?吏곸젒 ?뺤씤??蹂댁떆湲?諛붾엻?덈떎.",
        "risk_flags": ["LLM_JUDGE_FAILED"],
    }

    return {
        "final_verdict": _build_final_verdict(judge_result, draft_verdict, evidence_topk, ""),
        "user_result": _build_user_result(judge_result, claim_text),
    }


def _create_fallback_result(error_msg: str) -> Dict[str, Any]:
    """?먮윭 ??fallback 寃곌낵 ?앹꽦."""
    judge_result = {
        "verdict_label": "UNVERIFIED",
        "verdict_korean": "?뺤씤???대졄?듬땲??,
        "confidence_percent": 0,
        "headline": "??二쇱옣? ?꾩옱 ?뺤씤???대졄?듬땲??,
        "explanation": f"?쒖뒪???ㅻ쪟濡??명빐 寃利앹쓣 ?꾨즺?????놁뒿?덈떎. ({error_msg[:50]})",
        "evidence_summary": [],
        "cautions": ["?쒖뒪???ㅻ쪟 諛쒖깮"],
        "recommendation": "?좎떆 ???ㅼ떆 ?쒕룄?섍굅??吏곸젒 異쒖쿂瑜??뺤씤??二쇱꽭??",
    }

    final_verdict = {
        "analysis_id": "",
        "label": "UNVERIFIED",
        "confidence": 0.0,
        "summary": judge_result["headline"],
        "rationale": [],
        "citations": [],
        "counter_evidence": [],
        "limitations": ["?쒖뒪???ㅻ쪟 諛쒖깮"],
        "recommended_next_steps": [judge_result["recommendation"]],
        "risk_flags": ["QUALITY_GATE_FAILED"],
        "model_info": {"provider": "fallback", "model": "error", "version": "v1.0"},
        "latency_ms": 0,
        "cost_usd": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # ?덉쭏 ?됯? (fallback - ?됯? 遺덇?)
        "evaluation": {
            "hallucination_count": -1,
            "grounding_score": -1.0,
            "is_consistent": None,
            "policy_violations": [],
        },
        "verdict_korean": "?뺤씤???대졄?듬땲??,
        "confidence_percent": 0,
        "headline": judge_result["headline"],
        "explanation": judge_result["explanation"],
        "evidence_summary": [],
    }

    user_result = {
        "claim": "",
        "verdict": {
            "label": "UNVERIFIED",
            "korean": "?뺤씤???대졄?듬땲??,
            "confidence_percent": 0,
            "icon": "??,
            "color": "gray",
            "badge": "?뺤씤 遺덇?",
        },
        "headline": judge_result["headline"],
        "explanation": judge_result["explanation"],
        "evidence": [],
        "cautions": judge_result["cautions"],
        "recommendation": judge_result["recommendation"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "final_verdict": final_verdict,
        "user_result": user_result,
    }

