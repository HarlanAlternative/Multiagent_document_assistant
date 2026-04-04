from app.services.llm.base import LLMProviderConfig
from app.services.llm.bedrock_utils import get_bedrock_client


class BedrockNativeChatClient:
    def is_configured(self, config: LLMProviderConfig, model: str | None = None) -> bool:
        return bool(config.aws_region and (model or config.chat_model))

    def complete(
        self,
        *,
        config: LLMProviderConfig,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        resolved_model = model or config.chat_model
        if not config.aws_region:
            raise RuntimeError("AWS region is not configured for Bedrock.")
        if not resolved_model:
            raise RuntimeError("Bedrock chat model is not configured.")

        client = get_bedrock_client(config, "bedrock-runtime")
        payload: dict = {
            "modelId": resolved_model,
            "system": [{"text": system_prompt}],
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": user_prompt}],
                }
            ],
        }
        inference_config: dict[str, float] = {}
        if temperature is not None:
            inference_config["temperature"] = temperature
        if inference_config:
            payload["inferenceConfig"] = inference_config

        response = client.converse(**payload)
        content = (((response or {}).get("output") or {}).get("message") or {}).get("content") or []
        texts = [str(item.get("text") or "").strip() for item in content if isinstance(item, dict) and item.get("text")]
        joined = "\n".join(text for text in texts if text).strip()
        if not joined:
            raise RuntimeError("Bedrock response did not include text content.")
        return joined
