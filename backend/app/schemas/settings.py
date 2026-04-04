from pydantic import BaseModel, Field


class LLMSettingsRead(BaseModel):
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


class LLMSettingsUpdateRequest(BaseModel):
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


class SearchSettingsRead(BaseModel):
    search_enabled: bool
    search_provider: str
    search_api_key_masked: str | None = None


class SearchSettingsUpdateRequest(BaseModel):
    search_enabled: bool | None = None
    search_provider: str | None = None
    search_api_key: str | None = Field(default=None, min_length=10)
