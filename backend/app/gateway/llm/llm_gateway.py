"""
LLM Gateway.

SLM(Small Language Model) 호출을 관리하는 Gateway입니다.

Features:
- Circuit Breaker로 연쇄 장애 방지
- 재시도 정책 (지수 백오프)
- 스키마 변환 및 검증
- 메트릭 수집
- OpenAI API / Ollama Native API 폴백
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from functools import lru_cache

import requests

from ..core.base_gateway import (
    BaseGateway,
    GatewayError,
    GatewayTimeoutError,
    GatewayValidationError,
)
from ..core.circuit_breaker import CircuitBreakerConfig
from ..core.retry_policy import RetryConfig
from ..schemas import (
    Citation,
    DraftVerdict,
    SchemaTransformer,
)

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 설정."""

    base_url: str = ""
    """API 기본 URL"""

    api_key: str = "ollama"
    """API 키"""

    model: str = "gemma3:4b"
    """모델 이름"""

    timeout_seconds: int = 60
    """요청 타임아웃"""

    max_tokens: int = 1024
    """최대 토큰 수"""

    temperature: float = 0.2
    """생성 온도"""

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """환경 변수에서 설정 로드."""
        return cls(
            base_url=os.getenv("SLM_BASE_URL", "http://ollama:11434/v1"),
            api_key=os.getenv("SLM_API_KEY", "ollama"),
            model=os.getenv("SLM_MODEL", "gemma3:4b"),
            timeout_seconds=int(os.getenv("SLM_TIMEOUT_SECONDS", "60")),
            max_tokens=int(os.getenv("SLM_MAX_TOKENS", "1024")),
            temperature=float(os.getenv("SLM_TEMPERATURE", "0.2")),
        )


