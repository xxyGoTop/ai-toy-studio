from fastapi import APIRouter

from app.api import generation, models, print_jobs, projects

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(projects.router)
api_router.include_router(models.router)
api_router.include_router(generation.router)
api_router.include_router(print_jobs.router)
