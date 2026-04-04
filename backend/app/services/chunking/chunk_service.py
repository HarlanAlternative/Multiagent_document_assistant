from dataclasses import dataclass

from app.services.parsing.base import ParsedDocument, ParsedUnit
from app.utils.text import approximate_token_count, build_preview, normalize_whitespace


@dataclass(slots=True)
class ChunkPayload:
    chunk_index: int
    content: str
    token_count: int
    source_type: str
    page_number: int | None = None
    slide_number: int | None = None
    section_title: str | None = None
    content_preview: str | None = None


class ChunkService:
    def __init__(self, chunk_size_words: int = 220, chunk_overlap_words: int = 40) -> None:
        self.chunk_size_words = chunk_size_words
        self.chunk_overlap_words = chunk_overlap_words

    def build_chunks(self, parsed_document: ParsedDocument) -> list[ChunkPayload]:
        chunks: list[ChunkPayload] = []
        chunk_index = 0
        for unit in parsed_document.units:
            clean_text = normalize_whitespace(unit.text)
            if not clean_text:
                continue
            for content in self._split_unit(unit):
                chunks.append(
                    ChunkPayload(
                        chunk_index=chunk_index,
                        content=content,
                        token_count=approximate_token_count(content),
                        source_type=unit.source_type,
                        page_number=unit.page_number,
                        slide_number=unit.slide_number,
                        section_title=unit.section_title,
                        content_preview=build_preview(content),
                    )
                )
                chunk_index += 1
        return chunks

    def _split_unit(self, unit: ParsedUnit) -> list[str]:
        words = normalize_whitespace(unit.text).split()
        if len(words) <= self.chunk_size_words:
            return [" ".join(words)]

        step = max(1, self.chunk_size_words - self.chunk_overlap_words)
        segments: list[str] = []
        for start in range(0, len(words), step):
            window = words[start : start + self.chunk_size_words]
            if not window:
                continue
            segments.append(" ".join(window))
            if start + self.chunk_size_words >= len(words):
                break
        return segments
