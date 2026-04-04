from pydantic import BaseModel, Field


class ModelCatalogRequest(BaseModel):
    provider_name: str = Field(min_length=1)
    api_key: str | None = Field(default=None, min_length=4)
    base_url: str | None = None
    aws_region: str | None = None
    aws_access_key_id: str | None = Field(default=None, min_length=4)
    aws_secret_access_key: str | None = Field(default=None, min_length=8)
    aws_session_token: str | None = Field(default=None, min_length=8)


class ModelCatalogResponse(BaseModel):
    items: list[str] = Field(default_factory=list)
