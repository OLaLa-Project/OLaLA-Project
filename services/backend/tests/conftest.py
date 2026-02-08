from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.health import router as health_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(health_router)
    with TestClient(app) as test_client:
        yield test_client
