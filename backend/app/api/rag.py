# backend/app/api/rag.py
import json
from typing import Any, Generator
import requests
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.wiki_schemas import WikiSearchRequest
from app.core.settings import settings
from app.services.rag_usecase import retrieve_wiki_context

OLLAMA_URL = settings.ollama_url
OLLAMA_TIMEOUT = settings.ollama_timeout

router = APIRouter(prefix="/api")

class WikiSearchResponse(BaseModel):
    ok: bool
    sources: list[dict[str, Any]]
    context_chars: int


@router.post("/rag/wiki/search")
def wiki_search(req: WikiSearchRequest, db: Session = Depends(get_db)) -> JSONResponse:
    pack = retrieve_wiki_context(
        db,
        question=req.question,
        top_k=req.top_k,
        page_ids=req.page_ids,
        window=req.window,
        max_chars=req.max_chars,
        page_limit=req.page_limit,
        embed_missing=req.embed_missing,
        search_mode=req.search_mode,
    )
    return JSONResponse(
        WikiSearchResponse(
            ok=True,
            sources=pack["sources"],
            context_chars=len(pack["context"]),
        ).model_dump()
    )


@router.post("/wiki/rag-stream")
def wiki_rag_stream(req: WikiSearchRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    pack = retrieve_wiki_context(
        db,
        question=req.question,
        top_k=req.top_k,
        page_ids=req.page_ids,
        window=req.window,
        max_chars=req.max_chars,
        page_limit=req.page_limit,
        embed_missing=req.embed_missing,
        search_mode=req.search_mode,
    )

    prompt = (
        "너는 사실 검증 보조자다.\n"
        "아래에 제공된 문맥만 사용해서 질문에 답하라.\n"
        "문맥에 없는 내용은 추측하지 말고 '근거 없음'이라고 밝혀라.\n"
        "답변은 반드시 한국어로 작성하라.\n\n"
        f"문맥:\n{pack['context']}\n\n"
        f"질문: {req.question}\n"
        "답변:"
    )

    model_name = (req.model or "").strip() or "gemma3:4b"
    ollama_payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": True,
    }

    def gen() -> Generator[bytes, None, None]:
        meta = {
            "type": "sources",
            "sources": pack["sources"],
            "meta": {
                "hits": len(pack["sources"]),
                "search_mode": req.search_mode,
                "lexical_mode": (pack.get("debug") or {}).get("lexical_mode"),
            },
        }
        yield json.dumps(meta).encode("utf-8") + b"\n"

        try:
            with requests.post(
                f"{OLLAMA_URL}/api/generate",
                json=ollama_payload,
                stream=True,
                timeout=OLLAMA_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        yield line + b"\n"
        except requests.RequestException as err:
            message = str(err)
            yield json.dumps({"error": message}).encode("utf-8") + b"\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")
