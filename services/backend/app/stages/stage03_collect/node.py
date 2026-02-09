"""Stage 3 - Collect Evidence (Wiki + Naver + DDG Parallel)."""

import logging
import asyncio
import re
import difflib
from typing import List, Dict, Any
from app.db.session import SessionLocal
from app.core.async_utils import run_async_in_sync
from app.core.observability import record_external_api_result
from app.core.settings import settings
from app.services.wiki_retriever import retrieve_wiki_hits

# Web Search Clients
import requests
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


logger = logging.getLogger(__name__)


def _api_timeout_seconds() -> float:
    return max(1.0, float(settings.external_api_timeout_seconds))


def _api_retry_attempts() -> int:
    return max(1, int(settings.external_api_retry_attempts))


def _api_backoff_seconds() -> float:
    return float(max(0.05, float(settings.external_api_backoff_seconds)))


def _backoff_delay(attempt: int) -> float:
    # Exponential backoff with cap to avoid runaway wait.
    return float(min(5.0, _api_backoff_seconds() * (2**attempt)))


def _is_retryable_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599

async def _search_wiki(query: str, search_mode: str) -> List[Dict[str, Any]]:
    """Execute Wiki Search."""
    results = []
    try:
        # DB Session per thread/task
        # Note: SessionLocal is synchronous. In a real highly concurrent app, consider AsyncSession.
        # Here we run sync DB call in a thread pool via asyncio.to_thread if needed, 
        # but for simplicity in this MVP scafold, straight execution (blocking loop briefly) 
        # is acceptable or wrap with to_thread.
        
        def _sync_wiki_task():
            with SessionLocal() as db:
                return retrieve_wiki_hits(
                    db=db,
                    question=query,
                    top_k=2,         
                    window=2,        
                    page_limit=2,
                    embed_missing=True,
                    search_mode=search_mode
                )
        
        # Offload sync DB work to thread
        hits_data = await asyncio.to_thread(_sync_wiki_task)
            
        for h in hits_data.get("hits", []):
            results.append({
                "source_type": "WIKIPEDIA",
                "title": h["title"],
                "url": f"wiki://page/{h['page_id']}",
                "content": h["content"],
                "metadata": {
                    "page_id": h["page_id"],
                    "chunk_id": h["chunk_id"],
                    "dist": h.get("dist"),
                    "lex_score": h.get("lex_score"),
                    "search_query": query,  # User request: show query used
                }
            })
    except Exception as e:
        logger.error(f"Wiki Search Failed for '{query}': {e}")
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
        "X-Naver-Client-Secret": client_secret
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
                    title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")
                    desc = item["description"].replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")

                    results.append({
                        "source_type": "NEWS",
                        "title": title,
                        "url": item["link"],
                        "content": desc,
                        "metadata": {"origin": "naver", "pub_date": item.get("pubDate")}
                    })
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
                    return list(ddgs.text(query, max_results=10))

            async with sem:
                ddg_results = await asyncio.wait_for(
                    asyncio.to_thread(_sync_ddg),
                    timeout=request_timeout,
                )

            logger.info("DDG results=%d attempt=%d", len(ddg_results), attempt + 1)

            for r in ddg_results:
                results.append({
                    "source_type": "WEB_URL",
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "content": r.get("body", ""),
                    "metadata": {"origin": "duckduckgo"}
                })
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

def _extract_queries(state: dict) -> list:
    def _coerce_query_item(item: Any) -> Dict[str, Any] | None:
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

    raw_queries = state.get("search_queries", [])
    if raw_queries:
        search_queries = [q for q in (_coerce_query_item(i) for i in raw_queries) if q]
    else:
        raw_variants = state.get("query_variants", [])
        search_queries = [q for q in (_coerce_query_item(i) for i in raw_variants) if q]
        if not search_queries:
            fallback = state.get("claim_text") or state.get("input_payload")
            if fallback:
                search_queries = [{"type": "direct", "text": fallback}]
    
    logger.info(f"[Extract Queries] Found {len(search_queries)} queries")
    for i, q in enumerate(search_queries):
        if isinstance(q, dict):
            msg = f"[Extract Queries] Query {i}: type={q.get('type')}, text='{q.get('text', '')[:50]}'"
            logger.info(msg)
        else:
            msg = f"[Extract Queries] Query {i}: (string) '{str(q)[:50]}'"
            logger.info(msg)
    
    # NOTE: keyword_bundles auto-addition removed
    # It was creating noise by searching for compound terms like "백신 관련주"
    # that don't have dedicated wiki pages
    # LLM should generate precise wiki queries only
    
    return search_queries

async def _safe_execute(coro, timeout=10.0, name="Task"):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Task Timeout ({timeout}s): {name}")
        return []
    except Exception as e:
        logger.error(f"Task Error ({name}): {e}")
        return []

