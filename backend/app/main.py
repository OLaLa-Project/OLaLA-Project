from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.truth_check import router as truth_router
from app.db.init_db import init_db

app = FastAPI(title="OLaLA MVP")
app.include_router(health_router)
app.include_router(truth_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
