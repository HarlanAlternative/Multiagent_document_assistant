import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.schemas.chat import ChatMode, CitationRead, RetrievedChunkRead, WebSearchResultRead
from app.services.agents.answer_agent import AnswerAgent
from app.services.agents.citation_agent import CitationAgent
from app.services.agents.retrieval_agent import RetrievalAgent
from app.services.agents.router_agent import RouteDecision, RouterAgent
from app.services.agents.web_search_agent import WebSearchAgent


@dataclass(slots=True)
class OrchestrationResult:
    answer: str
    route_used: str
    citations: list[CitationRead] = field(default_factory=list)
    internal_sources: list[CitationRead] = field(default_factory=list)
    external_sources: list[CitationRead] = field(default_factory=list)
    retrieved_chunks: list[RetrievedChunkRead] = field(default_factory=list)
    web_results: list[WebSearchResultRead] = field(default_factory=list)
    confidence_note: str | None = None


class AgentOrchestrator:
    def __init__(
        self,
        router_agent: RouterAgent | None = None,
        retrieval_agent: RetrievalAgent | None = None,
        web_search_agent: WebSearchAgent | None = None,
        answer_agent: AnswerAgent | None = None,
        citation_agent: CitationAgent | None = None,
    ) -> None:
        self.router_agent = router_agent or RouterAgent()
        self.retrieval_agent = retrieval_agent or RetrievalAgent()
        self.web_search_agent = web_search_agent or WebSearchAgent()
        self.answer_agent = answer_agent or AnswerAgent()
        self.citation_agent = citation_agent or CitationAgent()

    def run(
        self,
        db: Session,
        question: str,
        mode: ChatMode,
        project_id: str,
        project_memory: str | None = None,
        conversation_context: str | None = None,
        retrieval_context: str | None = None,
        selected_document_ids: list[str] | None = None,
        file_type: str | None = None,
    ) -> OrchestrationResult:
        context_dependent = self._is_context_dependent(question)
        retrieval_context_to_use = retrieval_context if context_dependent else None
        answer_context_to_use = conversation_context if context_dependent else None
        route_decision: RouteDecision = self.router_agent.decide(
            question=question,
            mode=mode,
            conversation_context=conversation_context,
            selected_document_ids=selected_document_ids or [],
        )
        retrieved_chunks: list[RetrievedChunkRead] = []
        web_results: list[WebSearchResultRead] = []
        web_note = None

        if route_decision.use_private:
            retrieved_chunks = self.retrieval_agent.retrieve(
                db=db,
                question=question,
                conversation_context=retrieval_context_to_use,
                project_id=project_id,
                selected_document_ids=selected_document_ids or [],
                file_type=file_type,
            )

        if route_decision.use_web:
            web_results, web_note = self.web_search_agent.search(question=question)

        answer, answer_note = self.answer_agent.answer(
            question=question,
            retrieved_chunks=retrieved_chunks,
            web_results=web_results,
            project_memory=project_memory,
            conversation_context=answer_context_to_use,
        )
        internal_sources = self.citation_agent.format(retrieved_chunks)
        external_sources = self.citation_agent.format_web(web_results)
        citations = [*internal_sources, *external_sources]
        search_note = None
        if route_decision.use_web and not web_results and not web_note:
            search_note = "External web search did not return usable results for this query."
        confidence_note = self._combine_notes(route_decision.confidence_note, web_note, search_note, answer_note)
        return OrchestrationResult(
            answer=answer,
            route_used=route_decision.route_used,
            citations=citations,
            internal_sources=internal_sources,
            external_sources=external_sources,
            retrieved_chunks=retrieved_chunks,
            web_results=web_results,
            confidence_note=confidence_note,
        )

    def _combine_notes(self, *notes: str | None) -> str | None:
        filtered_notes = [note for note in notes if note]
        if not filtered_notes:
            return None
        return " ".join(filtered_notes)

    def _is_context_dependent(self, question: str) -> bool:
        lowered = question.lower().strip()
        if len(lowered) <= 8:
            return True

        english_markers = (
            "it",
            "that",
            "those",
            "them",
            "this one",
            "that one",
            "the former",
            "the latter",
            "second point",
            "first point",
            "third point",
            "continue",
            "go on",
            "what about",
            "how about",
            "explain more",
            "tell me more",
            "compare that",
        )
        chinese_markers = (
            "这个",
            "那个",
            "这些",
            "那些",
            "它",
            "它们",
            "其",
            "上一条",
            "上一点",
            "下一点",
            "第二点",
            "第一点",
            "第三点",
            "继续",
            "接着",
            "展开",
            "详细说",
            "再说",
            "刚才",
            "前面",
            "上面",
            "那个文件",
            "这个文件",
        )
        if any(marker in lowered for marker in english_markers):
            return True
        if any(marker in question for marker in chinese_markers):
            return True
        if re.fullmatch(r"[?？!.。,\s]+", question):
            return True
        return False