def _normalize_wiki_query(text: str) -> List[str]:
    """
    위키 쿼리 정규화: LLM이 생성한 표제어를 정제.
    - 불필요한 조사/접미사 제거
    - 복합어 분리 (필요시)
    """
    if not text:
        return []
    
    # 1. 구분자로 분리 (쉼표, &)
    parts = re.split(r"\s*[,&]\s*", text)
    
    # 2. 각 파트 정제
    terms = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        
        # 한글 조사 제거 (예: "니파바이러스의" -> "니파바이러스")
        p = re.sub(r"(의|에|를|을|이|가|은|는|와|과|로|으로)$", "", p)
        
        # 너무 긴 복합어 감지 (20자 이상) - 경고만 출력
        if len(p) > 20:
            logger.warning(f"Wiki query too long (likely compound term): '{p}'")
        
        terms.append(p.strip())
    
    return terms if terms else [text.strip()]


async def run_wiki_async(state: dict) -> dict:
    """Execute Only Wiki Search (async)."""
    search_queries = _extract_queries(state)
    search_mode = state.get("search_mode", "lexical")

    tasks = []
    wiki_inputs: Dict[str, str] = {}
    
    logger.info(f"[Wiki Search] Total queries: {len(search_queries)}")
    
    for q in search_queries:
        text = q if isinstance(q, str) else q.get("text", "")
        qtype = "direct" if isinstance(q, str) else q.get("type", "direct")
        if not isinstance(q, str) and hasattr(qtype, "value"):
            qtype = qtype.value
        qtype = str(qtype).lower().strip()
        q_search_mode = search_mode if isinstance(q, str) else q.get("search_mode", search_mode)
        
        logger.info(f"[Wiki Search] Processing query: type={qtype}, text='{text}'")
        
        if not text:
            continue

        # Only process queries explicitly marked as "wiki" type
        if qtype == "wiki":
            normalized = _normalize_wiki_query(text)
            logger.info(f"[Wiki Search] Normalized '{text}' → {normalized}")
            for term in normalized:
                if term and term not in wiki_inputs:
                    wiki_inputs[term] = q_search_mode

    wiki_input_list = list(wiki_inputs.keys())
    logger.info(f"[Wiki Search] Final wiki_inputs: {wiki_input_list}")

    if wiki_inputs:
        # Run parallel searches (Union strategy)
        # Using " & " (AND) logic forces a single page to cover ALL topics, which is too restrictive.
        # Queries like "Bitcoin Price" and "Geopolitics" should be separate searches.
        for term, mode in wiki_inputs.items():
             tasks.append(_safe_execute(_search_wiki(term, mode), 600.0, f"Wiki-Query:{term[:10]}"))
    else:
        logger.info("[Wiki Search] No wiki inputs - skipping search")

    results = await asyncio.gather(*tasks)
    flat = [item for sublist in results for item in sublist]

    # Deduplicate by Page ID (since multiple queries might find same page)
    unique_map = {}
    for item in flat:
        pid = item["metadata"]["page_id"]
        if pid not in unique_map:
            unique_map[pid] = item
    
    flat = list(unique_map.values())

    logger.info(f"Stage 3 (Wiki) Complete. Found {len(flat)}")
    return {"wiki_candidates": flat}


def run_wiki(state: dict) -> dict:
    """Execute Only Wiki Search (sync wrapper for legacy)."""
    return run_async_in_sync(run_wiki_async, state)

