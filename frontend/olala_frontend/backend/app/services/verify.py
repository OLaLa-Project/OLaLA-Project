import asyncio
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class VerificationService:
    _MAX_QUERY_LENGTH = 240
    _MAX_EVIDENCE_COUNT = 10
    _SAFE_VERDICTS = {"true", "false", "mixed", "unverified"}

    async def search(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        trimmed_query = (query or "").strip()
        if not trimmed_query:
            return []

        safe_limit = max(1, min(limit, self._MAX_EVIDENCE_COUNT))
        try:
            results = await asyncio.to_thread(
                self._duckduckgo_search_sync,
                trimmed_query,
                safe_limit,
            )
        except Exception:
            logger.exception("verify.search_failed")
            results = []

        if results:
            return results[:safe_limit]

        return [self._fallback_evidence(trimmed_query)]

    async def analyze(self, raw_input: str, mode: str = "text") -> dict[str, object]:
        cleaned_input = (raw_input or "").strip()
        if not cleaned_input:
            return self._empty_result()

        normalized_mode = self._normalize_mode(mode, cleaned_input)
        search_query = (
            cleaned_input[: self._MAX_QUERY_LENGTH]
            if normalized_mode == "url"
            else self._compact_query(cleaned_input)
        )
        evidence_cards = await self.search(
            search_query,
            limit=max(1, min(settings.verify_search_limit, self._MAX_EVIDENCE_COUNT)),
        )

        fallback = self._heuristic_analyze(cleaned_input, normalized_mode, evidence_cards)
        provider = "heuristic"

        should_try_openai = (
            settings.verify_provider.lower() in {"auto", "openai"}
            and bool(settings.openai_api_key.strip())
        )
        if should_try_openai:
            openai_result = await self._openai_analyze(cleaned_input, normalized_mode, evidence_cards)
            if openai_result is not None:
                fallback.update(openai_result)
                provider = "openai"
        elif settings.verify_provider.lower() == "openai":
            logger.warning("verify.openai_requested_without_key")

        fallback["evidence_cards"] = evidence_cards
        fallback["mode"] = normalized_mode
        fallback["provider"] = provider
        return fallback

    def _empty_result(self) -> dict[str, object]:
        return {
            "verdict": "unverified",
            "confidence": 0.0,
            "headline": "검증할 내용을 입력해 주세요.",
            "reason": "URL이나 문장을 입력하면 근거를 수집해 결과를 제공합니다.",
            "evidence_cards": [],
            "mode": "text",
            "provider": "heuristic",
        }

    def _normalize_mode(self, mode: str, raw_input: str) -> str:
        lowered = (mode or "").strip().lower()
        if lowered in {"url", "text"}:
            return lowered
        if raw_input.lower().startswith(("http://", "https://")):
            return "url"
        return "text"

    def _compact_query(self, raw_text: str) -> str:
        compact = " ".join(raw_text.strip().split())
        return compact[: self._MAX_QUERY_LENGTH]

    def _fallback_evidence(self, query: str) -> dict[str, object]:
        return {
            "title": "추가 검색이 필요합니다",
            "source": "OLaLA",
            "snippet": f"'{query[:80]}' 관련 신뢰 가능한 출처를 추가로 확인해 주세요.",
            "url": "",
            "score": 0.45,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "stance": "neutral",
        }

    def _duckduckgo_search_sync(self, query: str, limit: int) -> list[dict[str, object]]:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
            },
        )
        endpoint = settings.verify_search_api_url.rstrip("/")
        url = f"{endpoint}/?{params}"
        request = urllib.request.Request(
            url=url,
            headers={
                "Accept": "application/json",
                "User-Agent": "OLaLA-Verify/1.0",
            },
        )

        payload: dict[str, Any]
        try:
            with urllib.request.urlopen(
                request,
                timeout=settings.verify_request_timeout_seconds,
            ) as response:
                decoded = response.read().decode("utf-8", errors="ignore")
                payload = json.loads(decoded)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            return []
        except json.JSONDecodeError:
            return []

        entries: list[dict[str, object]] = []

        abstract_text = str(payload.get("AbstractText") or "").strip()
        abstract_url = str(payload.get("AbstractURL") or "").strip()
        heading = str(payload.get("Heading") or query).strip()
        if abstract_text and abstract_url:
            entries.append(
                {
                    "title": heading or "검색 결과",
                    "source": self._extract_source(abstract_url),
                    "snippet": abstract_text,
                    "url": abstract_url,
                    "score": 0.73,
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "stance": "neutral",
                },
            )

        for topic in self._flatten_related_topics(payload.get("RelatedTopics")):
            text = str(topic.get("Text") or "").strip()
            first_url = str(topic.get("FirstURL") or "").strip()
            if not text or not first_url:
                continue
            title, snippet = self._split_topic_text(text)
            entries.append(
                {
                    "title": title,
                    "source": self._extract_source(first_url),
                    "snippet": snippet,
                    "url": first_url,
                    "score": 0.64,
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "stance": "neutral",
                },
            )
            if len(entries) >= limit:
                break

        deduped: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in entries:
            key = str(item.get("url") or item.get("title") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= limit:
                break

        return deduped

    def _flatten_related_topics(self, related_topics: Any) -> list[dict[str, Any]]:
        flattened: list[dict[str, Any]] = []
        if not isinstance(related_topics, list):
            return flattened

        for item in related_topics:
            if not isinstance(item, dict):
                continue
            if "Topics" in item and isinstance(item["Topics"], list):
                flattened.extend(self._flatten_related_topics(item["Topics"]))
                continue
            flattened.append(item)
        return flattened

    def _split_topic_text(self, text: str) -> tuple[str, str]:
        if " - " in text:
            title, snippet = text.split(" - ", 1)
            return title.strip(), snippet.strip()
        return text.strip(), text.strip()

    def _extract_source(self, url: str) -> str:
        host = urllib.parse.urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"

    async def _openai_analyze(
        self,
        raw_input: str,
        mode: str,
        evidence_cards: list[dict[str, object]],
    ) -> dict[str, object] | None:
        try:
            response_json = await asyncio.to_thread(
                self._openai_analyze_sync,
                raw_input,
                mode,
                evidence_cards,
            )
        except Exception:
            logger.exception("verify.openai_request_failed")
            return None

        return self._parse_openai_output(response_json)

    def _openai_analyze_sync(
        self,
        raw_input: str,
        mode: str,
        evidence_cards: list[dict[str, object]],
    ) -> dict[str, Any]:
        system_prompt = (
            "You are a Korean fact-check assistant. "
            "Use the provided user claim and evidence snippets only. "
            "Return strict JSON with keys: verdict, confidence, headline, reason. "
            "verdict must be one of true,false,mixed,unverified. "
            "confidence must be between 0 and 1."
        )
        evidence_text = "\n".join(
            [
                (
                    f"- title: {item.get('title', '')}\n"
                    f"  source: {item.get('source', '')}\n"
                    f"  snippet: {item.get('snippet', '')}\n"
                    f"  url: {item.get('url', '')}"
                )
                for item in evidence_cards[:5]
            ],
        )
        user_prompt = (
            f"mode: {mode}\n"
            f"input: {raw_input}\n\n"
            f"evidence:\n{evidence_text}\n\n"
            "Output language must be Korean."
        )

        payload = {
            "model": settings.openai_verify_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        endpoint = settings.openai_base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.openai_api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(
            request,
            timeout=settings.verify_request_timeout_seconds,
        ) as response:
            decoded = response.read().decode("utf-8", errors="ignore")
            return json.loads(decoded)

    def _parse_openai_output(self, response_json: dict[str, Any]) -> dict[str, object] | None:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        message = choices[0].get("message")
        if not isinstance(message, dict):
            return None

        content = message.get("content", "")
        raw_text = self._normalize_message_content(content)
        if not raw_text:
            return None

        parsed = self._extract_json_map(raw_text)
        if parsed is None:
            return None

        verdict = str(parsed.get("verdict") or "unverified").strip().lower()
        if verdict not in self._SAFE_VERDICTS:
            verdict = "unverified"

        confidence = self._safe_confidence(parsed.get("confidence"), default=0.5)
        headline = str(parsed.get("headline") or "").strip()
        reason = str(parsed.get("reason") or "").strip()

        if not headline:
            headline = self._headline_for_verdict(verdict)
        if not reason:
            reason = "근거를 바탕으로 결과를 정리했어요. 제공된 링크를 직접 확인해 주세요."

        return {
            "verdict": verdict,
            "confidence": confidence,
            "headline": headline[:120],
            "reason": reason[:500],
        }

    def _normalize_message_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    maybe_text = item.get("text")
                    if isinstance(maybe_text, str):
                        text_parts.append(maybe_text)
            return "\n".join(text_parts).strip()
        return ""

    def _extract_json_map(self, raw_text: str) -> dict[str, Any] | None:
        try:
            direct = json.loads(raw_text)
            if isinstance(direct, dict):
                return direct
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return None
        try:
            recovered = json.loads(match.group(0))
            if isinstance(recovered, dict):
                return recovered
        except json.JSONDecodeError:
            return None
        return None

    def _safe_confidence(self, value: Any, default: float) -> float:
        candidate: float
        if isinstance(value, (int, float)):
            candidate = float(value)
        else:
            try:
                candidate = float(str(value))
            except (TypeError, ValueError):
                candidate = default

        if candidate > 1:
            candidate = candidate / 100.0
        return max(0.0, min(candidate, 1.0))

    def _heuristic_analyze(
        self,
        raw_input: str,
        mode: str,
        evidence_cards: list[dict[str, object]],
    ) -> dict[str, object]:
        lowered = raw_input.lower()
        evidence_count = len(evidence_cards)
        trusted_domains = ("korea.kr", "go.kr", "who.int", "un.org", "gov")
        risky_keywords = ("단독", "충격", "무조건", "100%", "익명", "카더라", "rumor")

        if mode == "url" and any(token in lowered for token in trusted_domains):
            verdict = "true"
            confidence = 0.81
            reason = "공식 기관 또는 공신력 높은 도메인이 포함되어 있어요. 최신성/원문 일치 여부는 추가 확인해 주세요."
        elif any(keyword in lowered for keyword in risky_keywords):
            verdict = "false"
            confidence = 0.32
            reason = "자극적 표현이나 불명확한 출처 단서가 있어요. 공식 발표/원문 기사와 교차 검증이 필요합니다."
        elif evidence_count >= 3:
            verdict = "mixed"
            confidence = 0.56
            reason = "상반된 관점의 단서가 함께 보입니다. 핵심 주장과 날짜, 출처를 기준으로 추가 확인해 주세요."
        else:
            verdict = "unverified"
            confidence = 0.44
            reason = "지금 정보만으로는 결론을 내리기 어렵습니다. 추가 검색 결과를 열어 원문을 비교해 주세요."

        return {
            "verdict": verdict,
            "confidence": confidence,
            "headline": self._headline_for_verdict(verdict),
            "reason": reason,
        }

    def _headline_for_verdict(self, verdict: str) -> str:
        if verdict == "true":
            return "대체로 사실에 가까워요"
        if verdict == "false":
            return "주의가 필요한 주장입니다"
        if verdict == "mixed":
            return "일부는 사실, 일부는 추가 검증이 필요해요"
        return "추가 검증이 필요해요"


verification_service = VerificationService()
