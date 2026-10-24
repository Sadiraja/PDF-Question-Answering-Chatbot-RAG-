import re
from typing import List, Dict, Any
from dataclasses import dataclass
from .document_loader import DocumentPage

@dataclass
class Chunk:
    chunk_id: str
    source: str
    page: int  # 1-indexed
    chunk_index: int
    text: str
    char_length: int
    metadata: Dict[str, Any]

class RecursiveChunker:
    """Recursively splits text on semantic separators with configurable overlap."""

    def __init__(self, chunk_size: int = 700, chunk_overlap: int = 120):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively splits text into chunks under chunk_size."""
        final_chunks: List[str] = []
        if not separators:
            # Fallback character slice
            return [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size - self.chunk_overlap)]

        separator = separators[0]
        remaining_separators = separators[1:]

        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        current_doc: List[str] = []
        current_len = 0

        for s in splits:
            token = s if not separator else s + separator
            token_len = len(token)

            if token_len > self.chunk_size:
                # If current accumulator has content, flush it
                if current_doc:
                    accumulated = "".join(current_doc).strip()
                    if accumulated:
                        final_chunks.append(accumulated)
                    current_doc = []
                    current_len = 0
                # Split oversized component with subsequent separator
                sub_chunks = self._split_text(s, remaining_separators)
                final_chunks.extend(sub_chunks)
                continue

            if current_len + token_len > self.chunk_size:
                accumulated = "".join(current_doc).strip()
                if accumulated:
                    final_chunks.append(accumulated)
                
                # Maintain overlap from current_doc
                overlap_doc: List[str] = []
                overlap_len = 0
                for item in reversed(current_doc):
                    if overlap_len + len(item) <= self.chunk_overlap:
                        overlap_doc.insert(0, item)
                        overlap_len += len(item)
                    else:
                        break
                current_doc = overlap_doc + [token]
                current_len = overlap_len + token_len
            else:
                current_doc.append(token)
                current_len += token_len

        if current_doc:
            accumulated = "".join(current_doc).strip()
            if accumulated:
                final_chunks.append(accumulated)

        return [c for c in final_chunks if c]

    def chunk_pages(self, pages: List[DocumentPage]) -> List[Chunk]:
        """Splits document pages into chunks tagged with page and source metadata."""
        all_chunks: List[Chunk] = []
        global_index = 0

        for page in pages:
            raw_text = page.text
            if not raw_text.strip():
                continue

            text_splits = self._split_text(raw_text, self.separators)
            for page_chunk_idx, split_text in enumerate(text_splits):
                cleaned_chunk = split_text.strip()
                if not cleaned_chunk:
                    continue

                clean_source_id = re.sub(r'[^a-zA-Z0-9_-]', '_', page.source)
                chunk_id = f"{clean_source_id}_p{page.page_number}_c{page_chunk_idx}"
                
                metadata = {
                    "source": page.source,
                    "page": page.page_number,
                    "total_pages": page.total_pages,
                    "chunk_index": global_index,
                    "page_chunk_index": page_chunk_idx,
                    "char_length": len(cleaned_chunk)
                }

                chunk = Chunk(
                    chunk_id=chunk_id,
                    source=page.source,
                    page=page.page_number,
                    chunk_index=global_index,
                    text=cleaned_chunk,
                    char_length=len(cleaned_chunk),
                    metadata=metadata
                )
                all_chunks.append(chunk)
                global_index += 1

        return all_chunks
