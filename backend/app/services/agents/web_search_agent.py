from app.schemas.chat import WebSearchResultRead
from app.services.search.web_search_service import WebSearchService


class WebSearchAgent:
    def __init__(self, web_search_service: WebSearchService | None = None) -> None:
        self.web_search_service = web_search_service or WebSearchService()

    def search(self, question: str) -> tuple[list[WebSearchResultRead], str | None]:
        return self.web_search_service.search(query=question)
