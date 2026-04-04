from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class ParsedUnit:
    source_type: str
    text: str
    page_number: int | None = None
    slide_number: int | None = None
    section_title: str | None = None


@dataclass(slots=True)
class ParsedDocument:
    file_type: str
    source_path: Path
    units: list[ParsedUnit] = field(default_factory=list)
    page_count: int | None = None
    slide_count: int | None = None


class Parser(Protocol):
    def parse(self, file_path: Path) -> ParsedDocument:
        ...
