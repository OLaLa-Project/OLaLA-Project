"""
SLM Client for OpenAI-compatible API (vLLM, Ollama 등).

환경변수:
    SLM_BASE_URL: SLM 서버 주소 (default: http://localhost:8001/v1)
                  - Ollama: http://ollama:11434/v1
                  - vLLM: http://localhost:8001/v1
    SLM_API_KEY: API 키 (default: local-slm-key, Ollama는 "ollama")
    SLM_MODEL: 모델명 (default: slm, Ollama 예: llama3.2)
    SLM_TIMEOUT_SECONDS: 타임아웃 (default: 60)
    SLM_MAX_TOKENS: 최대 토큰 (default: 768)
    SLM_TEMPERATURE: 온도 (default: 0.1)
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class SLMConfig:
    """SLM 호출 설정."""
    base_url: str
    api_key: str
    model: str
    timeout: int
    max_tokens: int
    temperature: float

    @classmethod
    def from_env(cls) -> "SLMConfig":
        """환경변수에서 설정 로드."""
        return cls(
            base_url=os.getenv("SLM_BASE_URL", "http://localhost:8001/v1"),
            api_key=os.getenv("SLM_API_KEY", "local-slm-key"),
            model=os.getenv("SLM_MODEL", "slm"),
            timeout=int(os.getenv("SLM_TIMEOUT_SECONDS", "60")),
            max_tokens=int(os.getenv("SLM_MAX_TOKENS", "768")),
            temperature=float(os.getenv("SLM_TEMPERATURE", "0.1")),
        )


class SLMClient:
    """vLLM OpenAI-compatible API 클라이언트."""

    def __init__(self, config: Optional[SLMConfig] = None):
        self.config = config or SLMConfig.from_env()

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Chat completion 호출.

        Args:
            system_prompt: 시스템 프롬프트 (역할 지정)
            user_prompt: 사용자 프롬프트 (실제 태스크)
            max_tokens: 최대 출력 토큰 (None이면 config 값 사용)
            temperature: 온도 (None이면 config 값 사용)

        Returns:
            모델 응답 텍스트

        Raises:
            SLMError: API 호출 실패 시
        """
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
        }

        logger.debug(f"SLM 호출: model={self.config.model}, max_tokens={payload['max_tokens']}")

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.debug(f"SLM 응답 길이: {len(content)} chars")
            return content.strip()

        except requests.exceptions.Timeout:
            logger.error(f"SLM 타임아웃: {self.config.timeout}초 초과")
            raise SLMError(f"SLM 호출 타임아웃 ({self.config.timeout}초)")

        except requests.exceptions.RequestException as e:
            logger.error(f"SLM 호출 실패: {e}")
            raise SLMError(f"SLM 호출 실패: {e}")

        except (KeyError, IndexError) as e:
            logger.error(f"SLM 응답 파싱 실패: {e}")
            raise SLMError(f"SLM 응답 형식 오류: {e}")


class SLMError(Exception):
    """SLM 호출 관련 에러."""
    pass


# 모듈 레벨 편의 함수
_default_client: Optional[SLMClient] = None


def get_client() -> SLMClient:
    """싱글톤 클라이언트 반환."""
    global _default_client
    if _default_client is None:
        _default_client = SLMClient()
    return _default_client


def call_slm(system_prompt: str, user_prompt: str, **kwargs) -> str:
    """
    편의 함수: SLM 호출.

    Args:
        system_prompt: 시스템 프롬프트
        user_prompt: 사용자 프롬프트
        **kwargs: 추가 옵션 (max_tokens, temperature)

    Returns:
        모델 응답 텍스트
    """
    return get_client().chat_completion(system_prompt, user_prompt, **kwargs)
