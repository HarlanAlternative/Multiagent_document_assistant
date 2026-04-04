import json

from app.services.llm.base import LLMProviderConfig
from app.services.llm.bedrock_utils import get_bedrock_client


class BedrockEmbeddingClient:
    def embed_texts(self, *, config: LLMProviderConfig, texts: list[str], dimensions: int) -> list[list[float]]:
        if not config.aws_region:
            raise RuntimeError("AWS region is not configured for Bedrock embeddings.")
        model_id = config.embedding_model
        if not model_id:
            raise RuntimeError("Bedrock embedding model is not configured.")

        client = get_bedrock_client(config, "bedrock-runtime")
        embeddings: list[list[float]] = []
        for text in texts:
            body = {
                "inputText": text,
                "dimensions": dimensions,
                "normalize": True,
            }
            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(response["body"].read().decode("utf-8"))
            vector = payload.get("embedding") or payload.get("embeddings")
            if not isinstance(vector, list):
                raise RuntimeError("Bedrock embedding response did not include an embedding vector.")
            embeddings.append([float(value) for value in vector])
        return embeddings
