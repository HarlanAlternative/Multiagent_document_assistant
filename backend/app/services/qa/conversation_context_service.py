import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.llm.base import LLMClient
from app.services.llm.multi_provider_client import MultiProviderChatClient
from app.utils.text import normalize_whitespace, split_sentences

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConversationContext:
    summary: str | None
    recent_messages: list[Message]
    prompt_context: str | None
    retrieval_hint: str | None


class ConversationContextService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.settings = get_settings()
        self.llm_client = llm_client or MultiProviderChatClient()

    def prepare_context(self, db: Session, conversation: Conversation) -> ConversationContext:
        ordered_messages = self._load_messages(db=db, conversation_id=conversation.id)
        summary = conversation.summary
        if self._needs_compression(summary=summary, messages=ordered_messages):
            summary = self._summarize_history(existing_summary=summary, messages=ordered_messages)
            conversation.summary = summary
            db.add(conversation)
            db.flush()

        recent_messages = ordered_messages[-self.settings.conversation_recent_message_window :]
        return ConversationContext(
            summary=summary,
            recent_messages=recent_messages,
            prompt_context=self._build_prompt_context(summary=summary, messages=recent_messages),
            retrieval_hint=self._build_retrieval_hint(summary=summary, messages=recent_messages),
        )

    def refresh_summary(self, db: Session, conversation: Conversation) -> None:
        ordered_messages = self._load_messages(db=db, conversation_id=conversation.id)
        if not self._needs_compression(summary=conversation.summary, messages=ordered_messages):
            return
        conversation.summary = self._summarize_history(existing_summary=conversation.summary, messages=ordered_messages)
        db.add(conversation)
        db.flush()

    def _needs_compression(self, summary: str | None, messages: list[Message]) -> bool:
        if len(messages) <= self.settings.conversation_recent_message_window:
            return False
        total_chars = len(summary or "") + sum(len(message.content) for message in messages)
        return total_chars > self.settings.conversation_context_char_limit

    def _summarize_history(self, existing_summary: str | None, messages: list[Message]) -> str:
        keep_count = self.settings.conversation_recent_message_window
        archived_messages = messages[:-keep_count] if len(messages) > keep_count else messages
        transcript = self._format_messages(archived_messages, max_message_chars=280)
        if not transcript:
            return (existing_summary or "").strip()

        summary = self._summarize_with_llm(existing_summary=existing_summary, transcript=transcript)
        if not summary:
            summary = self._summarize_heuristically(existing_summary=existing_summary, transcript=transcript)
        return self._trim(summary, self.settings.conversation_summary_target_chars)

    def _summarize_with_llm(self, existing_summary: str | None, transcript: str) -> str | None:
        if not self.llm_client.is_configured():
            return None
        system_prompt = (
            "You compress conversation history for a document-grounded copilot. "
            "Summarize only stable context needed for future turns. "
            "Capture user goals, important definitions, established facts, cited findings, unresolved questions, and preferences. "
            "Do not invent facts. Keep it concise plain text."
        )
        user_prompt = (
            f"Existing summary:\n{existing_summary or 'None'}\n\n"
            f"Conversation transcript to compress:\n{transcript}\n\n"
            f"Return an updated summary no longer than {self.settings.conversation_summary_target_chars} characters."
        )
        try:
            response = self.llm_client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.warning("Conversation summary compression via LLM failed: %s", exc)
            return None
        cleaned = normalize_whitespace(response)
        return cleaned or None

    def _summarize_heuristically(self, existing_summary: str | None, transcript: str) -> str:
        sentences = split_sentences(transcript.replace("User:", "User said:").replace("Assistant:", "Assistant said:"))
        selected = sentences[-8:]
        prefix = f"Earlier summary: {existing_summary}. " if existing_summary else ""
        return normalize_whitespace(f"{prefix}{' '.join(selected)}")

    def _build_prompt_context(self, summary: str | None, messages: list[Message]) -> str | None:
        parts: list[str] = []
        if summary:
            parts.append(f"Compressed conversation summary:\n{summary}")
        recent_transcript = self._format_messages(messages, max_message_chars=500)
        if recent_transcript:
            parts.append(f"Recent conversation turns:\n{recent_transcript}")
        combined = "\n\n".join(parts).strip()
        return combined or None

    def _build_retrieval_hint(self, summary: str | None, messages: list[Message]) -> str | None:
        user_turns = [message.content for message in messages if message.role == "user"]
        parts: list[str] = []
        if summary:
            parts.append(summary)
        if user_turns:
            parts.append("Recent user questions: " + " | ".join(user_turns[-3:]))
        combined = normalize_whitespace(" ".join(parts))
        if not combined:
            return None
        return self._trim(combined, self.settings.retrieval_context_char_limit)

    def _load_messages(self, db: Session, conversation_id: str) -> list[Message]:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(db.scalars(statement).all())

    def _format_messages(self, messages: list[Message], max_message_chars: int) -> str:
        lines: list[str] = []
        for message in messages:
            content = normalize_whitespace(message.content)
            if not content:
                continue
            lines.append(f"{message.role.capitalize()}: {self._trim(content, max_message_chars)}")
        return "\n".join(lines)

    def _trim(self, text: str, limit: int) -> str:
        normalized = normalize_whitespace(text)
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[: limit - 3].rstrip()}..."
