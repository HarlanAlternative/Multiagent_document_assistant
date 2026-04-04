from app.services.llm.base import LLMProviderConfig
from app.services.llm.bedrock_native_client import BedrockNativeChatClient
from app.services.llm.claude_native_client import ClaudeNativeChatClient
from app.services.llm.gemini_native_client import GeminiNativeChatClient
from app.services.llm.openai_compatible_client import OpenAICompatibleChatClient
from app.services.settings.runtime_settings_service import RuntimeSettingsService


class MultiProviderChatClient:
    def __init__(self) -> None:
        self.runtime_settings_service = RuntimeSettingsService()
        self.openai_compatible_client = OpenAICompatibleChatClient()
        self.gemini_client = GeminiNativeChatClient()
        self.claude_client = ClaudeNativeChatClient()
        self.bedrock_client = BedrockNativeChatClient()

    def is_configured(self, model: str | None = None) -> bool:
        config = self._get_config()
        provider = self._get_provider_client(config.provider_name)
        return provider.is_configured(config=config, model=model)

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        config = self._get_config()
        provider = self._get_provider_client(config.provider_name)
        return provider.complete(
            config=config,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
        )

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

    def _get_provider_client(self, provider_name: str | None):
        normalized = (provider_name or "openai").strip().lower()
        if normalized == "bedrock":
            return self.bedrock_client
        if normalized == "gemini":
            return self.gemini_client
        if normalized == "claude":
            return self.claude_client
        return self.openai_compatible_client
