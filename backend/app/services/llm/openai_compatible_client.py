import json
import logging
import time
from collections.abc import Iterable
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.services.llm.base import LLMProviderConfig
from app.services.settings.runtime_settings_service import RuntimeSettingsService

logger = logging.getLogger(__name__)


class OpenAICompatibleChatClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout_seconds = settings.llm_timeout_seconds
        self.runtime_settings_service = RuntimeSettingsService()

    def is_configured(self, model: str | None = None, config: LLMProviderConfig | None = None) -> bool:
        config = config or self._get_config()
        return bool(config.api_key and (model or config.chat_model))

    def complete(
        self,
        *,
        config: LLMProviderConfig | None = None,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        config = config or self._get_config()
        return self.complete_with_config(
            config=config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
        )

    def complete_with_config(
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
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        if not resolved_model:
            raise RuntimeError("CHAT_MODEL is not configured.")

        request_url, payload = self._build_request(
            base_url=config.base_url.rstrip("/"),
            wire_api=config.wire_api.lower().strip(),
            model=resolved_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        request = Request(
            request_url,
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
                    raw_text = response.read().decode("utf-8")
                raw_payload = json.loads(raw_text)
                break
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"LLM request failed with status {exc.code}: {body or exc.reason}") from exc
            except (URLError, JSONDecodeError, RuntimeError) as exc:
                last_error = exc
                if attempt == 2:
                    if isinstance(exc, URLError):
                        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc
                    raise RuntimeError(str(exc)) from exc
                logger.warning("LLM request attempt %s failed, retrying once: %s", attempt, exc)
                time.sleep(0.5)
        else:
            raise RuntimeError(f"LLM request failed: {last_error}")

        if config.wire_api.lower().strip() == "responses":
            text = self._extract_responses_text(raw_payload)
            if text:
                return text
            raise RuntimeError("Responses API payload did not include text content.")

        text = self._extract_chat_completions_text(raw_payload)
        if text:
            return text
        raise RuntimeError("Chat Completions payload did not include text content.")

    def _get_config(self) -> LLMProviderConfig:
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

    def _build_request(
        self,
        *,
        base_url: str,
        wire_api: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None,
    ) -> tuple[str, dict]:
        if wire_api == "responses":
            payload = {
                "model": model,
                "instructions": system_prompt,
                "input": user_prompt,
            }
            if temperature is not None:
                payload["temperature"] = temperature
            return (f"{base_url}/responses", payload)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        return (f"{base_url}/chat/completions", payload)

    def _extract_chat_completions_text(self, payload: dict) -> str | None:
        choices = payload.get("choices") or []
        if not choices:
            return None

        message = choices[0].get("message") or {}
        return self._coerce_content_to_text(message.get("content"))

    def _extract_responses_text(self, payload: dict) -> str | None:
        output_items = payload.get("output") or []
        text_parts: list[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            for content_item in item.get("content") or []:
                if not isinstance(content_item, dict):
                    continue
                if content_item.get("type") == "output_text":
                    text = str(content_item.get("text") or "").strip()
                    if text:
                        text_parts.append(text)
        joined = "\n".join(text_parts).strip()
        return joined or None

    def _coerce_content_to_text(self, content: object) -> str | None:
        if isinstance(content, str):
            return content.strip() or None
        if isinstance(content, Iterable) and not isinstance(content, (str, bytes, dict)):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = str(item.get("text") or "").strip()
                    if text:
                        text_parts.append(text)
            joined = "".join(text_parts).strip()
            return joined or None
        return None
