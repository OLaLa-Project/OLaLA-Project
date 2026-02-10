"""Stage 3 - Collect Evidence (Wiki + Naver + DDG Parallel)."""

import asyncio
import difflib
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from app.core.async_utils import run_async_in_sync
from app.core.observability import record_external_api_result
from app.core.settings import settings
from app.db.session import SessionLocal
from app.stages._shared.html_signals import analyze_html_signals
from app.stages._shared.source_trust import build_source_trust
from app.services.wiki_retriever import retrieve_wiki_hits

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


logger = logging.getLogger(__name__)

_SOURCE_PRIOR = {
    "WIKIPEDIA": 0.78,
    "KNOWLEDGE_BASE": 0.78,
    "KB_DOC": 0.78,
    "NEWS": 0.58,
    "WEB_URL": 0.44,
    "WEB": 0.44,
}
_INTENT_BONUS = {
    "official_statement": 0.08,
    "fact_check": 0.08,
    "origin_trace": 0.06,
    "entity_profile": 0.03,
}
_TRACKING_QUERY_PREFIXES = (
    "utm_",
    "fbclid",
    "gclid",
    "mkt_tok",
    "igshid",
    "ref",
)
_LOW_QUALITY_WEB_DOMAINS = {
    "airbnb.com",
    "ask.com",
    "baidu.com",
    "blogspot.com",
    "dic.daum.net",
    "kin.naver.com",
    "namu.wiki",
    "play.google.com",
    "apps.apple.com",
    "quora.com",
    "reddit.com",
    "youtube.com",
    "youtu.be",
    "wiktionary.org",
    "wordrow.kr",
    "zhihu.com",
    "stackexchange.com",
    "stackoverflow.com",
}
_LOW_QUALITY_TITLE_PATTERNS = (
    re.compile(r"(사전|뜻|의미|dictionary|번역|단어\s*뜻)", re.IGNORECASE),
    re.compile(r"(도움말|help|faq|q\s*&\s*a|질문.?답변|사용법|how\s*to)", re.IGNORECASE),
    re.compile(r"(예시|sample|template|서식)", re.IGNORECASE),
)
_CJK_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff]")
_HANGUL_CHAR_PATTERN = re.compile(r"[가-힣]")
_ALLOWED_STANCES = {"support", "skeptic", "neutral"}


def _api_timeout_seconds() -> float:
    return max(1.0, float(settings.external_api_timeout_seconds))


def _api_retry_attempts() -> int:
    return max(1, int(settings.external_api_retry_attempts))


def _api_backoff_seconds() -> float:
    return float(max(0.05, float(settings.external_api_backoff_seconds)))


def _stage3_ddg_max_results() -> int:
    return max(10, int(settings.stage3_ddg_max_results))


def _stage3_global_cap() -> int:
    return max(1, int(settings.stage3_global_candidate_cap))


def _stage3_source_caps() -> dict[str, int]:
    return {
        "news": max(0, int(settings.stage3_source_cap_news)),
        "wiki": max(0, int(settings.stage3_source_cap_wiki)),
        "web": max(0, int(settings.stage3_source_cap_web)),
    }


def _backoff_delay(attempt: int) -> float:
    # Exponential backoff with cap to avoid runaway wait.
    return float(min(5.0, _api_backoff_seconds() * (2**attempt)))


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_keywords(text: str, max_terms: int = 16) -> list[str]:
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", text.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= max_terms:
            break
    return keywords


def _keyword_overlap_ratio(text: str, keywords: list[str]) -> float:
    source = (text or "").lower()
    if not source or not keywords:
        return 0.0
    hits = sum(1 for keyword in keywords if keyword in source)
    return hits / max(1, len(keywords))


