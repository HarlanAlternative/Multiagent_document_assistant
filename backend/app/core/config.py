from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Multi-Agent Personal Knowledge Copilot"
    api_v1_prefix: str = "/api"
    debug: bool = False

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'storage' / 'app.db').resolve().as_posix()}"
    file_storage_path: Path = BACKEND_DIR / "storage" / "uploads"
    runtime_settings_path: Path = BACKEND_DIR / "storage" / "runtime_settings.json"

    qdrant_url: str | None = None
    qdrant_collection_name: str = "document_chunks"
    qdrant_api_key: str | None = None
    qdrant_timeout_seconds: float = 5.0

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_wire_api: str = "chat_completions"
    openai_embedding_model: str | None = "text-embedding-3-large"
    aws_region: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    embedding_model: str | None = None
    bedrock_embedding_model: str | None = "amazon.titan-embed-text-v2:0"
    chat_model: str | None = None
    router_model: str | None = None
    answer_model: str | None = None
    llm_timeout_seconds: float = 30.0
    search_api_key: str | None = None
    search_provider: str = "tavily"
    search_top_k: int = 5
    search_timeout_seconds: float = 8.0

    vector_store: str = Field(
        default="qdrant",
        validation_alias=AliasChoices("VECTOR_STORE", "VECTOR_STORE_PROVIDER"),
    )
    router_provider: str = "heuristic"
    embedding_provider: str = "deterministic"
    answer_provider: str = "extractive"
    search_enabled: bool = False

    chunk_size_words: int = 220
    chunk_overlap_words: int = 40
    retrieval_top_k: int = 5
    retrieval_score_threshold: float = 0.3
    max_upload_size_mb: int = 25
    embedding_dimensions: int = 256
    default_project_name: str = "General"
    project_memory_max_chars: int = 4000
    conversation_context_char_limit: int = 6000
    conversation_recent_message_window: int = 6
    conversation_summary_target_chars: int = 1800
    retrieval_context_char_limit: int = 1200

    allowed_extensions: tuple[str, ...] = Field(default=("pdf", "pptx", "docx", "txt", "md"))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.file_storage_path.mkdir(parents=True, exist_ok=True)
    settings.runtime_settings_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
