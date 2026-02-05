"""Stage 3 - Collect Evidence (Wiki + Naver + DDG Parallel)."""

import logging
import asyncio
import os
import re
import difflib
from typing import List, Dict, Any
from app.db.session import SessionLocal
from app.services.wiki_retriever import retrieve_wiki_hits

# Web Search Clients
import requests
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


logger = logging.getLogger(__name__)

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

async def _search_naver(query: str) -> List[Dict[str, Any]]:
    """Execute Naver Search (News)."""
    results = []
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.warning("Naver API credentials missing. Skipping.")
        return []

    try:
        safe_query = (query or "").strip()
        if len(safe_query) > 100:
            safe_query = safe_query[:100]
        print(f"[DEBUG Naver] query='{safe_query}'")
        logger.info("Naver query=%s", safe_query)
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret
        }
        params = {"query": safe_query, "display": 10, "sort": "sim"}
        
        # Offload sync HTTP request
        resp = await asyncio.to_thread(requests.get, url, headers=headers, params=params)
        print(f"[DEBUG Naver] status={resp.status_code}")
        logger.info("Naver status=%s", resp.status_code)
        
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            print(f"[DEBUG Naver] items={len(items)}")
            if not items:
                logger.warning("Naver returned 0 items for query='%s'", safe_query)
            for item in items:
                # Clean html tags from title/description if needed
                title = item["title"].replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")
                desc = item["description"].replace("<b>", "").replace("</b>", "").replace("&quot;", "\"")
                
                results.append({
                    "source_type": "NEWS",
                    "title": title,
                    "url": item["link"],
                    "content": desc,
                    "metadata": {"origin": "naver", "pub_date": item.get("pubDate")}
                })
        else:
            logger.error(f"Naver API Error: {resp.status_code} {resp.text[:200]}")
            
    except Exception as e:
        logger.error(f"Naver Search Failed for '{query}': {e}")
        
    return results

async def _search_duckduckgo(query: str) -> List[Dict[str, Any]]:
    """Execute DuckDuckGo Search."""
    results = []
    try:
        print(f"[DEBUG DDG] query='{(query or '').strip()}'")
        logger.info("DDG query=%s", (query or "").strip())
        # DDGS is synchronous
        def _sync_ddg():
            with DDGS() as ddgs:
                # text() returns iterator, consume it
                return list(ddgs.text(query, max_results=10))

        ddg_results = await asyncio.to_thread(_sync_ddg)
        print(f"[DEBUG DDG] results={len(ddg_results)}")
        logger.info("DDG results=%d", len(ddg_results))
        
        for r in ddg_results:
            results.append({
                "source_type": "WEB_URL",
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "content": r.get("body", ""),
                "metadata": {"origin": "duckduckgo"}
            })
            
    except Exception as e:
        logger.error(f"DuckDuckGo Search Failed for '{query}': {e}")
        
    return results

def _extract_queries(state: dict) -> list:
    def _coerce_query_item(item: Any) -> Dict[str, Any] | None:
        if isinstance(item, dict):
            return item
        if hasattr(item, "model_dump"):
            return item.model_dump()
        if hasattr(item, "dict"):
            return item.dict()
        if hasattr(item, "to_dict"):
            return item.to_dict()
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
    
    print(f"[DEBUG Extract Queries] Found {len(search_queries)} queries")
    logger.info(f"[Extract Queries] Found {len(search_queries)} queries")
    for i, q in enumerate(search_queries):
        if isinstance(q, dict):
            msg = f"[Extract Queries] Query {i}: type={q.get('type')}, text='{q.get('text', '')[:50]}'"
            print(f"[DEBUG {msg}]")
            logger.info(msg)
        else:
            msg = f"[Extract Queries] Query {i}: (string) '{str(q)[:50]}'"
            print(f"[DEBUG {msg}]")
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
    
    print(f"[DEBUG Wiki Search] Total queries: {len(search_queries)}")
    logger.info(f"[Wiki Search] Total queries: {len(search_queries)}")
    
    for q in search_queries:
        text = q if isinstance(q, str) else q.get("text", "")
        qtype = "direct" if isinstance(q, str) else q.get("type", "direct")
        if not isinstance(q, str) and hasattr(qtype, "value"):
            qtype = qtype.value
        qtype = str(qtype).lower().strip()
        q_search_mode = search_mode if isinstance(q, str) else q.get("search_mode", search_mode)
        
        print(f"[DEBUG Wiki Search] Processing query: type={qtype}, text='{text}'")
        logger.info(f"[Wiki Search] Processing query: type={qtype}, text='{text}'")
        
        if not text:
            continue

        # Only process queries explicitly marked as "wiki" type
        if qtype == "wiki":
            normalized = _normalize_wiki_query(text)
            print(f"[DEBUG Wiki Search] Normalized '{text}' → {normalized}")
            logger.info(f"[Wiki Search] Normalized '{text}' → {normalized}")
            for term in normalized:
                if term and term not in wiki_inputs:
                    wiki_inputs[term] = q_search_mode

    wiki_input_list = list(wiki_inputs.keys())
    print(f"[DEBUG Wiki Search] Final wiki_inputs: {wiki_input_list}")
    logger.info(f"[Wiki Search] Final wiki_inputs: {wiki_input_list}")

    if wiki_inputs:
        # Run parallel searches (Union strategy)
        # Using " & " (AND) logic forces a single page to cover ALL topics, which is too restrictive.
        # Queries like "Bitcoin Price" and "Geopolitics" should be separate searches.
        for term, mode in wiki_inputs.items():
             tasks.append(_safe_execute(_search_wiki(term, mode), 600.0, f"Wiki-Query:{term[:10]}"))
    else:
        print("[DEBUG Wiki Search] No wiki inputs - skipping search")

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
    try:
        return asyncio.run(run_wiki_async(state))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        out = loop.run_until_complete(run_wiki_async(state))
        loop.close()
        return out

async def run_web_async(state: dict) -> dict:
    """Execute Only Web/News Search (async)."""
    search_queries = _extract_queries(state)

    tasks = []
    for q in search_queries:
        text = q if isinstance(q, str) else q.get("text", "")
        qtype = "direct" if isinstance(q, str) else q.get("type", "direct")
        if not isinstance(q, str) and hasattr(qtype, "value"):
            qtype = qtype.value
        qtype = str(qtype).lower().strip()
        if not text:
            continue

        if qtype == "news":
            tasks.append(_safe_execute(_search_naver(text), 10.0, f"Naver:{text[:10]}"))
            tasks.append(_safe_execute(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
        elif qtype == "web":
            tasks.append(_safe_execute(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
        elif qtype == "verification":
            tasks.append(_safe_execute(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
            tasks.append(_safe_execute(_search_naver(text), 10.0, f"Naver:{text[:10]}"))
        elif qtype == "direct":
            tasks.append(_safe_execute(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
            tasks.append(_safe_execute(_search_naver(text), 10.0, f"Naver:{text[:10]}"))

    results = await asyncio.gather(*tasks)
    flat = [item for sublist in results for item in sublist]
    logger.info(f"Stage 3 (Web) Complete. Found {len(flat)}")
    return {"web_candidates": flat}


def run_web(state: dict) -> dict:
    """Execute Only Web/News Search (sync wrapper for legacy)."""
    try:
        return asyncio.run(run_web_async(state))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        out = loop.run_until_complete(run_web_async(state))
        loop.close()
        return out

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
