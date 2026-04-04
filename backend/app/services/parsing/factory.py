from pathlib import Path

from fastapi import HTTPException, status

from app.services.parsing.base import ParsedDocument
from app.services.parsing.docx_parser import DOCXParser
from app.services.parsing.pdf_parser import PDFParser
from app.services.parsing.pptx_parser import PPTXParser
from app.services.parsing.text_parser import TextParser


class ParserFactory:
    def __init__(self) -> None:
        self.pdf_parser = PDFParser()
        self.pptx_parser = PPTXParser()
        self.docx_parser = DOCXParser()
        self.text_parser = TextParser()

    def parse(self, file_path: Path, file_type: str) -> ParsedDocument:
        file_type = file_type.lower()
        if file_type == "pdf":
            return self.pdf_parser.parse(file_path)
        if file_type == "pptx":
            return self.pptx_parser.parse(file_path)
        if file_type == "docx":
            return self.docx_parser.parse(file_path)
        if file_type in {"txt", "md"}:
            return self.text_parser.parse(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_type}",
        )
