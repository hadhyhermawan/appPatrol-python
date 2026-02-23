import asyncio
from fastapi.testclient import TestClient
import uvicorn

import sys
import os

from main import app
from app.routers import izin_legacy

client = TestClient(app)

# wait actually I don't need a script, I can just modify the FastAPI exception handler
