import os
from dotenv import load_dotenv

load_dotenv()

# Vector Database Options
DEFAULT_VECTOR_DB = "FAISS"  # "FAISS" or "ChromaDB"
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), ".chroma_db")
FAISS_INDEX_DIR = os.path.join(os.path.dirname(__file__), ".faiss_index")

# Chunking Configuration
DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 120

# Retrieval Configuration
DEFAULT_TOP_K = 4
DEFAULT_SCORE_THRESHOLD = 0.35  # Cosine similarity minimum threshold (0.0 to 1.0)

# Embeddings Configuration
DEFAULT_EMBEDDING_PROVIDER = "HuggingFace"  # "HuggingFace", "Google Gemini", "OpenAI"
DEFAULT_HF_MODEL = "all-MiniLM-L6-v2"
DEFAULT_GEMINI_EMBEDDING_MODEL = "models/text-embedding-004"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

# LLM Generation Configuration
DEFAULT_LLM_PROVIDER = "OpenRouter"  # "OpenRouter", "Google Gemini", "OpenAI", "Extractive Fallback"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-4o-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

# Strict Fallback Message for Out-of-Domain / Unanswerable Questions
STRICT_FALLBACK_MESSAGE = (
    "I cannot answer this question based on the provided document(s). "
    "The required information was not found in the uploaded text."
)
