from app.core.config import get_settings
from app.services.llm.base import LLMProviderConfig
from app.services.llm.http_utils import post_json


class GeminiNativeChatClient:
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
            raise RuntimeError("Gemini API key is not configured.")
        if not resolved_model:
            raise RuntimeError("Gemini model is not configured.")

        base_url = (config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        payload = {
            "system_instruction": {
                "parts": [
                    {"text": system_prompt},
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": user_prompt},
                    ],
                }
            ],
        }
        if temperature is not None:
            payload["generationConfig"] = {"temperature": temperature}

        response = post_json(
            url=f"{base_url}/models/{resolved_model}:generateContent",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": config.api_key,
            },
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )

        candidates = response.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini response did not include candidates.")
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        texts = [str(part.get("text") or "").strip() for part in parts if isinstance(part, dict)]
        joined = "\n".join(text for text in texts if text).strip()
        if not joined:
            raise RuntimeError("Gemini response did not include text content.")
        return joined