def _parse_datetime_maybe(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = parsedate_to_datetime(text)
        except Exception:
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except Exception:
                return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _freshness_bonus(metadata: dict[str, Any]) -> float:
    dt = _parse_datetime_maybe(metadata.get("pub_date"))
    if dt is None:
        return 0.0
    age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    if age_days < 0:
        age_days = 0.0
    if age_days <= 3:
        return 0.08
    if age_days <= 14:
        return 0.05
    if age_days <= 60:
        return 0.02
    return 0.0


def _normalize_mode(value: Any) -> str:
    raw = str(value or "fact").strip().lower()
    if raw in {"fact", "rumor", "mixed"}:
        return raw
    if "rumor" in raw and "fact" in raw:
        return "mixed"
    if "rumor" in raw:
        return "rumor"
    return "fact"


def _normalize_stance(value: Any) -> str:
    stance = str(value or "").strip().lower()
    if stance in _ALLOWED_STANCES:
        return stance
    return "neutral"


def _normalize_query_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        dumped = item.model_dump()
        return dumped if isinstance(dumped, dict) else None
    if hasattr(item, "dict"):
        dumped = item.dict()
        return dumped if isinstance(dumped, dict) else None
    if hasattr(item, "to_dict"):
        dumped = item.to_dict()
        return dumped if isinstance(dumped, dict) else None
    if isinstance(item, str):
        return {"type": "direct", "text": item}
    return None


def _query_context(item: dict[str, Any]) -> dict[str, Any]:
    raw_meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    return {
        "query_text": _clean_text(item.get("text")),
        "query_type": str(item.get("type") or "direct").strip().lower() or "direct",
        "claim_id": str(raw_meta.get("claim_id") or "").strip(),
        "intent": str(raw_meta.get("intent") or "").strip().lower(),
        "mode": _normalize_mode(raw_meta.get("mode")),
        "stance": _normalize_stance(raw_meta.get("stance")),
    }


def _merge_metadata(base: dict[str, Any], query_meta: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged["query_text"] = query_meta.get("query_text", "")
    merged["query_type"] = query_meta.get("query_type", "direct")
    merged["claim_id"] = query_meta.get("claim_id", "")
    merged["intent"] = query_meta.get("intent", "")
    merged["mode"] = _normalize_mode(query_meta.get("mode"))
    merged["stance"] = _normalize_stance(query_meta.get("stance"))
    return merged


async def _safe_execute(coro, timeout=10.0, name="Task"):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("Task Timeout (%ss): %s", timeout, name)
        return []
    except Exception as e:
        logger.error("Task Error (%s): %s", name, e)
        return []


async def _safe_execute_with_context(coro, query_meta: dict[str, Any], timeout=10.0, name="Task") -> list[dict[str, Any]]:
    results = await _safe_execute(coro, timeout=timeout, name=name)
    enriched: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        item["metadata"] = _merge_metadata(metadata, query_meta)
        enriched.append(item)
    return enriched


async def _search_wiki(query: str, search_mode: str) -> dict[str, Any]:
    """Execute Wiki Search and propagate retriever debug info."""
    results: list[dict[str, Any]] = []
    debug: dict[str, Any] = {}
    result_cap = max(1, int(settings.stage3_wiki_result_cap))
    try:
        def _sync_wiki_task():
            with SessionLocal() as db:
                return retrieve_wiki_hits(
                    db=db,
                    question=query,
                    top_k=result_cap,
                    window=2,
                    page_limit=result_cap,
                    embed_missing=True,
                    search_mode=search_mode,
                )

        hits_data = await asyncio.to_thread(_sync_wiki_task)
        if isinstance(hits_data, dict):
            raw_debug = hits_data.get("debug")
            if isinstance(raw_debug, dict):
                debug = dict(raw_debug)

        for h in hits_data.get("hits", []) if isinstance(hits_data, dict) else []:
            if not isinstance(h, dict):
                continue
            results.append(
                {
                    "source_type": "WIKIPEDIA",
                    "title": h.get("title", ""),
                    "url": f"wiki://page/{h.get('page_id')}",
                    "content": h.get("content", ""),
                    "metadata": {
                        "page_id": h.get("page_id"),
                        "chunk_id": h.get("chunk_id"),
                        "dist": h.get("dist"),
                        "lex_score": h.get("lex_score"),
                        "search_query": query,
                    },
                }
            )
    except Exception as e:
        debug["embed_error"] = str(e)
        logger.error("Wiki Search Failed for '%s': %s", query, e)
    return {"items": results, "debug": debug}


async def _search_naver(
    query: str,
    limiter: asyncio.Semaphore | None = None,
) -> List[Dict[str, Any]]:
    """Execute Naver Search (News)."""
    results = []
    client_id = settings.naver_client_id.strip()
    client_secret = settings.naver_client_secret.strip()

    if not client_id or not client_secret:
        logger.warning("Naver API credentials missing. Skipping.")
        return []

    safe_query = (query or "").strip()
    if len(safe_query) > 100:
        safe_query = safe_query[:100]
    logger.info("Naver query=%s", safe_query)

    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params: Dict[str, str | int] = {"query": safe_query, "display": 10, "sort": "sim"}
    request_timeout = _api_timeout_seconds()
    max_attempts = _api_retry_attempts()
    sem = limiter or asyncio.Semaphore(max(1, int(settings.naver_max_concurrency)))

    for attempt in range(max_attempts):
        try:
            async with sem:
                resp = await asyncio.to_thread(
                    requests.get,
                    url,
                    headers=headers,
                    params=params,
                    timeout=request_timeout,
                )
            logger.info("Naver status=%s attempt=%d", resp.status_code, attempt + 1)

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    logger.warning("Naver returned 0 items for query='%s'", safe_query)
                for item in items:
                    title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')
                    desc = item["description"].replace("<b>", "").replace("</b>", "").replace("&quot;", '"')

                    results.append(
                        {
                            "source_type": "NEWS",
                            "title": title,
                            "url": item["link"],
                            "content": desc,
                            "metadata": {"origin": "naver", "pub_date": item.get("pubDate")},
                        }
                    )
                record_external_api_result("naver", ok=True)
                return results

            if _is_retryable_status(resp.status_code) and attempt < max_attempts - 1:
                delay = _backoff_delay(attempt)
                logger.warning(
                    "Naver retryable status=%s query='%s' retry_in=%.2fs",
                    resp.status_code,
                    safe_query,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            logger.error("Naver API Error: %s %s", resp.status_code, resp.text[:200])
            record_external_api_result("naver", ok=False)
            return []
        except (requests.Timeout, requests.RequestException, asyncio.TimeoutError) as e:
            if attempt < max_attempts - 1:
                delay = _backoff_delay(attempt)
                logger.warning(
                    "Naver request failed query='%s' attempt=%d/%d retry_in=%.2fs err=%s",
                    safe_query,
                    attempt + 1,
                    max_attempts,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)
                continue
            logger.error("Naver Search Failed for '%s': %s", query, e)
            record_external_api_result("naver", ok=False)
            return []
        except Exception as e:
            logger.error("Naver Search Failed for '%s': %s", query, e)
            record_external_api_result("naver", ok=False)
            return []

    record_external_api_result("naver", ok=False)
    return []


async def _search_duckduckgo(
    query: str,
    limiter: asyncio.Semaphore | None = None,
) -> List[Dict[str, Any]]:
    """Execute DuckDuckGo Search."""
    results = []
    safe_query = (query or "").strip()
    logger.info("DDG query=%s", safe_query)

    max_attempts = _api_retry_attempts()
    request_timeout = _api_timeout_seconds()
    sem = limiter or asyncio.Semaphore(max(1, int(settings.ddg_max_concurrency)))

    for attempt in range(max_attempts):
        try:
            def _sync_ddg():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=_stage3_ddg_max_results()))

            async with sem:
                ddg_results = await asyncio.wait_for(
                    asyncio.to_thread(_sync_ddg),
                    timeout=request_timeout,
                )

            logger.info("DDG results=%d attempt=%d", len(ddg_results), attempt + 1)

            for r in ddg_results:
                results.append(
                    {
                        "source_type": "WEB_URL",
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "content": r.get("body", ""),
                        "metadata": {"origin": "duckduckgo"},
                    }
                )
            record_external_api_result("ddg", ok=True)
            return results
        except Exception as e:
            msg = str(e).lower()
            retryable = ("429" in msg) or ("rate" in msg) or isinstance(e, asyncio.TimeoutError)
            if retryable and attempt < max_attempts - 1:
                delay = _backoff_delay(attempt)
                logger.warning(
                    "DDG retryable failure query='%s' attempt=%d/%d retry_in=%.2fs err=%s",
                    safe_query,
                    attempt + 1,
                    max_attempts,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)
                continue
            logger.error("DuckDuckGo Search Failed for '%s': %s", query, e)
            record_external_api_result("ddg", ok=False)
            return []

    record_external_api_result("ddg", ok=False)
    return []


def _extract_queries(state: dict) -> list[dict[str, Any]]:
    raw_queries = state.get("search_queries", [])
    if raw_queries:
        search_queries = [q for q in (_normalize_query_item(i) for i in raw_queries) if q]
    else:
        raw_variants = state.get("query_variants", [])
        search_queries = [q for q in (_normalize_query_item(i) for i in raw_variants) if q]
        if not search_queries:
            fallback = state.get("claim_text") or state.get("input_payload")
            if fallback:
                search_queries = [{"type": "direct", "text": fallback}]

    logger.info("[Extract Queries] Found %d queries", len(search_queries))
    return search_queries


def _normalize_query_key(text: str) -> str:
    compact = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", compact)


def _clip_query_text(text: str, *, max_chars: int = 50) -> str:
    cleaned = _clean_text(text)
    max_chars = max(20, int(max_chars))
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].strip()


