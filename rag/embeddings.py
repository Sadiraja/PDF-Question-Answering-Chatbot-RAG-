import os
from abc import ABC, abstractmethod
from typing import List
import numpy as np

class BaseEmbedder(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> np.ndarray:
        """Returns 2D numpy array of shape (N, embedding_dim)."""
        pass

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        """Returns 1D numpy array of shape (embedding_dim,)."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass


class HuggingFaceEmbedder(BaseEmbedder):
    """Local SentenceTransformers embedder (no external API calls or keys required)."""
    _cached_models = {}

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        if model_name not in HuggingFaceEmbedder._cached_models:
            from sentence_transformers import SentenceTransformer
            HuggingFaceEmbedder._cached_models[model_name] = SentenceTransformer(model_name)
        self.model = HuggingFaceEmbedder._cached_models[model_name]
        if hasattr(self.model, "get_embedding_dimension"):
            self._dim = self.model.get_embedding_dimension()
        else:
            self._dim = self.model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
        return embedding.astype(np.float32)

    @property
    def dimension(self) -> int:
        return self._dim


class GeminiEmbedder(BaseEmbedder):
    """Google Gemini embedding provider using text-embedding-004."""

    def __init__(self, api_key: str = None, model_name: str = "models/text-embedding-004"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for GeminiEmbedder.")
        self.model_name = model_name
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self._genai = genai
        self._dim = 768

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        vectors = []
        for text in texts:
            res = self._genai.embed_content(
                model=self.model_name,
                content=text,
                task_type="retrieval_document"
            )
            emb = np.array(res['embedding'], dtype=np.float32)
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            vectors.append(emb)
        return np.vstack(vectors)

    def embed_query(self, text: str) -> np.ndarray:
        res = self._genai.embed_content(
            model=self.model_name,
            content=text,
            task_type="retrieval_query"
        )
        emb = np.array(res['embedding'], dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb

    @property
    def dimension(self) -> int:
        return self._dim


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding provider using text-embedding-3-small."""

    def __init__(self, api_key: str = None, model_name: str = "text-embedding-3-small"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIEmbedder.")
        self.model_name = model_name
        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)
        self._dim = 1536

    def embed_documents(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dim), dtype=np.float32)
        response = self.client.embeddings.create(input=texts, model=self.model_name)
        embeddings = [data.embedding for data in response.data]
        arr = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    def embed_query(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(input=[text], model=self.model_name)
        emb = np.array(response.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb

    @property
    def dimension(self) -> int:
        return self._dim


def get_embedder(provider: str = "HuggingFace", model_name: str = None, api_key: str = None) -> BaseEmbedder:
    """Factory helper to obtain an embedding instance."""
    provider_lower = provider.lower()
    if "gemini" in provider_lower or "google" in provider_lower:
        return GeminiEmbedder(api_key=api_key, model_name=model_name or "models/text-embedding-004")
    elif "openai" in provider_lower:
        return OpenAIEmbedder(api_key=api_key, model_name=model_name or "text-embedding-3-small")
    else:
        # Default to HuggingFace SentenceTransformers
        return HuggingFaceEmbedder(model_name=model_name or "all-MiniLM-L6-v2")
