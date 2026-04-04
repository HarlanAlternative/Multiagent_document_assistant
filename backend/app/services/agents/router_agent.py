import json
import logging
import re
import string
from dataclasses import dataclass

from app.core.config import get_settings
from app.schemas.chat import ChatMode
from app.services.llm.base import LLMClient
from app.services.llm.multi_provider_client import MultiProviderChatClient
from app.services.settings.runtime_settings_service import RuntimeSettingsService

TIME_SENSITIVE_PATTERN = re.compile(
    r"\b(latest|recent|recently|current|today|news|trend|trends|updated|up-to-date)\b",
    re.IGNORECASE,
)
PRIVATE_REFERENCE_PATTERN = re.compile(
    r"\b(according to|uploaded|document|documents|pdf|pptx?|slide|slides|deck|report|file|files|lecture|notes?)\b",
    re.IGNORECASE,
)
COMPARISON_PATTERN = re.compile(r"\b(compare|comparison|versus|vs\.?)\b", re.IGNORECASE)
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RouteDecision:
    route_used: str
    use_private: bool
    use_web: bool
    confidence_note: str | None = None


class RouterAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.settings = get_settings()
        self.runtime_settings_service = RuntimeSettingsService()
        self.llm_client = llm_client or MultiProviderChatClient()

    def decide(
        self,
        question: str,
        mode: ChatMode,
        conversation_context: str | None = None,
        selected_document_ids: list[str] | None = None,
    ) -> RouteDecision:
        runtime_settings = self.runtime_settings_service.get_effective_llm_settings()
        router_provider = runtime_settings.router_provider.lower().strip()
        router_model = runtime_settings.router_model or runtime_settings.chat_model or self.settings.chat_model

        if router_provider == "llm" and mode == ChatMode.AUTO:
            llm_decision = self._decide_with_llm(
                question=question,
                conversation_context=conversation_context,
                selected_document_ids=selected_document_ids or [],
                router_model=router_model,
            )
            if llm_decision is not None:
                return llm_decision

        return self._decide_with_heuristics(
            question=question,
            conversation_context=conversation_context,
            mode=mode,
            selected_document_ids=selected_document_ids or [],
        )

    def _decide_with_heuristics(
        self,
        question: str,
        conversation_context: str | None,
        mode: ChatMode,
        selected_document_ids: list[str],
    ) -> RouteDecision:
        question_for_routing = f"{conversation_context}\n\n{question}" if conversation_context else question
        if mode == ChatMode.PRIVATE_ONLY:
            return RouteDecision(route_used=ChatMode.PRIVATE_ONLY.value, use_private=True, use_web=False)

        if mode == ChatMode.PRIVATE_PLUS_WEB:
            return RouteDecision(
                route_used=ChatMode.PRIVATE_PLUS_WEB.value,
                use_private=True,
                use_web=True,
            )

        if mode == ChatMode.WEB_ONLY:
            return RouteDecision(route_used=ChatMode.WEB_ONLY.value, use_private=False, use_web=True)

        references_private_docs = bool(selected_document_ids) or bool(PRIVATE_REFERENCE_PATTERN.search(question_for_routing))
        is_time_sensitive = bool(TIME_SENSITIVE_PATTERN.search(question_for_routing))
        is_comparison = bool(COMPARISON_PATTERN.search(question_for_routing))

        if is_comparison and references_private_docs:
            return RouteDecision(
                route_used=ChatMode.PRIVATE_PLUS_WEB.value,
                use_private=True,
                use_web=True,
                confidence_note="Auto mode combined uploaded documents with web search for a comparison-style question.",
            )

        if is_time_sensitive and references_private_docs:
            return RouteDecision(
                route_used=ChatMode.PRIVATE_PLUS_WEB.value,
                use_private=True,
                use_web=True,
                confidence_note="Auto mode used uploaded documents plus web search because the question appears time-sensitive.",
            )

        if is_time_sensitive:
            return RouteDecision(
                route_used=ChatMode.WEB_ONLY.value,
                use_private=False,
                use_web=True,
                confidence_note="Auto mode chose web search because the question appears time-sensitive.",
            )

        return RouteDecision(route_used=ChatMode.PRIVATE_ONLY.value, use_private=True, use_web=False)

    def _decide_with_llm(
        self,
        question: str,
        conversation_context: str | None,
        selected_document_ids: list[str],
        router_model: str | None,
    ) -> RouteDecision | None:
        if not self.llm_client.is_configured(model=router_model):
            logger.warning("Router provider is set to llm, but LLM client is not fully configured. Falling back to heuristics.")
            return None

        system_prompt = (
            "You are a routing agent for a knowledge copilot. "
            "Choose exactly one route for the user question. "
            "Available routes: private_only, private_plus_web, web_only. "
            "Prefer private_only when uploaded documents are likely sufficient. "
            "Prefer private_plus_web when the question references uploaded documents and also asks for current or comparative information. "
            "Prefer web_only when the question is about current external information and does not depend on uploaded documents. "
            "A selected document count of 0 only means there is no explicit filter; the system can still search across uploaded documents. "
            "Return strict JSON with keys: route_used, use_private, use_web, confidence_note."
        )
        user_prompt = (
            f"Question: {question}\n"
            f"Selected document count: {len(selected_document_ids)}\n"
            f"Conversation context: {conversation_context or 'None'}\n"
            "Interpret selected document count as an optional filter count, not as the total number of uploaded documents.\n"
            "Return JSON only."
        )
        try:
            raw_response = self.llm_client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=router_model,
            )
            payload = self._parse_json_object(raw_response)
            route_used = str(payload.get("route_used") or "").strip()
            if route_used not in {
                ChatMode.PRIVATE_ONLY.value,
                ChatMode.PRIVATE_PLUS_WEB.value,
                ChatMode.WEB_ONLY.value,
            }:
                raise ValueError(f"Unsupported route_used={route_used!r}")
            return RouteDecision(
                route_used=route_used,
                use_private=bool(payload.get("use_private")),
                use_web=bool(payload.get("use_web")),
                confidence_note=self._normalize_confidence_note(
                    raw_note=(str(payload.get("confidence_note")).strip() if payload.get("confidence_note") else None),
                    route_used=route_used,
                ),
            )
        except Exception as exc:
            logger.warning("LLM router failed, falling back to heuristics: %s", exc)
            return None

    def _parse_json_object(self, content: str) -> dict:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                stripped = "\n".join(lines[1:-1]).strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in LLM router response.")
        return json.loads(stripped[start : end + 1])

    def _normalize_confidence_note(self, raw_note: str | None, route_used: str) -> str:
        if raw_note:
            sanitized = "".join(char for char in raw_note if char in string.printable).strip()
            sanitized = re.sub(r"\s+", " ", sanitized)
            if sanitized and len(sanitized) <= 180:
                return sanitized

        if route_used == ChatMode.PRIVATE_ONLY.value:
            return "Auto mode chose uploaded documents only because the question appears answerable from private sources."
        if route_used == ChatMode.PRIVATE_PLUS_WEB.value:
            return "Auto mode combined uploaded documents with web search because the question appears to need both private and current context."
        return "Auto mode chose web search because the question appears to depend on current external information."
