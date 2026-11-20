from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api import api_router
from app.config import get_settings
from app.db import init_db

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    settings.ensure_storage()
    init_db()


@app.get("/api/health")
def health():
    blender = Path(settings.blender_executable)
    return {
        "status": "ok",
        "app": settings.app_name,
        "blender_executable": str(blender),
        "blender_exists": blender.exists(),
        "ai_provider": settings.ai_provider,
        "storage_root": str(settings.storage_root),
    }


app.include_router(api_router)
app.mount(
    "/storage",
    StaticFiles(directory=str(settings.storage_root)),
    name="storage",
)
