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
import json
import time
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

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
    stream_enabled: bool
    stream_connect_timeout_seconds: float
    stream_read_timeout_seconds: float
    stream_hard_timeout_seconds: int

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
                stream_enabled=settings.slm_stream_enabled,
                stream_connect_timeout_seconds=settings.slm_stream_connect_timeout_seconds,
                stream_read_timeout_seconds=settings.slm_stream_read_timeout_seconds,
                stream_hard_timeout_seconds=settings.slm_stream_hard_timeout_seconds,
            )
        if key == "SLM2":
            return cls(
                base_url=settings.slm2_base_url,
                api_key=settings.slm2_api_key,
                model=settings.slm2_model,
                timeout=settings.slm2_timeout_seconds,
                max_tokens=settings.slm2_max_tokens,
                temperature=settings.slm2_temperature,
                stream_enabled=settings.slm_stream_enabled,
                stream_connect_timeout_seconds=settings.slm_stream_connect_timeout_seconds,
                stream_read_timeout_seconds=settings.slm_stream_read_timeout_seconds,
                stream_hard_timeout_seconds=settings.slm_stream_hard_timeout_seconds,
            )
        return cls(
            base_url=settings.slm_base_url,
            api_key=settings.slm_api_key,
            model=settings.slm_model,
            timeout=settings.slm_timeout_seconds,
            max_tokens=settings.slm_max_tokens,
            temperature=settings.slm_temperature,
            stream_enabled=settings.slm_stream_enabled,
            stream_connect_timeout_seconds=settings.slm_stream_connect_timeout_seconds,
            stream_read_timeout_seconds=settings.slm_stream_read_timeout_seconds,
            stream_hard_timeout_seconds=settings.slm_stream_hard_timeout_seconds,
        )

    @classmethod
    def from_env(cls, prefix: str = "SLM") -> "SLMConfig":
        """호환성 유지를 위한 alias."""
        return cls.from_settings(prefix=prefix)


