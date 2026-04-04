from pathlib import Path

from app.services.parsing.base import ParsedDocument, ParsedUnit
from app.utils.text import normalize_whitespace


class TextParser:
    def parse(self, file_path: Path) -> ParsedDocument:
        raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
        file_type = file_path.suffix.lower().lstrip(".") or "txt"
        units: list[ParsedUnit] = []

        if file_type == "md":
            current_section: str | None = None
            for block in raw_text.split("\n\n"):
                text = normalize_whitespace(block)
                if not text:
                    continue
                if text.startswith("#"):
                    current_section = text.lstrip("#").strip() or current_section
                    continue
                units.append(
                    ParsedUnit(
                        source_type="section",
                        text=text,
                        section_title=current_section,
                    )
                )
        else:
            content = normalize_whitespace(raw_text)
            if content:
                units.append(ParsedUnit(source_type="document", text=content))

        return ParsedDocument(
            file_type=file_type,
            source_path=file_path,
            units=units,
        )
