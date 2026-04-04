from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.services.projects.project_service import ProjectService
from app.services.settings.runtime_settings_service import RuntimeSettingsService

router = APIRouter()
runtime_settings_service = RuntimeSettingsService()
project_service = ProjectService()


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    settings = get_settings()
    llm_settings = runtime_settings_service.get_effective_llm_settings()
    search_settings = runtime_settings_service.get_effective_search_settings()
    projects = project_service.list_projects(db=db)
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "vector_store": llm_settings.vector_store,
        "embedding_provider": llm_settings.embedding_provider,
        "router_provider": llm_settings.router_provider,
        "answer_provider": llm_settings.answer_provider,
        "chat_model": llm_settings.chat_model,
        "llm_configured": llm_settings.is_configured,
        "search_enabled": search_settings.search_enabled,
        "search_provider": search_settings.search_provider,
        "project_count": len(projects),
    }
