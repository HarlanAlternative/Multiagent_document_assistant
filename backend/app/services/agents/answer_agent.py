from app.schemas.chat import RetrievedChunkRead, WebSearchResultRead
from app.services.qa.answer_service import AnswerService


class AnswerAgent:
    def __init__(self, answer_service: AnswerService | None = None) -> None:
        self.answer_service = answer_service or AnswerService()

    def answer(
        self,
        question: str,
        retrieved_chunks: list[RetrievedChunkRead],
        web_results: list[WebSearchResultRead],
        project_memory: str | None = None,
        conversation_context: str | None = None,
    ) -> tuple[str, str | None]:
        return self.answer_service.generate(
            question=question,
            retrieved_chunks=retrieved_chunks,
            web_results=web_results,
            project_memory=project_memory,
            conversation_context=conversation_context,
        )
