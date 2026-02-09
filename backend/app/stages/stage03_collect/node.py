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
    "NEWS": 0.66,
    "WEB_URL": 0.54,
    "WEB": 0.54,
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
    "play.google.com",
    "apps.apple.com",
    "youtube.com",
    "youtu.be",
    "zhihu.com",
    "stackexchange.com",
    "stackoverflow.com",
}
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


async def _search_wiki(query: str, search_mode: str) -> List[Dict[str, Any]]:
    """Execute Wiki Search."""
    results = []
    try:
        def _sync_wiki_task():
            with SessionLocal() as db:
                return retrieve_wiki_hits(
                    db=db,
                    question=query,
                    top_k=3,
                    window=2,
                    page_limit=3,
                    embed_missing=True,
                    search_mode=search_mode,
                )

        hits_data = await asyncio.to_thread(_sync_wiki_task)

        for h in hits_data.get("hits", []):
            results.append(
                {
                    "source_type": "WIKIPEDIA",
                    "title": h["title"],
                    "url": f"wiki://page/{h['page_id']}",
                    "content": h["content"],
                    "metadata": {
                        "page_id": h["page_id"],
                        "chunk_id": h["chunk_id"],
                        "dist": h.get("dist"),
                        "lex_score": h.get("lex_score"),
                        "search_query": query,
                    },
                }
            )
    except Exception as e:
        logger.error("Wiki Search Failed for '%s': %s", query, e)
    return results


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
    search_mode = state.get("search_mode", "lexical")

    tasks = []
    
    # 1. Select the best single query for Vector Search
    best_query_text = ""
    best_query_meta = {}
    best_search_mode = search_mode

    # Priority: First 'wiki' type -> First 'direct' type -> core_fact/fallback
    # Since we want a sentence for vector search, we prefer longer, descriptive queries.
    
    candidate_queries = [q for q in search_queries if str(q.get("type", "")).strip().lower() == "wiki"]
    if not candidate_queries:
         candidate_queries = [q for q in search_queries if str(q.get("type", "")).strip().lower() == "direct"]
    
    if candidate_queries:
        # Use the first valid candidate
        target = candidate_queries[0]
        best_query_text = _clean_text(target.get("text", ""))
        best_query_meta = _query_context(target)
        best_search_mode = target.get("search_mode", search_mode)
    
    if not best_query_text:
        # Fallback to claim text if no specific query found
        best_query_text = str(state.get("claim_text") or "").strip()
        best_query_meta = {"intent": "general", "mode": "fact", "stance": "neutral"}
    
    # 2. Execute ONE search if we have a query
    if best_query_text:
        # Don't normalize/split into terms. Use the full sentence for vector search.
        logger.info("Executing Single Wiki Vector Search: '%s'", best_query_text)
        
        # Ensure meta defines it as wiki
        if not best_query_meta.get("query_type"):
            best_query_meta["query_type"] = "wiki"
            
        tasks.append(
            _safe_execute_with_context(
                _search_wiki(best_query_text, best_search_mode),
                best_query_meta,
                timeout=600.0,
                name=f"Wiki-Vector:{best_query_text[:20]}",
            )
        )

    results = await asyncio.gather(*tasks) if tasks else []
    flat = [item for sublist in results for item in sublist]

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
    logger.info("Stage 3 (Wiki) Complete. Found %d", len(final_items))
    return {"wiki_candidates": final_items}


def run_wiki(state: dict) -> dict:
    """Execute Only Wiki Search (sync wrapper for legacy)."""
    return run_async_in_sync(run_wiki_async, state)


async def run_web_async(state: dict) -> dict:
    """Execute Only Web/News Search (async)."""
    search_queries = _extract_queries(state)

    tasks = []
    naver_limiter = asyncio.Semaphore(max(1, int(settings.naver_max_concurrency)))
    ddg_limiter = asyncio.Semaphore(max(1, int(settings.ddg_max_concurrency)))

    timeout_budget = _api_timeout_seconds() * _api_retry_attempts() + 5.0

    for query in search_queries:
        text = _clean_text(query.get("text", ""))
        qtype = str(query.get("type", "direct")).strip().lower() or "direct"
        if not text:
            continue

        query_meta = _query_context(query)

        if qtype == "news":
            tasks.append(
                _safe_execute_with_context(
                    _search_naver(text, limiter=naver_limiter),
                    query_meta,
                    timeout=timeout_budget,
                    name=f"Naver:{text[:10]}",
                )
            )
            tasks.append(
                _safe_execute_with_context(
                    _search_duckduckgo(text, limiter=ddg_limiter),
                    query_meta,
                    timeout=timeout_budget,
                    name=f"DDG:{text[:10]}",
                )
            )
        elif qtype == "web":
            tasks.append(
                _safe_execute_with_context(
                    _search_duckduckgo(text, limiter=ddg_limiter),
                    query_meta,
                    timeout=timeout_budget,
                    name=f"DDG:{text[:10]}",
                )
            )
        elif qtype in {"verification", "direct"}:
            tasks.append(
                _safe_execute_with_context(
                    _search_duckduckgo(text, limiter=ddg_limiter),
                    query_meta,
                    timeout=timeout_budget,
                    name=f"DDG:{text[:10]}",
                )
            )
            tasks.append(
                _safe_execute_with_context(
                    _search_naver(text, limiter=naver_limiter),
                    query_meta,
                    timeout=timeout_budget,
                    name=f"Naver:{text[:10]}",
                )
            )

    results = await asyncio.gather(*tasks) if tasks else []
    flat = [item for sublist in results for item in sublist]
    logger.info("Stage 3 (Web) Complete. Found %d", len(flat))
    return {"web_candidates": flat}


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
    if not domain:
        return False
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in _LOW_QUALITY_WEB_DOMAINS)


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

    score = source_prior + (0.22 * title_overlap) + (0.20 * content_overlap) + intent_bonus + freshness
    score = max(0.0, min(score, 1.0))

    breakdown = {
        "source_prior": round(source_prior, 4),
        "title_overlap": round(title_overlap, 4),
        "content_overlap": round(content_overlap, 4),
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

    canonical = state.get("canonical_evidence", {}) or {}
    source_url = canonical.get("source_url", "")
    source_title = _clean_text(canonical.get("article_title", ""))
    norm_source = _normalize_url_simple(source_url)

    claim_text = _clean_text(state.get("claim_text", ""))
    claim_keywords = _extract_keywords(claim_text)

    raw_candidates = list(wiki) + list(web)
    prepared: list[dict[str, Any]] = []
    low_quality_filtered = 0

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
