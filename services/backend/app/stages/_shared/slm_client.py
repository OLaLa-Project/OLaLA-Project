"""
SLM Client for OpenAI-compatible API (Ollama, vLLM 등).

환경변수:
    SLM_BASE_URL: SLM 서버 주소 (default: http://localhost:8001/v1)
                  - 호스트 Ollama (Docker→호스트): http://host.docker.internal:11434/v1
                  - 로컬 직접 실행: http://localhost:11434/v1
                  - vLLM: http://localhost:8001/v1
    SLM_API_KEY: API 키 (default: local-slm-key, Ollama는 "ollama")
    SLM_MODEL: 모델명 (default: slm, Ollama 예: gemma3:4b)
    SLM_TIMEOUT_SECONDS: 타임아웃 (default: 60)
    SLM_MAX_TOKENS: 최대 토큰 (default: 768)
    SLM_TEMPERATURE: 온도 (default: 0.1)
"""

import logging
from typing import Optional
from dataclasses import dataclass

import requests
from app.core.settings import settings

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
    def from_settings(cls, prefix: str = "SLM") -> "SLMConfig":
        """중앙 Settings에서 설정 로드."""
        key = (prefix or "SLM").upper()
        if key == "SLM1":
            return cls(
                base_url=settings.slm1_base_url,
                api_key=settings.slm1_api_key,
                model=settings.slm1_model,
                timeout=settings.slm1_timeout_seconds,
                max_tokens=settings.slm1_max_tokens,
                temperature=settings.slm1_temperature,
            )
        if key == "SLM2":
            return cls(
                base_url=settings.slm2_base_url,
                api_key=settings.slm2_api_key,
                model=settings.slm2_model,
                timeout=settings.slm2_timeout_seconds,
                max_tokens=settings.slm2_max_tokens,
                temperature=settings.slm2_temperature,
            )
        return cls(
            base_url=settings.slm_base_url,
            api_key=settings.slm_api_key,
            model=settings.slm_model,
            timeout=settings.slm_timeout_seconds,
            max_tokens=settings.slm_max_tokens,
            temperature=settings.slm_temperature,
        )

    @classmethod
    def from_env(cls, prefix: str = "SLM") -> "SLMConfig":
        """호환성 유지를 위한 alias."""
        return cls.from_settings(prefix=prefix)


