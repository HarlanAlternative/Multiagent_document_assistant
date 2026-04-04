from app.schemas.chat import CitationRead, RetrievedChunkRead, WebSearchResultRead


class CitationAgent:
    def format(self, retrieved_chunks: list[RetrievedChunkRead]) -> list[CitationRead]:
        citations: list[CitationRead] = []
        seen_keys: set[tuple[str, str | None, int | None, int | None]] = set()
        top_score = retrieved_chunks[0].score if retrieved_chunks else 0.0
        score_floor = max(top_score - 0.22, top_score * 0.72, 0.3)
        filtered_chunks = [chunk for chunk in retrieved_chunks if chunk.score >= score_floor][:4]

        for chunk in filtered_chunks:
            key = (chunk.document_id, chunk.chunk_id, chunk.page_number, chunk.slide_number)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            citations.append(
                CitationRead(
                    source_kind="document_chunk",
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    title=chunk.filename,
                    page_number=chunk.page_number,
                    slide_number=chunk.slide_number,
                )
            )
        return citations

    def format_web(self, web_results: list[WebSearchResultRead]) -> list[CitationRead]:
        citations: list[CitationRead] = []
        seen_urls: set[str] = set()
        for result in web_results:
            if result.url in seen_urls:
                continue
            seen_urls.add(result.url)
            citations.append(
                CitationRead(
                    source_kind="web_result",
                    title=result.title,
                    url=result.url,
                )
            )
        return citations
