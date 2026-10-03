import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, Field

from app.core.config import get_settings


class RuntimeLLMSettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, min_length=10)
    provider_name: str | None = None
    base_url: str | None = None
    wire_api: str | None = None
    aws_region: str | None = None
    aws_access_key_id: str | None = Field(default=None, min_length=4)
    aws_secret_access_key: str | None = Field(default=None, min_length=8)
    aws_session_token: str | None = Field(default=None, min_length=8)
    embedding_provider: str | None = None
    embedding_model: str | None = None
    vector_store: str | None = None
    chat_model: str | None = None
    router_model: str | None = None
    answer_model: str | None = None
    router_provider: str | None = None
    answer_provider: str | None = None


class RuntimeSearchSettingsUpdate(BaseModel):
    search_enabled: bool | None = None
    search_provider: str | None = None
    search_api_key: str | None = Field(default=None, min_length=10)


class RuntimeLLMSettingsSnapshot(BaseModel):
    is_configured: bool
    provider_name: str | None = None
    api_key_masked: str | None = None
    base_url: str
    wire_api: str
    aws_region: str | None = None
    aws_access_key_id_masked: str | None = None
    aws_secret_access_key_masked: str | None = None
    aws_session_token_masked: str | None = None
    embedding_provider: str
    embedding_model: str | None = None
    vector_store: str
    chat_model: str | None = None
    router_model: str | None = None
    answer_model: str | None = None
    router_provider: str
    answer_provider: str


class RuntimeSearchSettingsSnapshot(BaseModel):
    search_enabled: bool
    search_provider: str
    search_api_key_masked: str | None = None


@dataclass(slots=True)
class EffectiveLLMSettings:
    api_key: str | None
    provider_name: str | None
    base_url: str
    wire_api: str
    aws_region: str | None
    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    aws_session_token: str | None
    embedding_provider: str
    embedding_model: str | None
    vector_store: str
    chat_model: str | None
    router_model: str | None
    answer_model: str | None
    router_provider: str
    answer_provider: str

    @property
    def is_configured(self) -> bool:
        normalized_provider = (self.provider_name or "openai").strip().lower()
        if normalized_provider == "bedrock":
            return bool(self.aws_region and self.chat_model)
        return bool(self.api_key and self.chat_model)


@dataclass(slots=True)
class EffectiveSearchSettings:
    search_enabled: bool
    search_provider: str
    search_api_key: str | None


