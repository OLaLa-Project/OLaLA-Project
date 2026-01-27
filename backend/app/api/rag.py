# backend/app/api/rag.py
import json
from typing import Any, Generator, Optional
import requests
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.wiki_rag import retrieve_wiki_context

OLLAMA_URL = "http://ollama:11434"
OLLAMA_TIMEOUT = 60.0

router = APIRouter(prefix="/api")


class WikiSearchRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=50)
    page_ids: Optional[list[int]] = None
    window: int = Field(2, ge=0, le=5)
    max_chars: int = Field(4200, ge=500, le=20000)


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
    )

    prompt = (
        "You are a fact-checking assistant.\n"
        "Answer the question using only the provided context.\n\n"
        f"Context:\n{pack['context']}\n\n"
        f"Question: {req.question}\n"
        "Answer:"
    )

    ollama_payload = {
        "model": "gemma2:9b",  # change to your default
        "prompt": prompt,
        "stream": True,
    }

    def gen() -> Generator[bytes, None, None]:
        meta = {
            "type": "sources",
            "sources": pack["sources"],
            "meta": {"hits": len(pack["sources"])},
        }
        yield json.dumps(meta).encode("utf-8") + b"\n"

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

    return StreamingResponse(gen(), media_type="application/x-ndjson")