class SLMClient:
    """OpenAI-compatible API 클라이언트 (Ollama, vLLM 등)."""

    def __init__(self, config: Optional[SLMConfig] = None):
        self.config = config or SLMConfig.from_settings()

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
        base = self.config.base_url.rstrip("/")
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

        def _post_json(post_url: str, post_payload: dict) -> requests.Response:
            return requests.post(
                post_url,
                headers=headers,
                json=post_payload,
                timeout=self.config.timeout,
            )

        def _contains_model_not_found_message(response: requests.Response) -> bool:
            body = (response.text or "").lower()
            return "model" in body and "not found" in body

        def _chat_completion_urls(base_url: str) -> list[str]:
            candidates = [f"{base_url}/chat/completions"]
            if not base_url.endswith("/v1"):
                candidates.append(f"{base_url}/v1/chat/completions")
            dedup: list[str] = []
            for candidate in candidates:
                if candidate not in dedup:
                    dedup.append(candidate)
            return dedup

        def _native_ollama_urls(base_url: str) -> list[str]:
            if base_url.endswith("/v1"):
                root = base_url[:-3]
            else:
                root = base_url
            root = root.rstrip("/")
            return [f"{root}/api/chat", f"{root}/api/generate"]

        try:
            openai_like_payload = payload
            last_errors: list[str] = []

            for url in _chat_completion_urls(base):
                response = _post_json(url, openai_like_payload)
                if response.status_code == 404:
                    if _contains_model_not_found_message(response):
                        msg = f"모델 '{self.config.model}'이(가) 서버에 없습니다. (url={url})"
                        logger.error(msg)
                        raise SLMModelNotFoundError(msg)
                    last_errors.append(f"{url} -> 404")
                    continue
                response.raise_for_status()
                try:
                    data = response.json()
                except Exception as e:
                    logger.error("SLM API 응답 파싱 실패: %s", e)
                    logger.error("응답 본문: %s", response.text)
                    raise
                if "choices" in data:
                    content = data["choices"][0]["message"]["content"]
                    logger.debug("SLM 응답 길이: %d chars", len(content or ""))
                    return (content or "").strip()
                last_errors.append(f"{url} -> invalid_openai_response")

            # OpenAI-compatible 엔드포인트가 없는 서버(또는 /v1 미설정) 대응.
            for ollama_url in _native_ollama_urls(base):
                if ollama_url.endswith("/api/chat"):
                    ollama_payload = {
                        "model": self.config.model,
                        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                        "stream": False,
                        "options": {
                            "temperature": temperature if temperature is not None else self.config.temperature,
                            "num_predict": max_tokens or self.config.max_tokens,
                        },
                    }
                else:
                    ollama_payload = {
                        "model": self.config.model,
                        "prompt": user_prompt,
                        "system": system_prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature if temperature is not None else self.config.temperature,
                            "num_predict": max_tokens or self.config.max_tokens,
                        },
                    }

                response = _post_json(ollama_url, ollama_payload)
                if response.status_code == 404:
                    if _contains_model_not_found_message(response):
                        msg = f"모델 '{self.config.model}'이(가) 서버에 없습니다. (url={ollama_url})"
                        logger.error(msg)
                        raise SLMModelNotFoundError(msg)
                    last_errors.append(f"{ollama_url} -> 404")
                    continue
                response.raise_for_status()
                try:
                    data = response.json()
                except Exception as e:
                    logger.error("SLM API 응답 파싱 실패: %s", e)
                    logger.error("응답 본문: %s", response.text)
                    raise

                if ollama_url.endswith("/api/chat"):
                    message = data.get("message") if isinstance(data, dict) else None
                    content = message.get("content", "") if isinstance(message, dict) else ""
                else:
                    content = data.get("response", "") if isinstance(data, dict) else ""
                logger.debug("SLM 응답 길이: %d chars", len(content or ""))
                return (content or "").strip()

            detail = ", ".join(last_errors) if last_errors else "unknown"
            raise SLMError(
                f"SLM 엔드포인트를 찾지 못했습니다. base_url={base}, attempts=[{detail}]"
            )

        except requests.exceptions.Timeout:
            logger.error(f"SLM 타임아웃: {self.config.timeout}초 초과")
            raise SLMError(f"SLM 호출 타임아웃 ({self.config.timeout}초)")

        except requests.exceptions.RequestException as e:
            logger.error(f"SLM 호출 실패: {e}")
            raise SLMError(f"SLM 호출 실패: {e}")

        except (KeyError, IndexError) as e:
            logger.error(f"SLM 호출 실패: {e}")
            raise SLMError(f"SLM 호출 실패: {e}")


class SLMError(Exception):
    """SLM 호출 관련 예외."""
    pass


class SLMModelNotFoundError(SLMError):
    """요청한 모델이 서버에 없을 때 발생."""
    pass


# 모듈 레벨 편의 함수
_default_clients: dict[str, SLMClient] = {}

def get_client(prefix: str = "SLM") -> SLMClient:
    """싱글톤 클라이언트 반환."""
    key = (prefix or "SLM").upper()
    client = _default_clients.get(key)
    if client is None:
        client = SLMClient(SLMConfig.from_settings(prefix=key))
        _default_clients[key] = client
    return client


def call_slm(system_prompt: str, user_prompt: str, prefix: str = "SLM", **kwargs) -> str:
    """
    편의 함수: SLM 호출.

    Args:
        system_prompt: 시스템 프롬프트
        user_prompt: 사용자 프롬프트
        **kwargs: 추가 옵션 (max_tokens, temperature)

    Returns:
        모델 응답 텍스트
    """
    return get_client(prefix=prefix).chat_completion(system_prompt, user_prompt, **kwargs)

def call_slm1(system_prompt: str, user_prompt: str, **kwargs) -> str:
    """SLM1 호출 (Stage 1~2)."""
    return call_slm(system_prompt, user_prompt, prefix="SLM1", **kwargs)

def call_slm2(system_prompt: str, user_prompt: str, **kwargs) -> str:
    """SLM2 호출 (Stage 6~7)."""
    return call_slm(system_prompt, user_prompt, prefix="SLM2", **kwargs)