class RuntimeSettingsService:
    def __init__(self) -> None:
        settings = get_settings()
        self.path = Path(settings.runtime_settings_path)

    def get_effective_llm_settings(self) -> EffectiveLLMSettings:
        settings = get_settings()
        stored = self._read_data()
        provider_name = str(stored.get("provider_name") or "openai").strip().lower()
        default_base_url = "bedrock://native" if provider_name == "bedrock" else settings.openai_base_url
        embedding_provider = (stored.get("embedding_provider") or settings.embedding_provider).strip().lower()
        return EffectiveLLMSettings(
            api_key=stored.get("api_key"),
            provider_name=provider_name,
            base_url=str(stored.get("base_url") or default_base_url),
            wire_api=(stored.get("wire_api") or settings.openai_wire_api).strip(),
            aws_region=stored.get("aws_region") or settings.aws_region,
            aws_access_key_id=stored.get("aws_access_key_id") or settings.aws_access_key_id,
            aws_secret_access_key=stored.get("aws_secret_access_key") or settings.aws_secret_access_key,
            aws_session_token=stored.get("aws_session_token") or settings.aws_session_token,
            embedding_provider=embedding_provider,
            embedding_model=stored.get("embedding_model") or self._default_embedding_model(embedding_provider),
            vector_store=(stored.get("vector_store") or settings.vector_store).strip().lower(),
            chat_model=stored.get("chat_model") or settings.chat_model,
            router_model=stored.get("router_model") or settings.router_model,
            answer_model=stored.get("answer_model") or settings.answer_model,
            router_provider=(stored.get("router_provider") or settings.router_provider).strip(),
            answer_provider=(stored.get("answer_provider") or settings.answer_provider).strip(),
        )

    def get_snapshot(self) -> RuntimeLLMSettingsSnapshot:
        effective = self.get_effective_llm_settings()
        return RuntimeLLMSettingsSnapshot(
            is_configured=effective.is_configured,
            provider_name=effective.provider_name,
            api_key_masked=self._mask_api_key(effective.api_key),
            base_url=effective.base_url,
            wire_api=effective.wire_api,
            aws_region=effective.aws_region,
            aws_access_key_id_masked=self._mask_api_key(effective.aws_access_key_id),
            aws_secret_access_key_masked=self._mask_api_key(effective.aws_secret_access_key),
            aws_session_token_masked=self._mask_api_key(effective.aws_session_token),
            embedding_provider=effective.embedding_provider,
            embedding_model=effective.embedding_model,
            vector_store=effective.vector_store,
            chat_model=effective.chat_model,
            router_model=effective.router_model or effective.chat_model,
            answer_model=effective.answer_model or effective.chat_model,
            router_provider=effective.router_provider,
            answer_provider=effective.answer_provider,
        )

    def get_effective_search_settings(self) -> EffectiveSearchSettings:
        settings = get_settings()
        stored = self._read_data()
        raw_enabled = stored.get("search_enabled")
        if isinstance(raw_enabled, bool):
            search_enabled = raw_enabled
        elif isinstance(raw_enabled, str):
            search_enabled = raw_enabled.strip().lower() in {"1", "true", "yes", "on"}
        else:
            search_enabled = settings.search_enabled

        return EffectiveSearchSettings(
            search_enabled=search_enabled,
            search_provider=(stored.get("search_provider") or settings.search_provider).strip().lower(),
            search_api_key=stored.get("search_api_key") or settings.search_api_key,
        )

    def get_search_snapshot(self) -> RuntimeSearchSettingsSnapshot:
        effective = self.get_effective_search_settings()
        return RuntimeSearchSettingsSnapshot(
            search_enabled=effective.search_enabled,
            search_provider=effective.search_provider,
            search_api_key_masked=self._mask_api_key(effective.search_api_key),
        )

    def update_llm_settings(self, payload: RuntimeLLMSettingsUpdate) -> RuntimeLLMSettingsSnapshot:
        current = self._read_data()
        normalized_provider = (payload.provider_name or current.get("provider_name") or "openai").strip().lower()
        default_base_url = "bedrock://native" if normalized_provider == "bedrock" else "https://api.openai.com/v1"
        embedding_provider = (payload.embedding_provider or current.get("embedding_provider") or get_settings().embedding_provider).strip().lower()
        embedding_model = self._resolve_embedding_model(payload=payload, current=current, embedding_provider=embedding_provider)
        if payload.api_key:
            current["api_key"] = payload.api_key.strip()
        if payload.aws_access_key_id:
            current["aws_access_key_id"] = payload.aws_access_key_id.strip()
        if payload.aws_secret_access_key:
            current["aws_secret_access_key"] = payload.aws_secret_access_key.strip()
        if payload.aws_session_token:
            current["aws_session_token"] = payload.aws_session_token.strip()
        current.update(
            {
                "provider_name": normalized_provider,
                "base_url": str(payload.base_url if payload.base_url is not None else current.get("base_url") or default_base_url).strip(),
                "wire_api": (payload.wire_api if payload.wire_api is not None else current.get("wire_api") or "responses").strip(),
                "aws_region": (payload.aws_region or current.get("aws_region") or get_settings().aws_region or "us-east-1").strip(),
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "vector_store": (payload.vector_store or current.get("vector_store") or get_settings().vector_store).strip().lower(),
                "chat_model": (payload.chat_model or current.get("chat_model") or "gpt-5-mini").strip(),
                "router_model": (payload.router_model or payload.chat_model or current.get("router_model") or current.get("chat_model") or "gpt-5-mini").strip(),
                "answer_model": (payload.answer_model or payload.chat_model or current.get("answer_model") or current.get("chat_model") or "gpt-5-mini").strip(),
                "router_provider": (payload.router_provider or "llm").strip(),
                "answer_provider": (payload.answer_provider or "llm").strip(),
            }
        )
        self._write_data(current)
        return self.get_snapshot()

    def update_search_settings(self, payload: RuntimeSearchSettingsUpdate) -> RuntimeSearchSettingsSnapshot:
        current = self._read_data()
        if payload.search_api_key:
            current["search_api_key"] = payload.search_api_key.strip()
        if payload.search_enabled is not None:
            current["search_enabled"] = payload.search_enabled
        current["search_provider"] = (payload.search_provider or current.get("search_provider") or "duckduckgo").strip().lower()
        self._write_data(current)
        return self.get_search_snapshot()

    def _read_data(self) -> dict[str, object]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_data(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
            temp_path = Path(handle.name)
        temp_path.replace(self.path)

    def _mask_api_key(self, api_key: str | None) -> str | None:
        if not api_key:
            return None
        if len(api_key) <= 8:
            return "*" * len(api_key)
        return f"{api_key[:6]}...{api_key[-4:]}"

    def _default_embedding_model(self, embedding_provider: str) -> str | None:
        settings = get_settings()
        if embedding_provider == "bedrock":
            return settings.bedrock_embedding_model or settings.embedding_model
        if embedding_provider == "openai":
            return settings.openai_embedding_model or settings.embedding_model
        if embedding_provider == "local":
            return settings.local_embedding_model
        return settings.embedding_model

    def _resolve_embedding_model(
        self,
        *,
        payload: RuntimeLLMSettingsUpdate,
        current: dict[str, object],
        embedding_provider: str,
    ) -> str | None:
        if payload.embedding_model is not None:
            normalized = payload.embedding_model.strip()
            return normalized or None

        current_model = current.get("embedding_model")
        if isinstance(current_model, str) and current_model.strip():
            return current_model.strip()

        return self._default_embedding_model(embedding_provider)
