"""
PDF Question-Answering Chatbot (RAG) Core Package
"""

from .document_loader import PDFLoader, DocumentPage
from .chunker import RecursiveChunker, Chunk
from .embeddings import get_embedder, BaseEmbedder
from .vector_store import get_vector_store, BaseVectorStore, FAISSVectorStore, ChromaVectorStore
from .retriever import RAGRetriever, RetrievalResult
from .generator import RAGGenerator, RAGResponse

__all__ = [
    "PDFLoader",
    "DocumentPage",
    "RecursiveChunker",
    "Chunk",
    "get_embedder",
    "BaseEmbedder",
    "get_vector_store",
    "BaseVectorStore",
    "FAISSVectorStore",
    "ChromaVectorStore",
    "RAGRetriever",
    "RetrievalResult",
    "RAGGenerator",
    "RAGResponse",
]
