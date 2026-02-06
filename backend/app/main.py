import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.rag import router as rag_router
from app.api.wiki import router as wiki_router
from app.api.dashboard import router as dashboard_router
from app.api.truth_check import router as truth_router
from app.api.issue_chat import router as issue_chat_router
from app.db.session import init_db

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OLaLA Backend",
    description="Fact Checking Pipeline API",
    version="1.0.0"
)

# CORS 설정
origins = [
    "http://localhost:3000",  # React
    "http://localhost:8080",  # Flutter Web
    "http://localhost",       # Nginx/Production
    "*"                       # Development convenience
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(health_router, prefix="/api/health", tags=["health"])
app.include_router(rag_router, prefix="/api/rag", tags=["rag"])
app.include_router(wiki_router, prefix="/api/wiki", tags=["wiki"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(truth_router, prefix="/api/truth", tags=["truth"])
app.include_router(issue_chat_router) # issue_chat_router file defines its own prefix

@app.on_event("startup")
def on_startup() -> None:
    logger.info("Initializing Database...")
    init_db()
    logger.info("Database Initialized.")
