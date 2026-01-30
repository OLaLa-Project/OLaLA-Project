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

    @lru_cache(maxsize=4)
    def _load_verify_prompt(self, perspective: str) -> str:
        """검증 프롬프트 로드 (캐싱)."""
        # 프롬프트 파일 경로
        prompt_dir = Path(__file__).parent / "prompts"

        if perspective == "supportive":
            prompt_file = prompt_dir / "supportive.txt"
        elif perspective == "skeptical":
            prompt_file = prompt_dir / "skeptical.txt"
        else:
            prompt_file = prompt_dir / "supportive.txt"

        # 파일이 없으면 기본 프롬프트 반환
        if not prompt_file.exists():
            return self._get_default_verify_prompt(perspective)

        return prompt_file.read_text(encoding="utf-8")

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


# 전역 LLMGateway 인스턴스
_llm_gateway: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    """전역 LLMGateway 반환."""
    global _llm_gateway
    if _llm_gateway is None:
        _llm_gateway = LLMGateway()
    return _llm_gateway
