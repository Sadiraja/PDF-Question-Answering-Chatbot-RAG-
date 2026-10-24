import os
import pickle
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from .chunker import Chunk

class BaseVectorStore(ABC):
    """Abstract base class for vector store engines."""

    @abstractmethod
    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        """Add chunks and corresponding embeddings to the store."""
        pass

    @abstractmethod
    def search(self, query_embedding: np.ndarray, top_k: int = 4) -> List[Tuple[Chunk, float]]:
        """Search top-k most similar chunks. Returns list of (Chunk, similarity_score)."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Returns total number of chunks stored."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears all vectors and metadata from store."""
        pass


class FAISSVectorStore(BaseVectorStore):
    """Vector database implementation powered by Facebook AI Similarity Search (FAISS)."""

    def __init__(self, dimension: int = 384, persist_dir: Optional[str] = None):
        import faiss
        self.faiss = faiss
        self.dimension = dimension
        self.persist_dir = persist_dir
        # Inner Product with normalized vectors calculates Cosine Similarity
        self.index = self.faiss.IndexFlatIP(dimension)
        self.chunks: List[Chunk] = []

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) == 0:
            return
        if embeddings.shape[0] != len(chunks):
            raise ValueError(f"Number of chunks ({len(chunks)}) does not match embeddings count ({embeddings.shape[0]})")

        # Ensure correct float32 type and dimension
        emb = embeddings.astype(np.float32)
        if emb.shape[1] != self.dimension:
            # Recreate index if dimension changed (e.g. switched embedder)
            self.dimension = emb.shape[1]
            self.index = self.faiss.IndexFlatIP(self.dimension)
            self.chunks = []

        self.index.add(emb)
        self.chunks.extend(chunks)

        if self.persist_dir:
            self.save(self.persist_dir)

    def search(self, query_embedding: np.ndarray, top_k: int = 4) -> List[Tuple[Chunk, float]]:
        if self.count() == 0:
            return []

        top_k = min(top_k, self.count())
        q_emb = np.ascontiguousarray(query_embedding.reshape(1, -1), dtype=np.float32)

        # Search inner product (cosine similarity)
        scores, indices = self.index.search(q_emb, top_k)
        results: List[Tuple[Chunk, float]] = []

        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and idx < len(self.chunks):
                # Clamp score between 0.0 and 1.0 for cosine similarity
                clean_score = max(0.0, min(1.0, float(score)))
                results.append((self.chunks[idx], clean_score))

        return results

    def count(self) -> int:
        return self.index.ntotal if self.index else 0

    def clear(self) -> None:
        self.index = self.faiss.IndexFlatIP(self.dimension)
        self.chunks = []

    def save(self, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)
        index_file = os.path.join(directory, "faiss.index")
        meta_file = os.path.join(directory, "chunks.pkl")

        self.faiss.write_index(self.index, index_file)
        with open(meta_file, "wb") as f:
            pickle.dump(self.chunks, f)

    def load(self, directory: str) -> bool:
        index_file = os.path.join(directory, "faiss.index")
        meta_file = os.path.join(directory, "chunks.pkl")

        if os.path.exists(index_file) and os.path.exists(meta_file):
            self.index = self.faiss.read_index(index_file)
            self.dimension = self.index.d
            with open(meta_file, "rb") as f:
                self.chunks = pickle.load(f)
            return True
        return False


class ChromaVectorStore(BaseVectorStore):
    """Vector database implementation powered by ChromaDB."""

    def __init__(self, collection_name: str = "pdf_rag_collection", persist_dir: Optional[str] = None):
        import chromadb
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        
        if persist_dir:
            os.makedirs(persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.client = chromadb.EphemeralClient()

        # Delete existing collection if resetting, or get/create
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self._chunks_map: Dict[str, Chunk] = {}

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        embs_list = embeddings.tolist()

        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embs_list,
            metadatas=metadatas
        )

        for chunk in chunks:
            self._chunks_map[chunk.chunk_id] = chunk

    def search(self, query_embedding: np.ndarray, top_k: int = 4) -> List[Tuple[Chunk, float]]:
        if self.count() == 0:
            return []

        top_k = min(top_k, self.count())
        q_emb = query_embedding.tolist()

        res = self.collection.query(
            query_embeddings=[q_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        results: List[Tuple[Chunk, float]] = []
        if res and res["ids"] and len(res["ids"][0]) > 0:
            for idx in range(len(res["ids"][0])):
                cid = res["ids"][0][idx]
                doc_text = res["documents"][0][idx]
                meta = res["metadatas"][0][idx]
                # Chroma with cosine distance: distance is (1 - cosine_similarity)
                dist = res["distances"][0][idx] if res["distances"] else 0.0
                score = max(0.0, min(1.0, 1.0 - dist))

                if cid in self._chunks_map:
                    chunk = self._chunks_map[cid]
                else:
                    chunk = Chunk(
                        chunk_id=cid,
                        source=meta.get("source", "unknown"),
                        page=meta.get("page", 1),
                        chunk_index=meta.get("chunk_index", 0),
                        text=doc_text,
                        char_length=len(doc_text),
                        metadata=meta
                    )
                    self._chunks_map[cid] = chunk

                results.append((chunk, float(score)))

        return results

    def count(self) -> int:
        return self.collection.count()

    def clear(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self._chunks_map = {}


def get_vector_store(
    store_type: str = "faiss",
    dimension: int = 384,
    persist_dir: Optional[str] = None
) -> BaseVectorStore:
    """Factory helper to instantiate either FAISS or ChromaDB store."""
    if store_type.lower() == "chroma" or "chroma" in store_type.lower():
        return ChromaVectorStore(persist_dir=persist_dir)
    return FAISSVectorStore(dimension=dimension, persist_dir=persist_dir)
