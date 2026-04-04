from app.schemas.chat import WebSearchResultRead
from app.services.search.search_service import SearchService


class WebSearchService:
    def __init__(self, search_service: SearchService | None = None) -> None:
        self.search_service = search_service or SearchService()

    def search(self, query: str) -> tuple[list[WebSearchResultRead], str | None]:
        return self.search_service.search(query)
