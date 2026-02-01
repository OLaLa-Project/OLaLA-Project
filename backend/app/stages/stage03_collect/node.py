"""Stage 3 - Collect Evidence (Wiki + Naver + DDG Parallel)."""

import logging
import asyncio
import os
from typing import List, Dict, Any
from app.db.session import SessionLocal
from app.services.wiki_retriever import retrieve_wiki_hits

# Web Search Clients
import requests
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
                "source_type": "KNOWLEDGE_BASE",
                "title": h["title"],
                "url": f"wiki://page/{h['page_id']}",
                "content": h["content"],
                "metadata": {
                    "page_id": h["page_id"],
                    "chunk_id": h["chunk_id"],
                    "dist": h.get("dist"),
                    "lex_score": h.get("lex_score")
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
                "source_type": "WEB",
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "content": r.get("body", ""),
                "metadata": {"origin": "duckduckgo"}
            })
            
    except Exception as e:
        logger.error(f"DuckDuckGo Search Failed for '{query}': {e}")
        
    return results

def run(state: dict) -> dict:
    """
    Stage 3 Main:
    1. Extract queries
    2. Parallel Execute (Wiki + Naver + DDG)
    3. Aggregate results
    """
    search_queries = state.get("search_queries", [])
    if not search_queries:
        fallback = state.get("claim_text") or state.get("input_payload")
        if fallback:
            search_queries = [fallback]
    
    search_mode = state.get("search_mode", "auto")
    logger.info(f"Stage 3 Start. Queries: {search_queries}, Mode: {search_mode}")

    evidence_candidates = []
    
    async def _safe_task(coro, timeout=10.0, name="Task"):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Stage 3 Task Timeout ({timeout}s): {name}")
            return []
        except Exception as e:
            logger.error(f"Stage 3 Task Error ({name}): {e}")
            return []

    async def _gather_all():
        tasks = []
        for i, q_obj in enumerate(search_queries):
            # Handle both dict (new) and str (legacy)
            if isinstance(q_obj, str):
                text = q_obj
                qtype = "direct"
            else:
                text = q_obj.get("text", "")
                qtype = q_obj.get("type", "direct")
            
            if not text:
                continue

            # Routing Logic with Individual Timeouts
            if qtype == "wiki":
                tasks.append(_safe_task(_search_wiki(text, search_mode), 60.0, f"Wiki:{text[:10]}"))
            elif qtype == "news":
                tasks.append(_safe_task(_search_naver(text), 10.0, f"Naver:{text[:10]}"))
                tasks.append(_safe_task(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
            elif qtype == "web":
                 tasks.append(_safe_task(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
            else:
                tasks.append(_safe_task(_search_wiki(text, search_mode), 60.0, f"Wiki:{text[:10]}"))
                tasks.append(_safe_task(_search_duckduckgo(text), 10.0, f"DDG:{text[:10]}"))
                if qtype != "verification":
                    tasks.append(_safe_task(_search_naver(text), 5.0, f"Naver:{text[:10]}"))
        
        # Now gather safe tasks - none should hang indefinitely
        results = await asyncio.gather(*tasks)
        
        flat_results = []
        for r in results:
             if isinstance(r, list):
                 flat_results.extend(r)
        
        return flat_results

    try:
        evidence_candidates = asyncio.run(_gather_all())
    except RuntimeError: 
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        evidence_candidates = loop.run_until_complete(_gather_all())
        loop.close()

    state["evidence_candidates"] = evidence_candidates
    logger.info(f"Stage 3 Complete. Collected {len(evidence_candidates)} candidates.")
    
    return state
