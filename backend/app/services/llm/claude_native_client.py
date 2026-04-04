from app.core.config import get_settings
from app.services.llm.base import LLMProviderConfig
from app.services.llm.http_utils import post_json


class ClaudeNativeChatClient:
    def __init__(self) -> None:
        self.timeout_seconds = get_settings().llm_timeout_seconds

    def is_configured(self, config: LLMProviderConfig, model: str | None = None) -> bool:
        return bool(config.api_key and (model or config.chat_model))

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
        if not config.api_key:
            raise RuntimeError("Claude API key is not configured.")
        if not resolved_model:
            raise RuntimeError("Claude model is not configured.")

        base_url = (config.base_url or "https://api.anthropic.com/v1").rstrip("/")
        payload = {
            "model": resolved_model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        }
        if temperature is not None:
            payload["temperature"] = temperature

        response = post_json(
            url=f"{base_url}/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": config.api_key,
                "anthropic-version": "2023-06-01",
            },
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )

        content = response.get("content") or []
        texts = [str(item.get("text") or "").strip() for item in content if isinstance(item, dict) and item.get("type") == "text"]
        joined = "\n".join(text for text in texts if text).strip()
        if not joined:
            raise RuntimeError("Claude response did not include text content.")
        return joined