class LLMGateway(BaseGateway):
    """
    LLM Gateway.

    SLM 호출을 중앙에서 관리합니다.

    사용 예:
        gateway = LLMGateway()

        # 기본 생성
        response = gateway.generate(system_prompt, user_prompt)

        # 검증 작업 (Stage 6/7)
        verdict = gateway.verify_claim(
            claim_text="...",
            citations=[...],
            perspective="supportive",
        )
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        # 기본 설정
        circuit_config = circuit_config or CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=60,
            success_threshold=2,
        )
        retry_config = retry_config or RetryConfig(
            max_retries=2,
            base_delay=1.0,
            max_delay=10.0,
        )

        super().__init__(
            name="llm",
            circuit_config=circuit_config,
            retry_config=retry_config,
        )

        self.config = config or LLMConfig.from_env()
        self.transformer = SchemaTransformer()

        # 재시도 가능한 예외 추가
        self.retry_policy.add_retryable_exception(requests.exceptions.Timeout)
        self.retry_policy.add_retryable_exception(requests.exceptions.ConnectionError)

        logger.info(
            f"LLMGateway initialized: model={self.config.model}, "
            f"url={self.config.base_url}"
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ) -> str:
        """
        텍스트 생성.

        Args:
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            **kwargs: 추가 파라미터 (temperature, max_tokens 등)

        Returns:
            생성된 텍스트

        Raises:
            GatewayError: 생성 실패
        """
        def operation():
            return self._call_llm(system_prompt, user_prompt, **kwargs)

        return self.execute(operation, "generate")

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        retry_on_parse_error: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        JSON 응답 생성.

        Args:
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            retry_on_parse_error: JSON 파싱 실패 시 재시도 여부
            **kwargs: 추가 파라미터

        Returns:
            파싱된 JSON 딕셔너리

        Raises:
            GatewayValidationError: JSON 파싱 실패
        """
        def operation():
            response = self._call_llm(system_prompt, user_prompt, **kwargs)
            return self._parse_json(response)

        try:
            return self.execute(operation, "generate_json")
        except GatewayError as e:
            if retry_on_parse_error and "JSON" in str(e):
                # JSON 파싱 실패 시 재시도 프롬프트로 다시 시도
                retry_prompt = (
                    f"{system_prompt}\n\n"
                    "중요: 이전 응답이 올바른 JSON 형식이 아닙니다. "
                    "반드시 유효한 JSON만 출력하세요. 다른 설명 없이 JSON만 출력하세요."
                )

                def retry_operation():
                    response = self._call_llm(retry_prompt, user_prompt, **kwargs)
                    return self._parse_json(response)

                return self.execute(retry_operation, "generate_json_retry")
            raise

    def verify_claim(
        self,
        claim_text: str,
        citations: List[Citation],
        perspective: str,
        language: str = "ko",
    ) -> DraftVerdict:
        """
        주장 검증 (Stage 6/7).

        Args:
            claim_text: 검증할 주장
            citations: 증거 리스트
            perspective: 관점 ("supportive" 또는 "skeptical")
            language: 언어 코드

        Returns:
            DraftVerdict 객체
        """
        # 프롬프트 로드
        system_prompt = self._load_verify_prompt(perspective)
        user_prompt = self._build_verify_user_prompt(
            claim_text, citations, language
        )

        def operation():
            response = self._call_llm(system_prompt, user_prompt)
            raw_verdict = self._parse_json(response)
            return self.transformer.parse_slm_verdict(
                raw_verdict, citations, perspective
            )

        operation_name = f"verify_{perspective}"

        try:
            return self.execute(operation, operation_name)
        except GatewayError as e:
            logger.error(f"Verification failed ({perspective}): {e}")
            return DraftVerdict.create_fallback(str(e), perspective)

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ) -> str:
        """실제 LLM API 호출."""
        # OpenAI 호환 API 시도
        try:
            return self._call_openai_compatible(
                system_prompt, user_prompt, **kwargs
            )
        except Exception as e:
            logger.warning(f"OpenAI API failed, trying Ollama native: {e}")

        # Ollama Native API 폴백
        return self._call_ollama_native(system_prompt, user_prompt, **kwargs)

    def _call_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ) -> str:
        """OpenAI 호환 API 호출."""
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }

        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key and self.config.api_key != "ollama":
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except requests.exceptions.Timeout:
            raise GatewayTimeoutError(
                f"LLM request timeout after {self.config.timeout_seconds}s"
            )
        except requests.exceptions.RequestException as e:
            raise GatewayError(f"LLM request failed: {e}", cause=e)
        except (KeyError, IndexError) as e:
            raise GatewayError(f"Invalid LLM response format: {e}", cause=e)

    def _call_ollama_native(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ) -> str:
        """Ollama Native API 호출."""
        # base_url에서 Ollama URL 추출
        ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        url = f"{ollama_url.rstrip('/')}/api/generate"

        payload = {
            "model": self.config.model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("response", "")

        except requests.exceptions.Timeout:
            raise GatewayTimeoutError(
                f"Ollama request timeout after {self.config.timeout_seconds}s"
            )
        except requests.exceptions.RequestException as e:
            raise GatewayError(f"Ollama request failed: {e}", cause=e)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """텍스트에서 JSON 추출 및 파싱."""
        import re

        # 마크다운 코드블록에서 추출
        code_block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if code_block_match:
            text = code_block_match.group(1)
        else:
            # 순수 JSON 블록 추출
            first_brace = text.find("{")
            last_brace = text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                text = text[first_brace:last_brace + 1]

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise GatewayValidationError(
                f"JSON parsing failed: {e}",
                cause=e,
            )

    def _load_verify_prompt(self, perspective: str) -> str:
        """검증 프롬프트 로드."""
        return self._load_prompt(perspective)

    def _get_default_verify_prompt(self, perspective: str) -> str:
        """기본 검증 프롬프트."""
        if perspective == "supportive":
            return """당신은 팩트체커입니다. 주어진 증거를 바탕으로 주장을 **지지하는 관점**에서 분석하세요.

출력 형식 (반드시 JSON):
{
    "stance": "TRUE" | "FALSE" | "MIXED" | "UNVERIFIED",
    "confidence": 0.0 ~ 1.0,
    "reasoning_bullets": ["근거1", "근거2", ...],
    "citations": [
        {"evid_id": "ev_xxx", "quote": "인용문", "supports": true}
    ],
    "weak_points": ["약점1", ...],
    "followup_queries": ["후속질문1", ...]
}"""
        else:
            return """당신은 팩트체커입니다. 주어진 증거를 바탕으로 주장을 **회의적인 관점**에서 분석하세요.

출력 형식 (반드시 JSON):
{
    "stance": "TRUE" | "FALSE" | "MIXED" | "UNVERIFIED",
    "confidence": 0.0 ~ 1.0,
    "reasoning_bullets": ["근거1", "근거2", ...],
    "citations": [
        {"evid_id": "ev_xxx", "quote": "인용문", "supports": false}
    ],
    "weak_points": ["약점1", ...],
    "followup_queries": ["후속질문1", ...]
}"""

    def _build_verify_user_prompt(
        self,
        claim_text: str,
        citations: List[Citation],
        language: str,
    ) -> str:
        """검증 사용자 프롬프트 생성."""
        # 증거 포맷팅
        if not citations:
            evidence_text = "(증거 없음)"
        else:
            evidence_lines = []
            for cit in citations:
                evidence_lines.append(cit.format_for_prompt())
                evidence_lines.append("")
            evidence_text = "\n".join(evidence_lines)

        return f"""## 검증할 주장
{claim_text}

## 수집된 증거
{evidence_text}

## 요청
위 증거를 바탕으로 분석하고, 지정된 JSON 형식으로 결과를 출력하세요.
언어: {language}
"""

    # ─────────────────────────────────────────────
    # Stage 1: Normalize Claim
    # ─────────────────────────────────────────────

    def normalize_claim(
        self,
        user_input: str,
        article_title: str = "",
        article_content: str = "",
        max_content_length: int = 1000,
    ) -> str:
        """
        주장 정규화 (Stage 1).

        사용자 입력과 기사 내용으로부터 핵심 주장 1문장을 추출합니다.

        Args:
            user_input: 사용자 입력 텍스트
            article_title: 기사 제목
            article_content: 기사 본문
            max_content_length: 본문 최대 길이

        Returns:
            정규화된 주장 문장
        """
        system_prompt = self._load_prompt("normalize")
        content_snippet = article_content[:max_content_length] if article_content else ""

        user_prompt = f"""[사용자 입력]: {user_input}
[기사 제목]: {article_title}
[기사 본문(일부)]: {content_snippet}

위 내용을 바탕으로 '검증해야 할 핵심 주장' 한 문장을 작성하라."""

        def operation():
            response = self._call_llm(system_prompt, user_prompt)
            # 응답 정제
            claim = response.strip().strip('"').strip("'")
            return claim if claim else user_input

        try:
            return self.execute(operation, "normalize_claim")
        except GatewayError as e:
            logger.warning(f"Normalize failed, using fallback: {e}")
            # Fallback: 기사 제목 > 사용자 입력
            if article_title:
                return article_title
            return user_input or "확인할 수 없는 주장"

    # ─────────────────────────────────────────────
    # Stage 2: Query Generation
    # ─────────────────────────────────────────────

    def generate_queries(
        self,
        claim_text: str,
        context: Optional[Dict[str, Any]] = None,
        max_content_length: int = 1500,
    ) -> Dict[str, Any]:
        """
        검색 쿼리 생성 (Stage 2).

        정규화된 주장으로부터 다각도 검색 쿼리를 생성합니다.

        Args:
            claim_text: 정규화된 주장
            context: canonical_evidence 컨텍스트
            max_content_length: 컨텍스트 본문 최대 길이

        Returns:
            {
                "core_fact": str,
                "query_variants": [{"type": str, "text": str}, ...],
                "keyword_bundles": {"primary": [...], "secondary": [...]},
                "search_constraints": {...}
            }
        """
        system_prompt = self._load_prompt("querygen")
        context = context or {}

        fetched_content = context.get("fetched_content", "")
        has_article = bool(fetched_content)

        if has_article:
            truncated = fetched_content[:max_content_length]
            context_str = json.dumps(
                {k: v for k, v in context.items() if k != "fetched_content"},
                ensure_ascii=False,
                default=str,
            )
            user_prompt = f"""Input User Text: "{claim_text}"
[첨부된 기사 내용 시작]
{truncated}
[첨부된 기사 내용 끝]

Context Hints: {context_str}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. 기사 내용이 있다면 기사의 핵심 주장을 최우선으로 반영하세요. `text` 필드는 절대 비워두면 안 됩니다."""
        else:
            context_str = json.dumps(context, ensure_ascii=False, default=str)
            user_prompt = f"""Input Text: "{claim_text}"
Context Hints: {context_str}

위 정보를 바탕으로 JSON 포맷의 출력을 생성하세요. `text` 필드는 절대 비워두면 안 됩니다."""

        def operation():
            response = self._call_llm(system_prompt, user_prompt)
            parsed = self._parse_json(response)
            return self._postprocess_queries(parsed, claim_text)

        try:
            return self.execute(operation, "generate_queries")
        except GatewayError as e:
            logger.warning(f"Query generation failed, using fallback: {e}")
            return self._generate_fallback_queries(claim_text)

    def _postprocess_queries(
        self,
        parsed: Dict[str, Any],
        claim_text: str,
    ) -> Dict[str, Any]:
        """LLM 출력 후처리: 빈 text 필드 보완, 기본 구조 보장."""
        core_fact = parsed.get("core_fact") or claim_text

        # query_variants 보완
        variants = parsed.get("query_variants", [])
        for q in variants:
            if not q.get("text"):
                qtype = q.get("type", "direct")
                if qtype == "verification":
                    q["text"] = f"{core_fact} 팩트체크"
                elif qtype == "news":
                    q["text"] = f"{core_fact} 뉴스"
                elif qtype == "contradictory":
                    q["text"] = f"{core_fact} 반박"
                else:
                    q["text"] = core_fact

        # 최소 1개 쿼리 보장
        if not variants:
            variants = [{"type": "direct", "text": core_fact}]

        return {
            "core_fact": core_fact,
            "query_variants": variants,
            "keyword_bundles": parsed.get("keyword_bundles", {"primary": [], "secondary": []}),
            "search_constraints": parsed.get("search_constraints", {}),
        }

    def _generate_fallback_queries(self, claim_text: str) -> Dict[str, Any]:
        """LLM 실패 시 규칙 기반 쿼리 생성."""
        words = claim_text.split()
        keywords = [w for w in words if len(w) > 1]

        variants = [
            {"type": "direct", "text": claim_text},
            {"type": "verification", "text": f"{claim_text} 팩트체크"},
            {"type": "news", "text": f"{claim_text} 뉴스"},
        ]

        return {
            "core_fact": claim_text,
            "query_variants": variants,
            "keyword_bundles": {
                "primary": keywords[:3],
                "secondary": keywords[3:6],
            },
            "search_constraints": {"note": "rule-based fallback"},
        }

    # ─────────────────────────────────────────────
    # Stage 9: Judge Verdict
    # ─────────────────────────────────────────────

    def judge_verdict(
        self,
        claim_text: str,
        draft_verdict: Dict[str, Any],
        evidence_topk: List[Dict[str, Any]],
        quality_score: int = 0,
        language: str = "ko",
    ) -> Dict[str, Any]:
        """
        최종 판정 및 사용자 친화적 결과 생성 (Stage 9).

        draft_verdict를 바탕으로 사용자가 이해하기 쉬운 최종 결과물을 생성합니다.

        Args:
            claim_text: 검증 대상 주장
            draft_verdict: Stage 8에서 생성된 초안 판정
            evidence_topk: 원본 증거 리스트 (출처 정보)
            quality_score: Stage 8에서 계산된 품질 점수
            language: 언어 코드

        Returns:
            {
                "verdict_label": "TRUE|FALSE|MIXED|UNVERIFIED",
                "verdict_korean": "사실입니다|거짓입니다|...",
                "confidence_percent": 85,
                "headline": "한 줄 요약",
                "explanation": "상세 설명",
                "evidence_summary": [{"point": "...", "source_title": "...", "source_url": "..."}],
                "cautions": ["주의사항"],
                "recommendation": "추가 확인 권장 사항"
            }
        """
        system_prompt = self._load_prompt("judge")
        user_prompt = self._build_judge_user_prompt(
            claim_text, draft_verdict, evidence_topk, quality_score, language
        )

        def operation():
            response = self._call_llm(system_prompt, user_prompt)
            parsed = self._parse_json(response)
            return self._postprocess_judge_result(parsed, draft_verdict, evidence_topk, quality_score)

        try:
            return self.execute(operation, "judge_verdict")
        except GatewayError as e:
            logger.warning(f"Judge failed, using fallback: {e}")
            return self._generate_fallback_judge(draft_verdict, evidence_topk, quality_score, str(e))

    def _build_judge_user_prompt(
        self,
        claim_text: str,
        draft_verdict: Dict[str, Any],
        evidence_topk: List[Dict[str, Any]],
        quality_score: int,
        language: str,
    ) -> str:
        """Judge 사용자 프롬프트 생성."""
        # draft_verdict 포맷팅
        verdict_str = json.dumps(draft_verdict, ensure_ascii=False, indent=2)

        # evidence 포맷팅 (간략화)
        evidence_lines = []
        for ev in evidence_topk[:5]:  # 최대 5개
            evid_id = ev.get("evid_id", "unknown")
            title = ev.get("title", "")
            snippet = (ev.get("snippet") or ev.get("content", ""))[:300]
            evidence_lines.append(f"[{evid_id}] {title}")
            evidence_lines.append(f"  내용: {snippet}")
            evidence_lines.append("")
        evidence_str = "\n".join(evidence_lines) if evidence_lines else "(증거 없음)"

        return f"""## 검증 대상 주장
{claim_text}

## 이전 단계 판정 결과 (draft_verdict)
{verdict_str}

## 원본 증거 (evidence_topk)
{evidence_str}

## 품질 점수 (Stage 8)
{quality_score}/100

## 요청
위 정보를 바탕으로 최종 판정을 평가하고, 지정된 JSON 형식으로 결과를 출력하세요.
언어: {language}
"""

    def _postprocess_judge_result(
        self,
        parsed: Dict[str, Any],
        draft_verdict: Dict[str, Any],
        evidence_topk: List[Dict[str, Any]],
        quality_score: int,
    ) -> Dict[str, Any]:
        """Judge 결과 후처리 - 품질 평가 + 사용자 친화적 형식 보장."""
        stance = draft_verdict.get("stance", "UNVERIFIED")
        confidence = draft_verdict.get("confidence", 0.0)
        citations_count = len(draft_verdict.get("citations", []))

        # evaluation 필드 추출 (LLM이 반환한 품질 평가)
        evaluation = parsed.get("evaluation", {})
        hallucination_count = evaluation.get("hallucination_count", 0)
        grounding_score = evaluation.get("grounding_score", 1.0)
        is_consistent = evaluation.get("is_consistent", True)
        policy_violations = evaluation.get("policy_violations", [])

        # verdict_korean 매핑
        verdict_korean_map = {
            "TRUE": "사실입니다",
            "FALSE": "거짓입니다",
            "MIXED": "일부 사실입니다",
            "UNVERIFIED": "확인이 어렵습니다",
        }

        # LLM 평가 기반 label 조정
        verdict_label = parsed.get("verdict_label", stance)

        # 품질 게이트 적용 (evaluation 결과 반영)
        if quality_score < 65 or citations_count == 0:
            verdict_label = "UNVERIFIED"
            confidence = 0.0
        elif hallucination_count >= 2 or grounding_score < 0.5:
            verdict_label = "UNVERIFIED"
            confidence = max(0.0, confidence * 0.5)
        elif not is_consistent:
            confidence = max(0.0, confidence * 0.7)

        confidence_percent = parsed.get("confidence_percent", int(confidence * 100))

        # risk_flags 결정 (LLM 결과 + 규칙 기반)
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

        # evidence_summary가 없으면 draft_verdict에서 생성
        evidence_summary = parsed.get("evidence_summary", [])
        if not evidence_summary:
            evidence_summary = self._build_evidence_summary(draft_verdict, evidence_topk)

        return {
            # 품질 평가 결과
            "evaluation": {
                "hallucination_count": hallucination_count,
                "grounding_score": grounding_score,
                "is_consistent": is_consistent,
                "policy_violations": policy_violations,
            },
            # 사용자 친화적 결과
            "verdict_label": verdict_label,
            "verdict_korean": parsed.get("verdict_korean", verdict_korean_map.get(verdict_label, "확인이 어렵습니다")),
            "confidence_percent": confidence_percent,
            "headline": parsed.get("headline", f"이 주장은 {confidence_percent}% 확률로 {verdict_korean_map.get(verdict_label, '확인이 어렵습니다')}"),
            "explanation": parsed.get("explanation", ""),
            "evidence_summary": evidence_summary,
            "cautions": parsed.get("cautions", draft_verdict.get("weak_points", [])),
            "recommendation": parsed.get("recommendation", ""),
            "risk_flags": risk_flags,
            # 내부용 메타데이터
            "_quality_score": quality_score,
            "_original_stance": stance,
            "_original_confidence": confidence,
        }

    def _build_evidence_summary(
        self,
        draft_verdict: Dict[str, Any],
        evidence_topk: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """draft_verdict에서 evidence_summary 생성."""
        evidence_map = {ev.get("evid_id", ""): ev for ev in evidence_topk}
        citations = draft_verdict.get("citations", [])
        reasoning = draft_verdict.get("reasoning_bullets", [])

        summary = []
        for i, cit in enumerate(citations[:3]):  # 최대 3개
            evid_id = cit.get("evid_id", "")
            source_ev = evidence_map.get(evid_id, {})

            # reasoning에서 해당 citation 관련 내용 찾기
            point = ""
            for r in reasoning:
                if evid_id in r or (i == 0 and not point):
                    # [시스템] 태그 제거
                    point = r.replace("[지지]", "").replace("[반박]", "").strip()
                    break

            if not point and cit.get("quote"):
                point = cit.get("quote", "")[:100]

            summary.append({
                "point": point or f"증거 {i+1}",
                "source_title": source_ev.get("title", cit.get("title", "")),
                "source_url": source_ev.get("url", cit.get("url", "")),
            })

        return summary

    def _generate_fallback_judge(
        self,
        draft_verdict: Dict[str, Any],
        evidence_topk: List[Dict[str, Any]],
        quality_score: int,
        error_msg: str,
    ) -> Dict[str, Any]:
        """Judge 실패 시 규칙 기반 fallback."""
        stance = draft_verdict.get("stance", "UNVERIFIED")
        confidence = draft_verdict.get("confidence", 0.0)
        citations_count = len(draft_verdict.get("citations", []))

        # 품질 게이트 적용
        if quality_score < 65 or citations_count == 0:
            stance = "UNVERIFIED"
            confidence = 0.0

        verdict_korean_map = {
            "TRUE": "사실입니다",
            "FALSE": "거짓입니다",
            "MIXED": "일부 사실입니다",
            "UNVERIFIED": "확인이 어렵습니다",
        }

        confidence_percent = int(confidence * 100)
        verdict_korean = verdict_korean_map.get(stance, "확인이 어렵습니다")

        # risk_flags 결정
        risk_flags = ["LLM_JUDGE_FAILED"]
        if quality_score < 65:
            risk_flags.append("QUALITY_GATE_FAILED")
        if citations_count < 2:
            risk_flags.append("LOW_EVIDENCE")

        return {
            # 품질 평가 (fallback - LLM 평가 없음)
            "evaluation": {
                "hallucination_count": -1,  # -1: 평가 불가
                "grounding_score": -1.0,
                "is_consistent": None,
                "policy_violations": [],
            },
            # 사용자 친화적 결과
            "verdict_label": stance,
            "verdict_korean": verdict_korean,
            "confidence_percent": confidence_percent,
            "headline": f"이 주장은 {confidence_percent}% 확률로 {verdict_korean}" if stance != "UNVERIFIED" else "이 주장은 현재 확인이 어렵습니다",
            "explanation": f"시스템 오류로 인해 자동 분석이 제한되었습니다. ({error_msg[:50]})",
            "evidence_summary": self._build_evidence_summary(draft_verdict, evidence_topk),
            "cautions": ["시스템 오류로 인해 분석이 제한됨", "수동 검토가 권장됨"],
            "recommendation": "이 결과는 자동 분석 시스템의 오류로 인해 제한적입니다. 직접 출처를 확인해 주세요.",
            "risk_flags": risk_flags,
            "_quality_score": quality_score,
            "_original_stance": stance,
            "_original_confidence": confidence,
        }

    # ─────────────────────────────────────────────
    # Prompt Loading (통합)
    # ─────────────────────────────────────────────

    @lru_cache(maxsize=8)
    def _load_prompt(self, prompt_type: str) -> str:
        """프롬프트 로드 (캐싱)."""
        prompt_dir = Path(__file__).parent / "prompts"

        prompt_files = {
            "normalize": "normalize.txt",
            "querygen": "querygen.txt",
            "supportive": "supportive.txt",
            "skeptical": "skeptical.txt",
            "judge": "judge.txt",
        }

        filename = prompt_files.get(prompt_type)
        if not filename:
            logger.warning(f"Unknown prompt type: {prompt_type}")
            return ""

        prompt_file = prompt_dir / filename
        if not prompt_file.exists():
            logger.warning(f"Prompt file not found: {prompt_file}")
            return self._get_default_prompt(prompt_type)

        return prompt_file.read_text(encoding="utf-8")

    def _get_default_prompt(self, prompt_type: str) -> str:
        """기본 프롬프트 반환."""
        defaults = {
            "normalize": "검증해야 할 핵심 주장을 한 문장으로 정리하세요.",
            "querygen": "검증용 검색 쿼리를 JSON 형식으로 생성하세요.",
            "supportive": self._get_default_verify_prompt("supportive"),
            "skeptical": self._get_default_verify_prompt("skeptical"),
        }
        return defaults.get(prompt_type, "")


# 전역 LLMGateway 인스턴스
_llm_gateway: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    """전역 LLMGateway 반환."""
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway
