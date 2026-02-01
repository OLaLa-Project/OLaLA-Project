"""
SLM Client for OpenAI-compatible API (Ollama, vLLM ??.

?섍꼍蹂??
    SLM_BASE_URL: SLM ?쒕쾭 二쇱냼 (default: http://localhost:8001/v1)
                  - ?몄뒪??Ollama (Docker?믫샇?ㅽ듃): http://host.docker.internal:11434/v1
                  - 濡쒖뺄 吏곸젒 ?ㅽ뻾: http://localhost:11434/v1
                  - vLLM: http://localhost:8001/v1
    SLM_API_KEY: API ??(default: local-slm-key, Ollama??"ollama")
    SLM_MODEL: 紐⑤뜽紐?(default: slm, Ollama ?? gemma3:4b)
    SLM_TIMEOUT_SECONDS: ??꾩븘??(default: 60)
    SLM_MAX_TOKENS: 理쒕? ?좏겙 (default: 768)
    SLM_TEMPERATURE: ?⑤룄 (default: 0.1)
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class SLMConfig:
    """SLM ?몄텧 ?ㅼ젙."""
    base_url: str
    api_key: str
    model: str
    timeout: int
    max_tokens: int
    temperature: float

    @classmethod
    def from_env(cls, prefix: str = "SLM") -> "SLMConfig":
        """?섍꼍蹂?섏뿉???ㅼ젙 濡쒕뱶."""
        key = (prefix or "SLM").upper()
        default_model = "slm"
        if key == "SLM1":
            default_model = "gemma3:4b"
        elif key == "SLM2":
            default_model = "Qwen3-4B"
        def _get(name: str, default: str) -> str:
            return os.getenv(f"{key}_{name}", default)
        return cls(
            base_url=_get("BASE_URL", "http://localhost:8001/v1"),
            api_key=_get("API_KEY", "local-slm-key"),
            model=_get("MODEL", default_model),
            timeout=int(_get("TIMEOUT_SECONDS", "60")),
            max_tokens=int(_get("MAX_TOKENS", "768")),
            temperature=float(_get("TEMPERATURE", "0.1")),
        )


class SLMClient:
    """OpenAI-compatible API ?대씪?댁뼵??(Ollama, vLLM ??."""

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
        Chat completion ?몄텧.

        Args:
            system_prompt: ?쒖뒪???꾨＼?꾪듃 (??븷 吏??
            user_prompt: ?ъ슜???꾨＼?꾪듃 (?ㅼ젣 ?쒖뒪??
            max_tokens: 理쒕? 異쒕젰 ?좏겙 (None?대㈃ config 媛??ъ슜)
            temperature: ?⑤룄 (None?대㈃ config 媛??ъ슜)

        Returns:
            紐⑤뜽 ?묐떟 ?띿뒪??

        Raises:
            SLMError: API ?몄텧 ?ㅽ뙣 ??
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

        logger.debug(f"SLM ?몄텧: model={self.config.model}, max_tokens={payload['max_tokens']}")

        def _post_json(post_url: str, post_payload: dict) -> requests.Response:
            return requests.post(
                post_url,
                headers=headers,
                json=post_payload,
                timeout=self.config.timeout,
            )

        try:
            response = _post_json(url, payload)
            if response.status_code == 404 and "/v1" in base:
                # Ollama 湲곕낯 ?붾뱶?ъ씤??fallback
                ollama_url = base.replace("/v1", "/api/generate")
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
            response.raise_for_status()
            data = response.json()
            if "choices" in data:
                content = data["choices"][0]["message"]["content"]
            else:
                content = data.get("response", "")
            logger.debug(f"SLM ?묐떟 湲몄씠: {len(content)} chars")
            return (content or "").strip()

        except requests.exceptions.Timeout:
            logger.error(f"SLM ??꾩븘?? {self.config.timeout}珥?珥덇낵")
            raise SLMError(f"SLM ?몄텧 ??꾩븘??({self.config.timeout}珥?")

        except requests.exceptions.RequestException as e:
            logger.error(f"SLM ?몄텧 ?ㅽ뙣: {e}")
            raise SLMError(f"SLM ?몄텧 ?ㅽ뙣: {e}")

        except (KeyError, IndexError) as e:
            logger.error(f"SLM ?묐떟 ?뚯떛 ?ㅽ뙣: {e}")
            raise SLMError(f"SLM ?묐떟 ?뺤떇 ?ㅻ쪟: {e}")


class SLMError(Exception):
    """SLM ?몄텧 愿???먮윭."""
    pass


# 紐⑤뱢 ?덈꺼 ?몄쓽 ?⑥닔
_default_clients: dict[str, SLMClient] = {}

def get_client(prefix: str = "SLM") -> SLMClient:
    """?깃????대씪?댁뼵??諛섑솚."""
    key = (prefix or "SLM").upper()
    client = _default_clients.get(key)
    if client is None:
        client = SLMClient(SLMConfig.from_env(prefix=key))
        _default_clients[key] = client
    return client


def call_slm(system_prompt: str, user_prompt: str, prefix: str = "SLM", **kwargs) -> str:
    """
    ?몄쓽 ?⑥닔: SLM ?몄텧.

    Args:
        system_prompt: ?쒖뒪???꾨＼?꾪듃
        user_prompt: ?ъ슜???꾨＼?꾪듃
        **kwargs: 異붽? ?듭뀡 (max_tokens, temperature)

    Returns:
        紐⑤뜽 ?묐떟 ?띿뒪??
    """
    return get_client(prefix=prefix).chat_completion(system_prompt, user_prompt, **kwargs)

def call_slm1(system_prompt: str, user_prompt: str, **kwargs) -> str:
    """SLM1 ?몄텧 (Stage 1~2)."""
    return call_slm(system_prompt, user_prompt, prefix="SLM1", **kwargs)

def call_slm2(system_prompt: str, user_prompt: str, **kwargs) -> str:
    """SLM2 ?몄텧 (Stage 6~7)."""
    return call_slm(system_prompt, user_prompt, prefix="SLM2", **kwargs)