def _is_blocked_domain(domain: str) -> bool:
    normalized = str(domain or "").strip().lower()
    if normalized.startswith("www."):
        normalized = normalized[4:]
    if not normalized:
        return False
    return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in _LOW_QUALITY_WEB_DOMAINS)


def _is_low_quality_title(title: str) -> bool:
    cleaned = _clean_text(title)
    if not cleaned:
        return False
    return any(pattern.search(cleaned) is not None for pattern in _LOW_QUALITY_TITLE_PATTERNS)


def _is_blocked_language(title: str, content: str) -> bool:
    text = f"{_clean_text(title)} {_clean_text(content)}".strip()
    if not text:
        return False
    cjk_count = len(_CJK_CHAR_PATTERN.findall(text))
    if cjk_count < 6:
        return False
    return _HANGUL_CHAR_PATTERN.search(text) is None


def _web_filter_reason(item: dict[str, Any]) -> str | None:
    source_type = str(item.get("source_type") or "").upper()
    if source_type not in {"WEB_URL", "WEB"}:
        return None
    url = _clean_text(item.get("url"))
    domain = _domain_from_url(url)
    if _is_blocked_domain(domain):
        return "domain"
    if _is_low_quality_title(item.get("title", "")):
        return "pattern"
    if _is_blocked_language(item.get("title", ""), item.get("content", "")):
        return "language"
    return None


