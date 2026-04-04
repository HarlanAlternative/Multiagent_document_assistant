from pathlib import Path

import fitz

from app.services.parsing.base import ParsedDocument, ParsedUnit


class PDFParser:
    def parse(self, file_path: Path) -> ParsedDocument:
        units: list[ParsedUnit] = []
        with fitz.open(file_path) as document:
            for index, page in enumerate(document, start=1):
                text = page.get_text("text")
                if not text or not text.strip():
                    continue
                units.append(
                    ParsedUnit(
                        source_type="pdf_page",
                        text=text,
                        page_number=index,
                    )
                )

            return ParsedDocument(
                file_type="pdf",
                source_path=file_path,
                units=units,
                page_count=document.page_count,
            )