async def run_web_async(state: dict) -> dict:
    """Execute Only Web/News Search (async)."""
    search_queries = _extract_queries(state)

    tasks = []
    naver_limiter = asyncio.Semaphore(max(1, int(settings.naver_max_concurrency)))
    ddg_limiter = asyncio.Semaphore(max(1, int(settings.ddg_max_concurrency)))
    for q in search_queries:
        text = q if isinstance(q, str) else q.get("text", "")
        qtype = "direct" if isinstance(q, str) else q.get("type", "direct")
        if not isinstance(q, str) and hasattr(qtype, "value"):
            qtype = qtype.value
        qtype = str(qtype).lower().strip()
        if not text:
            continue

        if qtype == "news":
            tasks.append(_safe_execute(_search_naver(text, limiter=naver_limiter), _api_timeout_seconds() * _api_retry_attempts() + 5.0, f"Naver:{text[:10]}"))
            tasks.append(_safe_execute(_search_duckduckgo(text, limiter=ddg_limiter), _api_timeout_seconds() * _api_retry_attempts() + 5.0, f"DDG:{text[:10]}"))
        elif qtype == "web":
            tasks.append(_safe_execute(_search_duckduckgo(text, limiter=ddg_limiter), _api_timeout_seconds() * _api_retry_attempts() + 5.0, f"DDG:{text[:10]}"))
        elif qtype == "verification":
            tasks.append(_safe_execute(_search_duckduckgo(text, limiter=ddg_limiter), _api_timeout_seconds() * _api_retry_attempts() + 5.0, f"DDG:{text[:10]}"))
            tasks.append(_safe_execute(_search_naver(text, limiter=naver_limiter), _api_timeout_seconds() * _api_retry_attempts() + 5.0, f"Naver:{text[:10]}"))
        elif qtype == "direct":
            tasks.append(_safe_execute(_search_duckduckgo(text, limiter=ddg_limiter), _api_timeout_seconds() * _api_retry_attempts() + 5.0, f"DDG:{text[:10]}"))
            tasks.append(_safe_execute(_search_naver(text, limiter=naver_limiter), _api_timeout_seconds() * _api_retry_attempts() + 5.0, f"Naver:{text[:10]}"))

    results = await asyncio.gather(*tasks)
    flat = [item for sublist in results for item in sublist]
    logger.info(f"Stage 3 (Web) Complete. Found {len(flat)}")
    return {"web_candidates": flat}


def run_web(state: dict) -> dict:
    """Execute Only Web/News Search (sync wrapper for legacy)."""
    return run_async_in_sync(run_web_async, state)

def _normalize_url_simple(url: str) -> str:
    """Simple URL normalization for comparison (strip protocol, www, trailing slash)."""
    if not url:
        return ""
    # Remove protocol
    u = re.sub(r"^https?://", "", url)
    # Remove www.
    u = re.sub(r"^www\.", "", u)
    # Remove trailing slash
    u = u.rstrip("/")
    u = u.rstrip("/")
    return u.lower()

def _is_similar_title(t1: str, t2: str, threshold: float = 0.9) -> bool:
    """Check if two titles are similar using SequenceMatcher."""
    if not t1 or not t2:
        return False
    # Normalize titles simple (remove special chars, lowercase)
    def norm(t):
        return re.sub(r"[^\w\s]", "", t).lower().strip()
    
    nt1, nt2 = norm(t1), norm(t2)
    if not nt1 or not nt2:
        return False
        
    return difflib.SequenceMatcher(None, nt1, nt2).ratio() > threshold

def run_merge(state: dict) -> dict:
    """Merge Wiki and Web candidates with Self-Reference Filtering."""
    wiki = state.get("wiki_candidates", [])
    web = state.get("web_candidates", [])
    
    # Check for canonical source URL (the article being checked)
    canonical = state.get("canonical_evidence", {}) or {}
    source_url = canonical.get("source_url", "")
    norm_source = _normalize_url_simple(source_url)
    
    all_candidates = []
    
    # Merge and Filter
    raw_candidates = wiki + web
    for cand in raw_candidates:
        cand_url = cand.get("url", "")
        norm_cand = _normalize_url_simple(cand_url)
        
        # Filter 1: Exact URL match (Self-Reference)
        if norm_source and norm_cand == norm_source:
            logger.info(f"Filtering self-reference URL: {cand_url}")
            continue
            
        # Filter 2: Naver News redundancy (e.g. source is n.news.naver.com, candidate is same)
        # Often Naver news URLs have params like ?sid=101. 
        # Ideally we check path similarity, but for now exact normalized match + basic param stripping is safer.
        # Let's trust normalize for now.
        
        # Filter 2: Naver News redundancy (e.g. source is n.news.naver.com, candidate is same)
        # Often Naver news URLs have params like ?sid=101. 
        # Ideally we check path similarity, but for now exact normalized match + basic param stripping is safer.
        # Let's trust normalize for now.
        
        # Filter 3: Title Similarity (Semantic Filter)
        # Check against Source Article Title
        source_title = canonical.get("article_title", "")
        cand_title = cand.get("title", "")
        
        if source_title and _is_similar_title(source_title, cand_title, threshold=0.9):
            logger.info(f"Filtering self-reference Title: {cand_title} (Source: {source_title})")
            continue
            
        all_candidates.append(cand)
    
    logger.info(f"Stage 3 (Merge) Complete. Total {len(all_candidates)} candidates (Filtered {len(raw_candidates) - len(all_candidates)}).")
    return {
        "evidence_candidates": all_candidates,
        "wiki_candidates": None,
        "web_candidates": None,
        "search_queries": None,  # queries are no longer needed
        "query_variants": None   # variants are no longer needed
    }

# Legacy run for compatibility if needed (wraps all)
def run(state: dict) -> dict:
    w = run_wiki(state)
    n = run_web(state)
    state.update(w)
    state.update(n)
    return run_merge(state)
