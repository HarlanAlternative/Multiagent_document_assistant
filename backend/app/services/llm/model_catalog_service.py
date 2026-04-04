from app.core.config import get_settings


class ModelCatalogService:
    def __init__(self) -> None:
        self.timeout_seconds = get_settings().llm_timeout_seconds

    def list_models(
        self,
        *,
        provider_name: str,
        api_key: str | None,
        base_url: str | None = None,
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
    ) -> list[str]:
        normalized = provider_name.strip().lower()
        if normalized == "bedrock":
            return self._list_bedrock_models(
                aws_region=aws_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
            )
        if normalized == "gemini":
            return self._list_gemini_models(api_key=api_key or "", base_url=base_url)
        if normalized == "claude":
            return self._list_claude_models(api_key=api_key or "", base_url=base_url)
        return self._list_openai_compatible_models(api_key=api_key or "", base_url=base_url)

    def _list_openai_compatible_models(self, *, api_key: str, base_url: str | None) -> list[str]:
        from urllib.request import Request, urlopen
        import json

        request = Request(
            f"{(base_url or 'https://api.openai.com/v1').rstrip('/')}/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") or []
        models = sorted(
            {
                str(item.get("id")).strip()
                for item in data
                if isinstance(item, dict) and item.get("id")
            }
        )
        return models

    def _list_gemini_models(self, *, api_key: str, base_url: str | None) -> list[str]:
        from urllib.request import Request, urlopen
        import json
        from urllib.parse import urlencode

        root = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        query = urlencode({"key": api_key, "pageSize": 100})
        request = Request(f"{root}/models?{query}", method="GET")
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = []
        for item in payload.get("models") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            supported = item.get("supportedGenerationMethods") or []
            if "generateContent" not in supported:
                continue
            models.append(name.split("/", 1)[-1] if "/" in name else name)
        return sorted(set(model for model in models if model))

    def _list_claude_models(self, *, api_key: str, base_url: str | None) -> list[str]:
        from urllib.request import Request, urlopen
        import json

        request = Request(
            f"{(base_url or 'https://api.anthropic.com/v1').rstrip('/')}/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") or []
        models = sorted(
            {
                str(item.get("id")).strip()
                for item in data
                if isinstance(item, dict) and item.get("id")
            }
        )
        return models

    def _list_bedrock_models(
        self,
        *,
        aws_region: str | None,
        aws_access_key_id: str | None,
        aws_secret_access_key: str | None,
        aws_session_token: str | None,
    ) -> list[str]:
        if not aws_region:
            raise RuntimeError("AWS region is required to load Bedrock models.")
        from app.services.llm.bedrock_utils import get_bedrock_client
        from app.services.llm.base import LLMProviderConfig

        config = LLMProviderConfig(
            provider_name="bedrock",
            api_key=None,
            base_url="",
            wire_api="bedrock",
            aws_region=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            chat_model=None,
            embedding_provider="bedrock",
            embedding_model=None,
            router_model=None,
            answer_model=None,
            router_provider="llm",
            answer_provider="llm",
        )
        client = get_bedrock_client(config, "bedrock")
        response = client.list_foundation_models(byOutputModality="TEXT")
        summaries = response.get("modelSummaries") or []
        models = [
            str(item.get("modelId") or "").strip()
            for item in summaries
            if isinstance(item, dict) and item.get("modelId")
        ]
        return sorted(set(model for model in models if model))
