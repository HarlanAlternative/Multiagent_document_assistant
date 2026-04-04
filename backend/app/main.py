from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.base import *  # noqa: F401,F403
from app.db.base_class import Base
from app.db.migration import run_runtime_migrations
from app.db.session import SessionLocal, engine
from app.services.projects.project_service import ProjectService
from app.services.vectorstore.factory import get_vector_store

settings = get_settings()
setup_logging(settings.debug)

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    run_runtime_migrations(engine)
    with SessionLocal() as db:
        project_service = ProjectService()
        default_project = project_service.ensure_default_project(db)
        project_service.backfill_unscoped_records(db, default_project)
    get_vector_store().ensure_collection()


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "docs_url": "/docs",
        "api_prefix": settings.api_v1_prefix,
    }