def _prepare_web_queries(search_queries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    original_count = 0

    for query in search_queries:
        qtype = str(query.get("type", "direct")).strip().lower() or "direct"
        if qtype not in {"news", "web", "verification", "direct"}:
            continue

        original_text = _clean_text(query.get("text", ""))
        if not original_text:
            continue
        original_count += 1

        clipped_text = _clip_query_text(
            original_text,
            max_chars=max(20, int(settings.stage3_web_query_max_chars)),
        )
        key = _normalize_query_key(clipped_text)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)

        cloned = dict(query)
        cloned["type"] = qtype
        cloned["text"] = clipped_text
        prepared.append(cloned)

    avg_query_len = round(sum(len(str(item.get("text") or "")) for item in prepared) / len(prepared), 2) if prepared else 0.0
    diagnostics = {
        "web_query_count": original_count,
        "web_query_deduped_count": len(prepared),
        "avg_query_len": avg_query_len,
        "queries_used": [_query_context(item) for item in prepared],
    }
    return prepared, diagnostics


def _normalize_wiki_query(text: str) -> List[str]:
    """
    위키 쿼리 정규화: LLM이 생성한 표제어를 정제.
    """
    if not text:
        return []

    parts = re.split(r"\s*[,&]\s*", text)
    terms = []
    for token in parts:
        token = token.strip()
        if not token:
            continue
        token = re.sub(r"(의|에|를|을|이|가|은|는|와|과|로|으로)$", "", token)
        if token:
            terms.append(token)

    return terms if terms else [text.strip()]


async def run_wiki_async(state: dict) -> dict:
    """Execute Only Wiki Search (async)."""
    search_queries = _extract_queries(state)
    vector_only = bool(settings.stage3_wiki_strict_vector_only)
    default_mode = str(state.get("search_mode", "lexical") or "lexical")

    # 1. Select the best single query for Vector Search
    best_query_text = ""
    best_query_meta = {}
    best_search_mode = "vector" if vector_only else default_mode

    # Strict mode: only wiki query is allowed for Stage3 wiki retrieval.
    candidate_queries = [q for q in search_queries if str(q.get("type", "")).strip().lower() == "wiki"]
    
    if candidate_queries:
        # Use the first valid candidate
        target = candidate_queries[0]
        best_query_text = _clean_text(target.get("text", ""))
        best_query_meta = _query_context(target)
        if not vector_only:
            best_search_mode = str(target.get("search_mode", default_mode) or default_mode)

    diagnostics = {
        "wiki_query_used": best_query_text,
        "wiki_search_mode_used": best_search_mode,
        "vector_only": vector_only,
        "wiki_result_cap": max(1, int(settings.stage3_wiki_result_cap)),
        "wiki_query_count": len(candidate_queries),
        "embed_error": None,
        "candidates_count": 0,
        "query_used_normalized": "",
        "vector_db_calls": 0,
        "direct_vector_fastpath": False,
    }

    if not best_query_text:
        logger.info("Stage 3 (Wiki) skipped: no wiki query")
        diagnostics["wiki_result_count"] = 0
        return {"wiki_candidates": [], "stage03_wiki_diagnostics": diagnostics}

    # 2. Execute ONE search if we have a query
    logger.info("Executing Single Wiki Vector Search: '%s'", best_query_text)

    # Ensure meta defines it as wiki
    if not best_query_meta.get("query_type"):
        best_query_meta["query_type"] = "wiki"

    search_result = await _safe_execute(
        _search_wiki(best_query_text, best_search_mode),
        timeout=600.0,
        name=f"Wiki-Vector:{best_query_text[:20]}",
    )

    wiki_debug: dict[str, Any] = {}
    raw_items: list[dict[str, Any]] = []
    if isinstance(search_result, dict):
        raw_debug = search_result.get("debug")
        if isinstance(raw_debug, dict):
            wiki_debug = dict(raw_debug)
        items = search_result.get("items")
        if isinstance(items, list):
            raw_items = [item for item in items if isinstance(item, dict)]
    elif isinstance(search_result, list):
        raw_items = [item for item in search_result if isinstance(item, dict)]

    flat: list[dict[str, Any]] = []
    for item in raw_items:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        enriched = dict(item)
        enriched["metadata"] = _merge_metadata(metadata, best_query_meta)
        flat.append(enriched)

    deduped: dict[tuple[Any, str], dict[str, Any]] = {}
    for item in flat:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        key = (metadata.get("page_id"), str(metadata.get("claim_id") or ""))
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = item
            continue
        existing_score = float((existing.get("metadata") or {}).get("pre_score", 0.0) or 0.0)
        incoming_score = float((item.get("metadata") or {}).get("pre_score", 0.0) or 0.0)
        if incoming_score > existing_score:
            deduped[key] = item

    final_items = list(deduped.values())
    result_cap = max(1, int(settings.stage3_wiki_result_cap))
    if len(final_items) > result_cap:
        final_items = final_items[:result_cap]
    logger.info("Stage 3 (Wiki) Complete. Found %d", len(final_items))
    diagnostics["wiki_result_count"] = len(final_items)
    diagnostics["embed_error"] = wiki_debug.get("embed_error")
    diagnostics["candidates_count"] = int(wiki_debug.get("candidates_count") or 0)
    diagnostics["query_used_normalized"] = str(
        wiki_debug.get("query_used_normalized") or _clean_text(best_query_text)
    )
    diagnostics["vector_db_calls"] = int(wiki_debug.get("vector_db_calls") or 0)
    diagnostics["direct_vector_fastpath"] = bool(wiki_debug.get("direct_vector_fastpath"))
    return {"wiki_candidates": final_items, "stage03_wiki_diagnostics": diagnostics}


