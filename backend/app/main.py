from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.dashboard import router as dashboard_router
from app.api.truth_check import router as truth_router
from app.api.wiki import router as wiki_router
from app.db.init_db import init_db
from app.api.rag import router as rag_router
from app.core.settings import settings

app = FastAPI(title="OLaLA MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse
import logging

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.error(f"Validation Error: {exc.errors()}")
    logging.error(f"Body: {exc.body}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)},
    )

app.include_router(health_router)
app.include_router(rag_router)
app.include_router(wiki_router)
app.include_router(dashboard_router)
app.include_router(truth_router)

@app.on_event("startup")
def on_startup() -> None:
    init_db()
    
    # Model warm-up to prevent first-request timeouts
    import logging
    from app.stages._shared.slm_client import call_slm1
    from app.orchestrator.embedding.client import embed_texts
    
    logger = logging.getLogger(__name__)
    
    # Warm up SLM (Ollama)
    try:
        logger.info("🔥 Warming up SLM model...")
        call_slm1(
            system_prompt="You are a helpful assistant.",
            user_prompt="Hello",
        )
        logger.info("✅ SLM model ready")
    except Exception as e:
        logger.warning(f"⚠️  SLM warm-up failed (will retry on first request): {e}")
    
    # Warm up Embedding model
    try:
        logger.info("🔥 Warming up embedding model...")
        embed_texts(["테스트"])
        logger.info("✅ Embedding model ready")
    except Exception as e:
        logger.warning(f"⚠️  Embedding warm-up failed (will retry on first request): {e}")