class SLMClient:
    """OpenAI-compatible API 클라이언트 (Ollama, vLLM 등)."""

    def __init__(self, config: Optional[SLMConfig] = None):
        self.config = config or SLMConfig.from_settings()

    def _stream_timeout(self) -> tuple[float, float]:
        connect_timeout = max(0.1, float(self.config.stream_connect_timeout_seconds))
        read_timeout = max(0.1, float(self.config.stream_read_timeout_seconds))
        return connect_timeout, read_timeout

    def _stream_deadline(self) -> Optional[float]:
        hard_timeout = int(self.config.stream_hard_timeout_seconds or 0)
        if hard_timeout <= 0:
            return None
        return time.monotonic() + hard_timeout

    def _check_deadline(self, deadline: Optional[float]) -> None:
        if deadline is None:
            return
        if time.monotonic() > deadline:
            raise requests.exceptions.Timeout(
                f"SLM 스트리밍 hard timeout ({self.config.stream_hard_timeout_seconds}초)"
            )

    @staticmethod
    def _extract_non_stream_content(data: dict) -> str:
        if "choices" in data:
            choices = data.get("choices") or []
            if choices:
                choice0 = choices[0] or {}
                message = choice0.get("message") if isinstance(choice0, dict) else None
                if isinstance(message, dict):
                    return str(message.get("content", "") or "")
                return str(choice0.get("text", "") or "")
        return str(data.get("response", "") or "")

    def _consume_openai_stream(
        self,
        response: requests.Response,
        deadline: Optional[float],
    ) -> str:
        chunks: list[str] = []
        response.encoding = response.encoding or "utf-8"
        for raw_line in response.iter_lines(decode_unicode=False):
            self._check_deadline(deadline)
            if not raw_line:
                continue
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8", errors="replace").strip()
            else:
                line = str(raw_line).strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line:
                continue
            if line == "[DONE]":
                break
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            choices = data.get("choices") or []
            if not choices:
                continue
            choice0 = choices[0] or {}
            text_piece = ""
            if isinstance(choice0, dict):
                delta = choice0.get("delta")
                if isinstance(delta, dict):
                    text_piece = str(delta.get("content", "") or "")
                if not text_piece:
                    message = choice0.get("message")
                    if isinstance(message, dict):
                        text_piece = str(message.get("content", "") or "")
            if text_piece:
                chunks.append(text_piece)

            finish_reason = choice0.get("finish_reason") if isinstance(choice0, dict) else None
            if finish_reason:
                break
        return "".join(chunks).strip()

    def _consume_ollama_stream(
        self,
        response: requests.Response,
        deadline: Optional[float],
    ) -> str:
        chunks: list[str] = []
        response.encoding = response.encoding or "utf-8"
        for raw_line in response.iter_lines(decode_unicode=False):
            self._check_deadline(deadline)
            if not raw_line:
                continue
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8", errors="replace").strip()
            else:
                line = str(raw_line).strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            text_piece = str(data.get("response", "") or "")
            if not text_piece:
                message = data.get("message")
                if isinstance(message, dict):
                    text_piece = str(message.get("content", "") or "")
            if text_piece:
                chunks.append(text_piece)
            if data.get("done") is True:
                break
        return "".join(chunks).strip()

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
        url = f"{base}/chat/completions"
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

        logger.debug(
            f"SLM 호출: model={self.config.model}, max_tokens={payload['max_tokens']}, "
            f"stream_enabled={self.config.stream_enabled}"
        )

        def _post_json(
            post_url: str,
            post_payload: dict,
            *,
            timeout: float | tuple[float, float] | None = None,
            stream: bool = False,
        ) -> requests.Response:
            return requests.post(
                post_url,
                headers=headers,
                json=post_payload,
                timeout=self.config.timeout if timeout is None else timeout,
                stream=stream,
            )

        def _to_ollama_generate_url(base_url: str) -> str:
            source = str(base_url or "").strip().rstrip("/")
            if not source:
                return ""
            if source.endswith("/api/generate"):
                return source
            if source.endswith("/v1"):
                return f"{source[:-3]}/api/generate"
            return f"{source}/api/generate"

        def _resolve_ollama_urls() -> list[str]:
            urls: list[str] = []

            def _append(url: str) -> None:
                candidate = str(url or "").strip()
                if not candidate:
                    return
                if candidate not in urls:
                    urls.append(candidate)

            _append(_to_ollama_generate_url(base))
            _append(_to_ollama_generate_url(settings.ollama_url))

            for original in list(urls):
                try:
                    parsed = urlsplit(original)
                except Exception:
                    continue
                hostname = (parsed.hostname or "").strip().lower()
                if hostname == "ollama":
                    alias_host = "olala-ollama"
                elif hostname == "olala-ollama":
                    alias_host = "ollama"
                else:
                    continue
                auth = ""
                if parsed.username:
                    auth = parsed.username
                    if parsed.password:
                        auth += f":{parsed.password}"
                    auth += "@"
                netloc = f"{auth}{alias_host}"
                if parsed.port:
                    netloc += f":{parsed.port}"
                _append(urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)))

            return urls

        def _call_ollama(use_stream: bool) -> str:
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
            errors: list[str] = []

            for ollama_url in _resolve_ollama_urls():
                logger.warning("SLM fallback attempt: %s -> %s", url, ollama_url)

                if use_stream:
                    stream_payload = dict(ollama_payload)
                    stream_payload["stream"] = True
                    try:
                        with _post_json(
                            ollama_url,
                            stream_payload,
                            timeout=self._stream_timeout(),
                            stream=True,
                        ) as response:
                            response.raise_for_status()
                            streamed = self._consume_ollama_stream(response, self._stream_deadline())
                        if streamed:
                            logger.debug(f"SLM(ollama-stream) 응답 길이: {len(streamed)} chars")
                            return streamed
                        logger.warning("SLM(ollama-stream) 응답이 비어 non-stream으로 재시도합니다.")
                    except requests.exceptions.Timeout as e:
                        logger.warning(f"SLM(ollama-stream) 타임아웃, non-stream fallback: {e}")
                        errors.append(f"{ollama_url} (stream timeout): {e}")
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"SLM(ollama-stream) 호출 실패, non-stream fallback: {e}")
                        errors.append(f"{ollama_url} (stream request): {e}")

                try:
                    with _post_json(ollama_url, ollama_payload) as response:
                        response.raise_for_status()
                        data = response.json()
                    content = str(data.get("response", "") or "")
                    logger.debug(f"SLM(ollama) 응답 길이: {len(content)} chars")
                    return content.strip()
                except requests.exceptions.RequestException as e:
                    errors.append(f"{ollama_url}: {e}")

            raise requests.exceptions.RequestException("; ".join(errors) if errors else "ollama fallback url not available")

        try:
            if self.config.stream_enabled:
                stream_payload = dict(payload)
                stream_payload["stream"] = True
                try:
                    with _post_json(
                        url,
                        stream_payload,
                        timeout=self._stream_timeout(),
                        stream=True,
                    ) as response:
                        if response.status_code == 404:
                            return _call_ollama(use_stream=True)
                        response.raise_for_status()
                        streamed = self._consume_openai_stream(response, self._stream_deadline())
                    if streamed:
                        logger.debug(f"SLM(stream) 응답 길이: {len(streamed)} chars")
                        return streamed
                    logger.warning("SLM(stream) 응답이 비어 non-stream으로 재시도합니다.")
                except requests.exceptions.Timeout as e:
                    logger.warning(f"SLM(stream) 타임아웃, non-stream fallback: {e}")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"SLM(stream) 호출 실패, non-stream fallback: {e}")
                except (KeyError, IndexError, ValueError) as e:
                    logger.warning(f"SLM(stream) 파싱 실패, non-stream fallback: {e}")

            with _post_json(url, payload) as response:
                if response.status_code == 404:
                    return _call_ollama(use_stream=self.config.stream_enabled)
                response.raise_for_status()
                try:
                    data = response.json()
                except Exception as e:
                    logger.error(f"SLM API 응답 파싱 실패: {e}")
                    logger.error(f"응답 본문: {response.text}")
                    raise
            content = self._extract_non_stream_content(data)
            logger.debug(f"SLM 응답 길이: {len(content)} chars")
            return content.strip()

        except requests.exceptions.Timeout:
            try:
                return _call_ollama(use_stream=False)
            except requests.exceptions.RequestException:
                pass
            logger.error(
                "SLM 타임아웃: request_timeout=%ss, stream_read_timeout=%ss, stream_hard_timeout=%ss",
                self.config.timeout,
                self.config.stream_read_timeout_seconds,
                self.config.stream_hard_timeout_seconds,
            )
            raise SLMError(
                "SLM 호출 타임아웃 "
                f"(request={self.config.timeout}s, "
                f"stream_read={self.config.stream_read_timeout_seconds}s, "
                f"stream_hard={self.config.stream_hard_timeout_seconds}s)"
            )

        except requests.exceptions.RequestException as e:
            try:
                return _call_ollama(use_stream=self.config.stream_enabled)
            except requests.exceptions.RequestException as fallback_error:
                logger.error(f"SLM 호출 실패: {e}")
                raise SLMError(f"SLM 호출 실패: {e}; ollama fallback 실패: {fallback_error}")

        except (KeyError, IndexError) as e:
            logger.error(f"SLM 호출 실패: {e}")
            raise SLMError(f"SLM 호출 실패: {e}")


class SLMError(Exception):
    """SLM 호출 관련 예외."""
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
