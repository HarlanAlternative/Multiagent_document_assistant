from app.core.config import get_settings
from app.services.settings.runtime_settings_service import RuntimeSettingsService
from app.services.vectorstore.base import VectorStore
from app.services.vectorstore.qdrant_vector_store import QdrantVectorStore
from app.services.vectorstore.simple_vector_store import LocalVectorStore


def get_vector_store() -> VectorStore:
    settings = get_settings()
    runtime_settings = RuntimeSettingsService().get_effective_llm_settings()
    provider = (runtime_settings.vector_store or settings.vector_store).strip().lower()
    if provider == "qdrant":
        return QdrantVectorStore()
    if provider == "local":
        return LocalVectorStore()
    raise NotImplementedError(
        f"Vector store provider '{provider}' is not implemented."
    )
