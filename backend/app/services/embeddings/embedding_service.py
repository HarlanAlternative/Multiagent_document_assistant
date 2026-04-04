import hashlib
import math

from app.core.config import get_settings
from app.services.embeddings.bedrock_embedding_client import BedrockEmbeddingClient
from app.services.embeddings.openai_embedding_client import OpenAIEmbeddingClient
from app.services.llm.base import LLMProviderConfig
from app.services.settings.runtime_settings_service import RuntimeSettingsService
from app.utils.text import tokenize_text


class EmbeddingService:
    def __init__(self, dimensions: int | None = None) -> None:
        settings = get_settings()
        self.dimensions = dimensions or settings.embedding_dimensions
        self.runtime_settings_service = RuntimeSettingsService()
        self.bedrock_client = BedrockEmbeddingClient()
        self.openai_client = OpenAIEmbeddingClient()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        config = self._get_runtime_config()
        provider = (config.embedding_provider or "deterministic").strip().lower()
        if provider == "bedrock":
            return self.bedrock_client.embed_texts(config=config, texts=texts, dimensions=self.dimensions)
        if provider == "openai":
            return self.openai_client.embed_texts(config=config, texts=texts, dimensions=self.dimensions)
        return [self._hash_to_vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def _get_runtime_config(self) -> LLMProviderConfig:
        effective = self.runtime_settings_service.get_effective_llm_settings()
        return LLMProviderConfig(
            provider_name=effective.provider_name,
            api_key=effective.api_key,
            base_url=effective.base_url,
            wire_api=effective.wire_api,
            aws_region=effective.aws_region,
            aws_access_key_id=effective.aws_access_key_id,
            aws_secret_access_key=effective.aws_secret_access_key,
            aws_session_token=effective.aws_session_token,
            chat_model=effective.chat_model,
            embedding_provider=effective.embedding_provider,
            embedding_model=effective.embedding_model,
            router_model=effective.router_model,
            answer_model=effective.answer_model,
            router_provider=effective.router_provider,
            answer_provider=effective.answer_provider,
        )

    def _hash_to_vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = tokenize_text(text)
        if not tokens:
            tokens = [text.lower().strip() or "__empty__"]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], byteorder="big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
