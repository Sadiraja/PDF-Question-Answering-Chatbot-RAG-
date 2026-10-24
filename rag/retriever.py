from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from .chunker import Chunk
from .embeddings import BaseEmbedder
from .vector_store import BaseVectorStore

@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float
    citation_tag: str

@dataclass
class RetrievalResult:
    query: str
    chunks: List[RetrievedChunk]
    has_sufficient_context: bool
    formatted_context: str
    top_score: float

class RAGRetriever:
    """Orchestrates query embedding, vector search, relevance thresholding, and prompt context formatting."""

    def __init__(
        self,
        embedder: BaseEmbedder,
        vector_store: BaseVectorStore,
        top_k: int = 4,
        score_threshold: float = 0.35
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.top_k = top_k
        self.score_threshold = score_threshold

    def retrieve(self, query: str, top_k: Optional[int] = None, score_threshold: Optional[float] = None) -> RetrievalResult:
        k = top_k if top_k is not None else self.top_k
        thresh = score_threshold if score_threshold is not None else self.score_threshold

        if not query.strip() or self.vector_store.count() == 0:
            return RetrievalResult(
                query=query,
                chunks=[],
                has_sufficient_context=False,
                formatted_context="",
                top_score=0.0
            )

        # 1. Embed query
        query_embedding = self.embedder.embed_query(query)

        # 2. Search vector store
        raw_results: List[Tuple[Chunk, float]] = self.vector_store.search(query_embedding, top_k=k)

        # 3. Filter by threshold
        retrieved: List[RetrievedChunk] = []
        top_score = 0.0

        for chunk, score in raw_results:
            if score > top_score:
                top_score = score
            if score >= thresh:
                citation_tag = f"[{chunk.source}, Page {chunk.page}, Chunk {chunk.metadata.get('page_chunk_index', 0) + 1}]"
                retrieved.append(RetrievedChunk(chunk=chunk, score=score, citation_tag=citation_tag))

        has_context = len(retrieved) > 0 and top_score >= thresh

        # 4. Format context for prompt injection
        context_parts = []
        for i, item in enumerate(retrieved, start=1):
            header = f"--- [Passage {i}] {item.citation_tag} (Similarity: {item.score:.2f}) ---"
            context_parts.append(f"{header}\n{item.chunk.text}\n")

        formatted_context = "\n".join(context_parts)

        return RetrievalResult(
            query=query,
            chunks=retrieved,
            has_sufficient_context=has_context,
            formatted_context=formatted_context,
            top_score=top_score
        )
