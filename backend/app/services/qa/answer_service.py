import logging

from app.core.config import get_settings
from app.schemas.chat import RetrievedChunkRead, WebSearchResultRead
from app.services.llm.base import LLMClient
from app.services.llm.multi_provider_client import MultiProviderChatClient
from app.services.settings.runtime_settings_service import RuntimeSettingsService
from app.utils.text import extract_keywords, split_sentences, unique_preserve_order

logger = logging.getLogger(__name__)


class AnswerService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.settings = get_settings()
        self.runtime_settings_service = RuntimeSettingsService()
        self.llm_client = llm_client or MultiProviderChatClient()

    def generate(
        self,
        question: str,
        retrieved_chunks: list[RetrievedChunkRead],
        web_results: list[WebSearchResultRead],
        project_memory: str | None = None,
        conversation_context: str | None = None,
    ) -> tuple[str, str | None]:
        runtime_settings = self.runtime_settings_service.get_effective_llm_settings()
        answer_provider = runtime_settings.answer_provider.lower().strip()
        answer_model = runtime_settings.answer_model or runtime_settings.chat_model or self.settings.chat_model

        if answer_provider == "llm":
            llm_answer = self._generate_with_llm(
                question=question,
                retrieved_chunks=retrieved_chunks,
                web_results=web_results,
                project_memory=project_memory,
                conversation_context=conversation_context,
                answer_model=answer_model,
            )
            if llm_answer is not None:
                return llm_answer

        internal_summary = self._summarize_internal(question=question, retrieved_chunks=retrieved_chunks)
        external_summary = self._summarize_web(question=question, web_results=web_results)

        if not internal_summary and not external_summary:
            return (
                "I do not have sufficient information in the available sources to answer this question.",
                "No relevant information found in selected documents or external web results.",
            )

        sections: list[str] = []
        if internal_summary:
            sections.append(f"From uploaded documents:\n{internal_summary}")
        if external_summary:
            sections.append(f"From web search:\n{external_summary}")

        answer = "\n\n".join(sections) if len(sections) > 1 else sections[0].split("\n", 1)[1]
        if len(answer) > 1200:
            answer = f"{answer[:1197].rstrip()}..."

        if internal_summary and external_summary:
            return answer, "Answer synthesized from private-document and external web evidence."
        if internal_summary:
            return answer, "Answer synthesized from retrieved private-document evidence."
        return answer, "Answer synthesized from external web evidence."

    def _generate_with_llm(
        self,
        question: str,
        retrieved_chunks: list[RetrievedChunkRead],
        web_results: list[WebSearchResultRead],
        project_memory: str | None,
        conversation_context: str | None,
        answer_model: str | None,
    ) -> tuple[str, str | None] | None:
        if not retrieved_chunks and not web_results:
            return (
                "I do not have sufficient information in the available sources to answer this question.",
                "No relevant information found in selected documents or external web results.",
            )
        if not self.llm_client.is_configured(model=answer_model):
            logger.warning("Answer provider is set to llm, but LLM client is not fully configured. Falling back to extractive synthesis.")
            return None

        system_prompt = (
            "You are the answer synthesis agent for a grounded knowledge copilot. "
            "Answer only from the provided evidence. "
            "Do not invent facts. "
            "If the evidence is insufficient, say that you do not have sufficient information. "
            "When both private documents and web results are present, clearly distinguish them. "
            "Do not mention a source type that was not provided. "
            "Ignore tangential evidence even if it shares keywords with the question. "
            "Only include claims that are explicitly supported by the supplied evidence. "
            "If the evidence contains numbered or bulleted lists, preserve all explicit items that answer the question. "
            "If the user asks for a mathematical form or formula, prefer the most general and equation-rich representation in the evidence over a narrow example slide. "
            "When citing a formula or test statistic, copy it only if it is clearly readable in the evidence. "
            "If the notation is garbled, explain it in words instead of reproducing broken math. "
            "When a formula is important and readable, render it as LaTeX display math using $$ on separate lines. "
            "Keep prose outside the $$ blocks. "
            "Example: $$ Y \\sim Normal(\\mu, \\sigma^2 I_n) $$"
        )
        evidence_sections: list[str] = []
        if retrieved_chunks:
            evidence_sections.append(f"Private document evidence:\n{self._format_internal_evidence(retrieved_chunks)}")
        if web_results:
            evidence_sections.append(f"Web evidence:\n{self._format_web_evidence(web_results)}")
        if conversation_context and conversation_context.strip():
            evidence_sections.append(
                "Conversation context (context only, do not treat this as a citable source):\n"
                f"{conversation_context.strip()}"
            )
        user_prompt = (
            f"Question:\n{question}\n\n"
            f"{'\n\n'.join(evidence_sections)}\n\n"
            "Write a concise answer. "
            "If some evidence is off-topic, omit it rather than blending it into the answer. "
            "Use plain readable formatting. "
            "If you include formulas, prefer one short lead sentence followed by display-math blocks. "
            "If both evidence types are present, use section headers 'From uploaded documents' and 'From web search'."
        )
        try:
            answer = self.llm_client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=answer_model,
            )
        except Exception as exc:
            logger.warning("LLM answer synthesis failed, falling back to extractive mode: %s", exc)
            return None

        clean_answer = answer.strip()
        if not clean_answer:
            logger.warning("LLM answer synthesis returned an empty response. Falling back to extractive mode.")
            return None
        return clean_answer, "Answer synthesized with an OpenAI-compatible LLM over grounded evidence."

    def _summarize_internal(self, question: str, retrieved_chunks: list[RetrievedChunkRead]) -> str:
        if not retrieved_chunks:
            return ""

        keywords = extract_keywords(question)
        scored_sentences: list[tuple[float, str]] = []
        for chunk in retrieved_chunks:
            for sentence in split_sentences(chunk.content):
                overlap = len(extract_keywords(sentence) & keywords)
                score = overlap + chunk.score
                scored_sentences.append((score, sentence))

        scored_sentences.sort(key=lambda item: item[0], reverse=True)
        selected = unique_preserve_order(sentence for _, sentence in scored_sentences if sentence)[:3]
        if not selected:
            selected = [chunk.content_preview for chunk in retrieved_chunks[:3]]
        return " ".join(selected)

    def _summarize_web(self, question: str, web_results: list[WebSearchResultRead]) -> str:
        if not web_results:
            return ""

        keywords = extract_keywords(question)
        scored_snippets: list[tuple[float, str]] = []
        for result in web_results:
            snippet = result.snippet or result.title
            if not snippet:
                continue
            overlap = len(extract_keywords(snippet) & keywords)
            score = overlap + max(0.0, 1.0 - (result.rank - 1) * 0.1)
            scored_snippets.append((score, f"{result.title}: {snippet}"))

        scored_snippets.sort(key=lambda item: item[0], reverse=True)
        selected = unique_preserve_order(text for _, text in scored_snippets if text)[:3]
        return " ".join(selected)

    def _format_internal_evidence(self, retrieved_chunks: list[RetrievedChunkRead]) -> str:
        if not retrieved_chunks:
            return "None"
        items: list[str] = []
        for chunk in retrieved_chunks[:6]:
            location = f"page {chunk.page_number}" if chunk.page_number else f"slide {chunk.slide_number}" if chunk.slide_number else "location unknown"
            excerpt = chunk.content.strip()
            if len(excerpt) > 1200:
                excerpt = f"{excerpt[:1197].rstrip()}..."
            items.append(
                f"- {chunk.filename} ({location}, score={chunk.score:.3f})\n{excerpt}"
            )
        return "\n".join(items)

    def _format_web_evidence(self, web_results: list[WebSearchResultRead]) -> str:
        if not web_results:
            return "None"
        items: list[str] = []
        for result in web_results[:6]:
            items.append(f"- {result.title} ({result.url}): {result.snippet}")
        return "\n".join(items)
