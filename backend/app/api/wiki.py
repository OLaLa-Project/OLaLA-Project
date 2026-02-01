# backend/app/api/wiki.py
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.wiki_schemas import WikiSearchRequest, WikiSearchResponse
from app.gateway.database.repos.wiki_repo import WikiRepository
from app.db.session import get_db
from app.services.wiki_usecase import retrieve_wiki_hits

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


@router.post("/search", response_model=WikiSearchResponse)
def wiki_search(req: WikiSearchRequest, db: Session = Depends(get_db)):
    data = retrieve_wiki_hits(
        db,
        question=req.question,
        top_k=req.top_k,
        window=req.window,
        page_limit=req.page_limit,
        embed_missing=req.embed_missing,
        max_chars=req.max_chars,
        page_ids=req.page_ids,
        search_mode=req.search_mode,
    )
    return {
        "question": req.question,
        "candidates": data["candidates"],
        "hits": data["hits"],
        "updated_embeddings": data.get("updated_embeddings"),
        "debug": data.get("debug"),
        "prompt_context": data.get("prompt_context"),
    }


class KeywordSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(12, ge=1, le=50)


class KeywordHit(BaseModel):
    page_id: int
    title: str


class KeywordSearchResponse(BaseModel):
    query: str
    hits: list[KeywordHit]


@router.post("/keyword-search", response_model=KeywordSearchResponse)
def keyword_search(req: KeywordSearchRequest, db: Session = Depends(get_db)):
    repo = WikiRepository(db)
    keywords = [segment.strip() for segment in req.query.split() if segment.strip()]
    if len(keywords) <= 1:
        rows = repo.find_pages_by_title_ilike(req.query, limit=req.limit)
    else:
        rows = repo.find_pages_by_any_keyword(keywords, limit=req.limit)

    hits = [{"page_id": pid, "title": title} for pid, title in rows]
    return {"query": req.query, "hits": hits}
