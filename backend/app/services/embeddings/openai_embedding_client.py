import json
import logging
import time
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.services.llm.base import LLMProviderConfig

logger = logging.getLogger(__name__)


class OpenAIEmbeddingClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout_seconds = settings.llm_timeout_seconds

    def embed_texts(self, *, config: LLMProviderConfig, texts: list[str], dimensions: int | None = None) -> list[list[float]]:
        if not config.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured for embeddings.")
        if not config.embedding_model:
            raise RuntimeError("Embedding model is not configured.")
        if not texts:
            return []

        try:
            return self._request_embeddings(config=config, texts=texts, dimensions=dimensions)
        except RuntimeError as exc:
            if dimensions and "dimensions" in str(exc).lower():
                logger.warning("Embedding provider rejected custom dimensions; retrying without dimensions: %s", exc)
                return self._request_embeddings(config=config, texts=texts, dimensions=None)
            raise

    def _request_embeddings(
        self,
        *,
        config: LLMProviderConfig,
        texts: list[str],
        dimensions: int | None,
    ) -> list[list[float]]:
        payload: dict[str, object] = {
            "model": config.embedding_model,
            "input": texts,
        }
        if dimensions and self._supports_dimensions(config.embedding_model):
            payload["dimensions"] = dimensions

        request = Request(
            f"{config.base_url.rstrip('/')}/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        last_error: Exception | None = None
        for attempt in range(1, 3):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    raw_payload = json.loads(response.read().decode("utf-8"))
                break
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"Embedding request failed with status {exc.code}: {body or exc.reason}") from exc
            except (URLError, JSONDecodeError) as exc:
                last_error = exc
                if attempt == 2:
                    if isinstance(exc, URLError):
                        raise RuntimeError(f"Embedding request failed: {exc.reason}") from exc
                    raise RuntimeError(str(exc)) from exc
                logger.warning("Embedding request attempt %s failed, retrying once: %s", attempt, exc)
                time.sleep(0.5)
        else:
            raise RuntimeError(f"Embedding request failed: {last_error}")

        data = raw_payload.get("data")
        if not isinstance(data, list) or not data:
            raise RuntimeError("Embedding response did not include any vectors.")

        ordered = sorted(
            (
                item
                for item in data
                if isinstance(item, dict) and isinstance(item.get("embedding"), list) and isinstance(item.get("index"), int)
            ),
            key=lambda item: int(item["index"]),
        )
        if len(ordered) != len(texts):
            raise RuntimeError("Embedding response size did not match request size.")

        vectors = [[float(value) for value in item["embedding"]] for item in ordered]
        if dimensions and any(len(vector) != dimensions for vector in vectors):
            raise RuntimeError("Embedding vector dimension mismatch.")
        return vectors

    def _supports_dimensions(self, model: str | None) -> bool:
        normalized = (model or "").strip().lower()
        return normalized.startswith("text-embedding-3")
