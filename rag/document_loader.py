import os
import io
import re
from typing import List, Union, BinaryIO
from dataclasses import dataclass
import pypdf

@dataclass
class DocumentPage:
    source: str
    page_number: int  # 1-indexed
    total_pages: int
    text: str
    char_count: int

class PDFLoader:
    """Extracts and normalizes text from PDF documents preserving page metadata."""

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalizes whitespace and removes unprintable artifacts."""
        if not text:
            return ""
        # Replace non-breaking spaces and form feeds
        text = text.replace('\xa0', ' ').replace('\x0c', '\n')
        # Replace multiple horizontal spaces with single space
        text = re.sub(r'[ \t]+', ' ', text)
        # Normalize multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @classmethod
    def load_from_path(cls, file_path: str) -> List[DocumentPage]:
        """Loads a PDF from an on-disk file path."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found at: {file_path}")

        file_name = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            return cls.load_from_bytes(f, file_name=file_name)

    @classmethod
    def load_from_bytes(cls, file_obj: Union[BinaryIO, bytes, io.BytesIO], file_name: str = "document.pdf") -> List[DocumentPage]:
        """Loads a PDF from a byte stream or bytes object (compatible with Streamlit UploadedFile)."""
        if isinstance(file_obj, bytes):
            stream = io.BytesIO(file_obj)
        elif hasattr(file_obj, "read"):
            content = file_obj.read()
            if isinstance(content, str):
                content = content.encode("utf-8")
            stream = io.BytesIO(content)
        else:
            raise ValueError("Unsupported file object type provided to PDFLoader.")

        reader = pypdf.PdfReader(stream)
        total_pages = len(reader.pages)
        pages: List[DocumentPage] = []

        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            extracted = page.extract_text() or ""
            cleaned = cls._clean_text(extracted)
            if cleaned:
                pages.append(
                    DocumentPage(
                        source=file_name,
                        page_number=page_num,
                        total_pages=total_pages,
                        text=cleaned,
                        char_count=len(cleaned)
                    )
                )

        return pages

    @classmethod
    def load_multiple_paths(cls, file_paths: List[str]) -> List[DocumentPage]:
        """Loads multiple PDF files into a single list of DocumentPages."""
        all_pages: List[DocumentPage] = []
        for path in file_paths:
            all_pages.extend(cls.load_from_path(path))
        return all_pages
