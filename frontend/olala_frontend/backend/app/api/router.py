from fastapi import APIRouter

from .routes.chat import router as chat_router
from .routes.health import router as health_router
from .routes.issues import router as issues_router
from .routes.verify import router as verify_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(issues_router)
api_router.include_router(chat_router)
api_router.include_router(verify_router)
