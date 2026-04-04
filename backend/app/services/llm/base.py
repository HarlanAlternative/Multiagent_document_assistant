from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class LLMProviderConfig:
    provider_name: str | None
    api_key: str | None
    base_url: str
    wire_api: str
    aws_region: str | None
    aws_access_key_id: str | None
    aws_secret_access_key: str | None
    aws_session_token: str | None
    chat_model: str | None
    embedding_provider: str | None
    embedding_model: str | None
    router_model: str | None
    answer_model: str | None
    router_provider: str
    answer_provider: str


class LLMClient(Protocol):
    def is_configured(self, model: str | None = None) -> bool:
        ...

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        ...
