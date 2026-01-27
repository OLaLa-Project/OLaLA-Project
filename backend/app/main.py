from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.dashboard import router as dashboard_router
from app.api.truth_check import router as truth_router
from app.api.wiki import router as wiki_router
from app.db.init_db import init_db
from app.api.rag import router as rag_router

app = FastAPI(title="OLaLA MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(rag_router)
app.include_router(wiki_router)
app.include_router(dashboard_router)
app.include_router(truth_router)

@app.on_event("startup")
def on_startup() -> None:
    init_db()