def run_wiki(state: dict) -> dict:
    """Execute Only Wiki Search (sync wrapper for legacy)."""
    return run_async_in_sync(run_wiki_async, state)


def _trim_ddg_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    max_results = max(1, int(settings.stage3_web_ddg_fallback_max_results))
    return results[:max_results]


async def _collect_web_candidates_for_query(
    query: dict[str, Any],
    *,
    timeout_budget: float,
    naver_limiter: asyncio.Semaphore,
    ddg_limiter: asyncio.Semaphore,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    text = _clean_text(query.get("text", ""))
    qtype = str(query.get("type", "direct")).strip().lower() or "direct"
    if not text:
        return [], {"fallback_ddg_count": 0}

    query_meta = _query_context(query)
    naver_min_results = max(0, int(settings.stage3_web_naver_min_results))
    fallback_ddg_count = 0
    collected: list[dict[str, Any]] = []

    if qtype == "web":
        ddg_results = await _safe_execute_with_context(
            _search_duckduckgo(text, limiter=ddg_limiter),
            query_meta,
            timeout=timeout_budget,
            name=f"DDG:{text[:10]}",
        )
        return _trim_ddg_results(ddg_results), {"fallback_ddg_count": 0}

    naver_results = await _safe_execute_with_context(
        _search_naver(text, limiter=naver_limiter),
        query_meta,
        timeout=timeout_budget,
        name=f"Naver:{text[:10]}",
    )
    collected.extend(naver_results)

    should_fallback_ddg = False
    if qtype == "news":
        should_fallback_ddg = len(naver_results) < naver_min_results
    elif qtype in {"verification", "direct"}:
        should_fallback_ddg = len(naver_results) < naver_min_results

    if should_fallback_ddg:
        ddg_results = await _safe_execute_with_context(
            _search_duckduckgo(text, limiter=ddg_limiter),
            query_meta,
            timeout=timeout_budget,
            name=f"DDG:{text[:10]}",
        )
        if ddg_results:
            collected.extend(_trim_ddg_results(ddg_results))
        fallback_ddg_count = 1

    return collected, {"fallback_ddg_count": fallback_ddg_count}


async def run_web_async(state: dict) -> dict:
    """Execute Only Web/News Search (async)."""
    search_queries = _extract_queries(state)
    prepared_queries, query_diagnostics = _prepare_web_queries(search_queries)

    tasks = []
    naver_limiter = asyncio.Semaphore(max(1, int(settings.naver_max_concurrency)))
    ddg_limiter = asyncio.Semaphore(max(1, int(settings.ddg_max_concurrency)))

    timeout_budget = _api_timeout_seconds() * _api_retry_attempts() + 5.0

    for query in prepared_queries:
        tasks.append(
            _collect_web_candidates_for_query(
                query,
                timeout_budget=timeout_budget,
                naver_limiter=naver_limiter,
                ddg_limiter=ddg_limiter,
            )
        )

    raw_results = await asyncio.gather(*tasks) if tasks else []
    flat: list[dict[str, Any]] = []
    fallback_ddg_count = 0
    for candidates, stats in raw_results:
        flat.extend(candidates)
        fallback_ddg_count += int(stats.get("fallback_ddg_count", 0))

    filtered: list[dict[str, Any]] = []
    blocked_domain_count = 0
    blocked_pattern_count = 0
    blocked_language_count = 0
    for item in flat:
        if not isinstance(item, dict):
            continue
        reason = _web_filter_reason(item)
        if reason == "domain":
            blocked_domain_count += 1
            continue
        if reason == "pattern":
            blocked_pattern_count += 1
            continue
        if reason == "language":
            blocked_language_count += 1
            continue
        filtered.append(item)

    logger.info("Stage 3 (Web) Complete. Found %d (raw=%d)", len(filtered), len(flat))
    diagnostics = dict(query_diagnostics)
    diagnostics["web_result_count"] = len(filtered)
    diagnostics["web_result_raw_count"] = len(flat)
    diagnostics["blocked_domain_count"] = blocked_domain_count
    diagnostics["blocked_pattern_count"] = blocked_pattern_count
    diagnostics["blocked_language_count"] = blocked_language_count
    diagnostics["fallback_ddg_count"] = fallback_ddg_count
    return {"web_candidates": filtered, "stage03_web_diagnostics": diagnostics}


def run_web(state: dict) -> dict:
    """Execute Only Web/News Search (sync wrapper for legacy)."""
    return run_async_in_sync(run_web_async, state)


def _normalize_url_simple(url: str) -> str:
    """Simple URL normalization for comparison (strip protocol, tracking params, trailing slash)."""
    if not url:
        return ""

    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = re.sub(r"/+", "/", parsed.path or "").rstrip("/")

    clean_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        k = key.lower()
        if any(k.startswith(prefix) for prefix in _TRACKING_QUERY_PREFIXES):
            continue
        clean_pairs.append((key, value))

    query = urlencode(clean_pairs, doseq=True)
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    if normalized.startswith("http://"):
        normalized = normalized[len("http://") :]
    elif normalized.startswith("https://"):
        normalized = normalized[len("https://") :]
    return normalized.lower()


def _bucket_source(source_type: str) -> str:
    src = str(source_type or "").upper()
    if src in {"WIKIPEDIA", "KNOWLEDGE_BASE", "KB_DOC"}:
        return "wiki"
    if src == "NEWS":
        return "news"
    return "web"


def _domain_from_url(url: str) -> str:
    netloc = (urlsplit(str(url or "").strip()).netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _is_low_quality_web_source(source_type: str, url: str) -> bool:
    if str(source_type or "").upper() in {"WIKIPEDIA", "KNOWLEDGE_BASE", "KB_DOC", "NEWS"}:
        return False
    domain = _domain_from_url(url)
    return _is_blocked_domain(domain)


def _is_similar_title(t1: str, t2: str, threshold: float = 0.9) -> bool:
    """Check if two titles are similar using SequenceMatcher."""
    if not t1 or not t2:
        return False

    def norm(text: str) -> str:
        return re.sub(r"[^\w\s]", "", text).lower().strip()

    nt1, nt2 = norm(t1), norm(t2)
    if not nt1 or not nt2:
        return False

    return difflib.SequenceMatcher(None, nt1, nt2).ratio() > threshold


def _compute_pre_score(candidate: dict[str, Any], claim_keywords: list[str]) -> tuple[float, dict[str, float]]:
    metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
    source_type = str(candidate.get("source_type") or "WEB_URL").upper()
    source_prior = _SOURCE_PRIOR.get(source_type, 0.5)

    title = _clean_text(candidate.get("title"))
    content = _clean_text(candidate.get("content"))
    title_overlap = _keyword_overlap_ratio(title, claim_keywords)
    content_overlap = _keyword_overlap_ratio(content, claim_keywords)

    intent = str(metadata.get("intent") or "").strip().lower()
    intent_bonus = _INTENT_BONUS.get(intent, 0.0)
    freshness = _freshness_bonus(metadata)

    score = (
        (0.46 * source_prior)
        + (0.30 * title_overlap)
        + (0.32 * content_overlap)
        + intent_bonus
        + freshness
    )
    score = max(0.0, min(score, 1.0))

    breakdown = {
        "source_prior": round(source_prior, 4),
        "title_overlap": round(title_overlap, 4),
        "content_overlap": round(content_overlap, 4),
        "max_overlap": round(max(title_overlap, content_overlap), 4),
        "intent_bonus": round(intent_bonus, 4),
        "freshness_bonus": round(freshness, 4),
    }
    return round(score, 4), breakdown


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _build_credibility(
    *,
    source_type: str,
    url: str,
    title: str,
    snippet: str,
    metadata: dict[str, Any],
    html_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trust = build_source_trust(
        url=url,
        source_type=source_type,
        overrides_json=settings.stage3_source_tier_overrides_json,
    )
    source_trust = float(trust.get("source_trust_score", 0.55))

    if not isinstance(html_signal, dict):
        html_signal = {
            "fetch_ok": False,
            "html_signal_score": 0.5,
            "breakdown": {"neutral": 1.0},
        }

    html_score = float(html_signal.get("html_signal_score", 0.5))
    credibility = _clip01((0.65 * source_trust) + (0.35 * html_score))

    return {
        "source_domain": trust.get("source_domain", "unknown"),
        "source_tier": trust.get("source_tier", "unknown"),
        "source_trust_score": round(source_trust, 4),
        "html_signal_score": round(html_score, 4),
        "html_fetch_ok": bool(html_signal.get("fetch_ok", False)),
        "html_signal_breakdown": html_signal.get("breakdown", {}),
        "credibility_score": round(credibility, 4),
        "credibility_breakdown": {
            "source_weight": 0.65,
            "html_weight": 0.35,
            "source_component": round(0.65 * source_trust, 4),
            "html_component": round(0.35 * html_score, 4),
        },
    }


def _is_content_too_short(candidate: dict[str, Any]) -> bool:
    source_type = str(candidate.get("source_type") or "").upper()
    if source_type in {"WIKIPEDIA", "KNOWLEDGE_BASE", "KB_DOC"}:
        return False
    content = _clean_text(candidate.get("content"))
    return len(content) < 40


def _dedupe_by_url(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        title_key = re.sub(r"\s+", " ", _clean_text(candidate.get("title"))).lower()
        key = _normalize_url_simple(_clean_text(candidate.get("url")))
        if not key:
            key = f"title::{title_key}"
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = candidate
            continue
        existing_score = float(((existing.get("metadata") or {}).get("pre_score") or 0.0))
        incoming_score = float(((candidate.get("metadata") or {}).get("pre_score") or 0.0))
        if incoming_score > existing_score:
            deduped[key] = candidate
    return list(deduped.values())


def _dedupe_by_title(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_candidates = sorted(
        candidates,
        key=lambda item: float(((item.get("metadata") or {}).get("pre_score") or 0.0)),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    for candidate in sorted_candidates:
        title = _clean_text(candidate.get("title"))
        if title and any(_is_similar_title(title, _clean_text(kept.get("title")), threshold=0.92) for kept in selected):
            continue
        selected.append(candidate)
    return selected


def _apply_source_caps(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    caps = _stage3_source_caps()
    global_cap = _stage3_global_cap()

    bucketed: dict[str, list[dict[str, Any]]] = {"news": [], "wiki": [], "web": []}
    for candidate in candidates:
        bucketed[_bucket_source(candidate.get("source_type", ""))].append(candidate)

    for bucket in bucketed.values():
        bucket.sort(
            key=lambda item: float(((item.get("metadata") or {}).get("pre_score") or 0.0)),
            reverse=True,
        )

    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()

    for bucket_name in ["news", "wiki", "web"]:
        cap = caps.get(bucket_name, 0)
        if cap <= 0:
            continue
        for candidate in bucketed[bucket_name][:cap]:
            selected.append(candidate)
            selected_ids.add(id(candidate))

    if len(selected) < global_cap:
        remaining = [
            candidate
            for candidate in sorted(
                candidates,
                key=lambda item: float(((item.get("metadata") or {}).get("pre_score") or 0.0)),
                reverse=True,
            )
            if id(candidate) not in selected_ids
        ]
        selected.extend(remaining[: max(0, global_cap - len(selected))])

    selected.sort(
        key=lambda item: float(((item.get("metadata") or {}).get("pre_score") or 0.0)),
        reverse=True,
    )
    return selected[:global_cap]


def run_merge(state: dict) -> dict:
    """Merge Wiki and Web candidates with dedup/filter/pre-score/global cap."""
    wiki = state.get("wiki_candidates", [])
    web = state.get("web_candidates", [])
    claim_mode = _normalize_mode(state.get("claim_mode"))
    rumor_or_mixed = claim_mode in {"rumor", "mixed"}

    canonical = state.get("canonical_evidence", {}) or {}
    source_url = canonical.get("source_url", "")
    source_title = _clean_text(canonical.get("article_title", ""))
    norm_source = _normalize_url_simple(source_url)

    claim_text = _clean_text(state.get("claim_text", ""))
    claim_keywords = _extract_keywords(claim_text)

    raw_candidates = list(wiki) + list(web)
    prepared: list[dict[str, Any]] = []
    low_quality_filtered = 0
    filtered_by_overlap = 0
    rescued_low_overlap = 0

    for candidate in raw_candidates:
        if not isinstance(candidate, dict):
            continue

        title = _clean_text(candidate.get("title"))
        content = _clean_text(candidate.get("content"))
        url = _clean_text(candidate.get("url"))

        if not title and not content:
            continue
        if _is_content_too_short(candidate):
            continue
        if _is_low_quality_web_source(candidate.get("source_type", ""), url):
            low_quality_filtered += 1
            continue

        norm_cand = _normalize_url_simple(url)
        if norm_source and norm_cand and norm_cand == norm_source:
            logger.info("Filtering self-reference URL: %s", url)
            continue

        if source_title and title and _is_similar_title(source_title, title, threshold=0.92):
            logger.info("Filtering self-reference Title: %s (Source: %s)", title, source_title)
            continue

        metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
        score, breakdown = _compute_pre_score(
            {
                "source_type": candidate.get("source_type"),
                "title": title,
                "content": content,
                "metadata": metadata,
            },
            claim_keywords,
        )
        source_bucket = _bucket_source(candidate.get("source_type", ""))
        max_overlap = float(breakdown.get("max_overlap", 0.0) or 0.0)
        if source_bucket in {"news", "web"}:
            min_overlap = max(0.0, float(settings.stage3_merge_min_overlap))
            soft_overlap = max(min_overlap, float(settings.stage3_merge_soft_overlap))
            if max_overlap < min_overlap:
                filtered_by_overlap += 1
                if not rumor_or_mixed:
                    continue
                rescued_low_overlap += 1
                rescue_cap = min(
                    float(settings.stage3_merge_low_overlap_score_cap),
                    float(settings.stage3_merge_low_overlap_rescue_score_cap),
                )
                capped_score = min(score, rescue_cap)
                if capped_score < score:
                    score = round(capped_score, 4)
                    breakdown["overlap_cap_applied"] = 1.0
                    breakdown["overlap_cap_value"] = round(capped_score, 4)
                breakdown["low_overlap_failopen"] = 1.0
            if max_overlap < soft_overlap:
                capped_score = min(score, float(settings.stage3_merge_low_overlap_score_cap))
                if capped_score < score:
                    score = round(capped_score, 4)
                    breakdown["overlap_cap_applied"] = 1.0
                    breakdown["overlap_cap_value"] = round(capped_score, 4)

        merged_metadata = dict(metadata)
        merged_metadata["pre_score"] = score
        merged_metadata["pre_score_breakdown"] = breakdown
        merged_metadata.update(
            _build_credibility(
                source_type=str(candidate.get("source_type") or "WEB_URL"),
                url=url,
                title=title,
                snippet=content,
                metadata=metadata,
                html_signal=None,
            )
        )

        prepared.append(
            {
                "source_type": candidate.get("source_type", "WEB_URL"),
                "title": title,
                "url": url,
                "content": content,
                "metadata": merged_metadata,
            }
        )

    deduped_by_url = _dedupe_by_url(prepared)
    deduped_by_title = _dedupe_by_title(deduped_by_url)
    html_enriched_count = 0
    html_fetch_fail_count = 0

    if bool(settings.stage3_html_signal_enabled):
        top_n = max(0, int(settings.stage3_html_signal_top_n))
        top_candidates = sorted(
            deduped_by_title,
            key=lambda item: float(((item.get("metadata") or {}).get("pre_score") or 0.0)),
            reverse=True,
        )[:top_n]

        for candidate in top_candidates:
            if not isinstance(candidate, dict):
                continue
            source_type = str(candidate.get("source_type") or "").upper()
            url = _clean_text(candidate.get("url"))
            if source_type not in {"NEWS", "WEB_URL", "WEB"} or not url:
                continue
            html_signal = analyze_html_signals(
                url=url,
                title=_clean_text(candidate.get("title")),
                snippet=_clean_text(candidate.get("content")),
                timeout_seconds=float(settings.stage3_html_signal_timeout_seconds),
            )
            if bool(html_signal.get("fetch_ok", False)):
                html_enriched_count += 1
            else:
                html_fetch_fail_count += 1

            metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
            metadata.update(
                _build_credibility(
                    source_type=source_type,
                    url=url,
                    title=_clean_text(candidate.get("title")),
                    snippet=_clean_text(candidate.get("content")),
                    metadata=metadata,
                    html_signal=html_signal,
                )
            )
            candidate["metadata"] = metadata

    capped = _apply_source_caps(deduped_by_title)

    source_mix = {"news": 0, "wiki": 0, "web": 0}
    tier_distribution: dict[str, int] = {}
    for item in capped:
        source_mix[_bucket_source(item.get("source_type", ""))] += 1
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        tier = str(meta.get("source_tier") or "unknown").strip().lower() or "unknown"
        tier_distribution[tier] = tier_distribution.get(tier, 0) + 1

    logger.info(
        "Stage 3 (Merge) Complete. raw=%d filtered=%d dedup=%d capped=%d mix=%s",
        len(raw_candidates),
        len(prepared),
        len(deduped_by_title),
        len(capped),
        source_mix,
    )
    return {
        "evidence_candidates": capped,
        "stage03_merge_stats": {
            "before_cap": len(deduped_by_title),
            "after_cap": len(capped),
            "source_mix": source_mix,
            "low_quality_filtered": low_quality_filtered,
            "filtered_by_overlap": filtered_by_overlap,
            "rescued_low_overlap": rescued_low_overlap,
            "html_enriched_count": html_enriched_count,
            "html_fetch_fail_count": html_fetch_fail_count,
            "tier_distribution": tier_distribution,
        },
        "wiki_candidates": None,
        "web_candidates": None,
        "search_queries": None,
        "query_variants": None,
    }


# Legacy run for compatibility if needed (wraps all)
def run(state: dict) -> dict:
    w = run_wiki(state)
    n = run_web(state)
    state.update(w)
    state.update(n)
    return run_merge(state)
