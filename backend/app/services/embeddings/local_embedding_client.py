import threading
from typing import Any

from app.core.config import get_settings
from app.services.llm.base import LLMProviderConfig

# Prefixes the models were trained with. fastembed does not add them, so they are applied here.
QUERY_AND_PASSAGE_PREFIXES = {
    "intfloat/multilingual-e5": ("query: ", "passage: "),
    "Qwen/Qwen3-Embedding": ("Instruct: Given a question, retrieve passages that answer the question\nQuery:", ""),
    "google/embeddinggemma": ("task: search result | query: ", "title: none | text: "),
}


class LocalEmbeddingClient:
    """Runs a fastembed (ONNX) model on this machine. The model is downloaded on first use."""

    _models: dict[str, Any] = {}
    _dimensions: dict[str, int] = {}
    _lock = threading.Lock()

    def embed_texts(self, *, config: LLMProviderConfig, texts: list[str], is_query: bool = False) -> list[list[float]]:
        if not texts:
            return []
        model_name = self.model_name(config)
        query_prefix, passage_prefix = next(
            (prefixes for key, prefixes in QUERY_AND_PASSAGE_PREFIXES.items() if model_name.startswith(key)),
            ("", ""),
        )
        prefix = query_prefix if is_query else passage_prefix
        model = self._load(model_name)
        return [vector.tolist() for vector in model.embed([f"{prefix}{text}" for text in texts])]

    def dimension(self, config: LLMProviderConfig) -> int:
        model_name = self.model_name(config)
        if model_name not in self._dimensions:
            TextEmbedding = self._text_embedding_class()
            description = next(
                (model for model in TextEmbedding.list_supported_models() if model["model"] == model_name),
                None,
            )
            if description is None:
                raise RuntimeError(f"fastembed does not support the embedding model {model_name!r}.")
            self._dimensions[model_name] = int(description["dim"])
        return self._dimensions[model_name]

    def model_name(self, config: LLMProviderConfig) -> str:
        return (config.embedding_model or get_settings().local_embedding_model).strip()

    def _load(self, model_name: str) -> Any:
        with self._lock:
            if model_name not in self._models:
                settings = get_settings()
                settings.local_embedding_cache_dir.mkdir(parents=True, exist_ok=True)
                TextEmbedding = self._text_embedding_class()
                self._models[model_name] = TextEmbedding(
                    model_name=model_name,
                    cache_dir=str(settings.local_embedding_cache_dir),
                )
            return self._models[model_name]

    def _text_embedding_class(self) -> Any:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError("Local embeddings need the fastembed package: pip install fastembed") from exc
        return TextEmbedding
