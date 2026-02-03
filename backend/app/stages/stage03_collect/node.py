"""Stage 3 - Collect Evidence (Wiki + Naver + DDG Parallel)."""

import logging
import asyncio
import os
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
                    top_k=5,         
                    window=2,        
                    page_limit=5,
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
        url = "https://openapi.naver.com/v1/search/news.json"
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret
        }
        params = {"query": safe_query, "display": 5, "sort": "sim"}
        
        # Offload sync HTTP request
        resp = await asyncio.to_thread(requests.get, url, headers=headers, params=params)
        
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
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
            logger.error(f"Naver API Error: {resp.status_code} {resp.text}")
            
    except Exception as e:
        logger.error(f"Naver Search Failed for '{query}': {e}")
        
    return results

async def _search_duckduckgo(query: str) -> List[Dict[str, Any]]:
    """Execute DuckDuckGo Search."""
    results = []
    try:
        # DDGS is synchronous
        def _sync_ddg():
            with DDGS() as ddgs:
                # text() returns iterator, consume it
                return list(ddgs.text(query, max_results=5))

        ddg_results = await asyncio.to_thread(_sync_ddg)
        
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
    search_queries = state.get("search_queries", [])
    if not search_queries:
        search_queries = state.get("query_variants", [])
    if not search_queries:
        fallback = state.get("claim_text") or state.get("input_payload")
        if fallback:
            search_queries = [fallback]
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

def run_wiki(state: dict) -> dict:
    """Execute Only Wiki Search."""
    search_queries = _extract_queries(state)
    search_mode = state.get("search_mode", "fts")
    
    async def _do_wiki():
        tasks = []
        # Filter for wiki queries
        wiki_inputs = []
        for q in search_queries:
            text = q if isinstance(q, str) else q.get("text", "")
            qtype = "direct" if isinstance(q, str) else q.get("type", "direct")
            if not text: continue
            
            if qtype in ("wiki", "verification", "direct"):
                if "wiki" in qtype or "wiki" in str(q).lower(): 
                   wiki_inputs.append(text)
                elif qtype == "direct":
                   # If generic, include in wiki
                   wiki_inputs.append(text)

        # Remove duplicates
        wiki_inputs = list(set(wiki_inputs))
        
        if wiki_inputs:
             # AND logic if multiple
            if len(wiki_inputs) > 1:
                combined = " & ".join(wiki_inputs)
                tasks.append(_safe_execute(_search_wiki(combined, search_mode), 60.0, "Wiki-AND"))
            else:
                tasks.append(_safe_execute(_search_wiki(wiki_inputs[0], search_mode), 60.0, "Wiki-Single"))

        results = await asyncio.gather(*tasks)
        flat = [item for sublist in results for item in sublist]
        return flat

    try:
        candidates = asyncio.run(_do_wiki())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        candidates = loop.run_until_complete(_do_wiki())
        loop.close()
        
    logger.info(f"Stage 3 (Wiki) Complete. Found {len(candidates)}")
    return {"wiki_candidates": candidates}

def run_web(state: dict) -> dict:
    """Execute Only Web/News Search."""
    search_queries = _extract_queries(state)
    
    async def _do_web():
        tasks = []
        for q in search_queries:
            text = q if isinstance(q, str) else q.get("text", "")
            qtype = "direct" if isinstance(q, str) else q.get("type", "direct")
            if not text: continue
            
            # Decide if this query goes to web/news
            if qtype == "news":
                tasks.append(_safe_execute(_search_naver(text), 10.0, f"Naver:{text[:10]}"))
                tasks.append(_safe_execute(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
            elif qtype == "web":
                tasks.append(_safe_execute(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
            elif qtype == "verification":
                tasks.append(_safe_execute(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
                tasks.append(_safe_execute(_search_naver(text), 10.0, f"Naver:{text[:10]}"))
            elif qtype == "direct":
                 # Generic fallback: do both if not explicitly wiki only
                 tasks.append(_safe_execute(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
                 # Maybe Naver too? Let's be generous
                 tasks.append(_safe_execute(_search_naver(text), 10.0, f"Naver:{text[:10]}"))

        results = await asyncio.gather(*tasks)
        flat = [item for sublist in results for item in sublist]
        return flat

    try:
        candidates = asyncio.run(_do_web())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        candidates = loop.run_until_complete(_do_web())
        loop.close()

    logger.info(f"Stage 3 (Web) Complete. Found {len(candidates)}")
    return {"web_candidates": candidates}

def run_merge(state: dict) -> dict:
    """Merge Wiki and Web candidates."""
    wiki = state.get("wiki_candidates", [])
    web = state.get("web_candidates", [])
    
    # Deduplicate by URL or content hash if needed, but for now simple concatenation
    # Maybe prioritize Wiki?
    
    all_candidates = wiki + web
    logger.info(f"Stage 3 (Merge) Complete. Total {len(all_candidates)} candidates.")
    return {"evidence_candidates": all_candidates}

# Legacy run for compatibility if needed (wraps all)
def run(state: dict) -> dict:
    w = run_wiki(state)
    n = run_web(state)
    state.update(w)
    state.update(n)
    return run_merge(state)
