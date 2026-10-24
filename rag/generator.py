import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .retriever import RetrievalResult, RetrievedChunk
from config import STRICT_FALLBACK_MESSAGE

SYSTEM_PROMPT = """You are a precise, factual Question-Answering assistant that strictly relies on provided document passages.

Instructions:
1. Answer the user's question using ONLY the factual information in the Provided Passages below.
2. For EVERY claim or fact you state, include an exact citation referencing the source and page in brackets, e.g.: [Page 2] or [FileName.pdf, Page 2].
3. STRICT PROHIBITION AGAINST HALLUCINATION: If the provided passages do not explicitly contain the information needed to answer the question, or if you cannot verify it directly from the text, you MUST state exactly:
"I cannot answer this question based on the provided document(s)."
4. Do NOT speculate, extrapolate, assume, or incorporate knowledge outside the provided passages.
"""

@dataclass
class RAGResponse:
    answer: str
    citations: List[Dict[str, Any]]
    is_answerable: bool
    model_used: str
    retrieval_result: RetrievalResult

class RAGGenerator:
    """Generates grounded answers from retrieved context using LLMs with hallucination safeguards."""

    def __init__(
        self,
        provider: str = "OpenRouter",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.provider = provider
        self.model_name = model_name
        self.api_key = (
            api_key
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )

    def _extract_citations(self, chunks: List[RetrievedChunk]) -> List[Dict[str, Any]]:
        """Transforms retrieved chunks into user-friendly citation objects."""
        citations = []
        for rc in chunks:
            chunk = rc.chunk
            preview = chunk.text[:250] + ("..." if len(chunk.text) > 250 else "")
            citations.append({
                "source": chunk.source,
                "page": chunk.page,
                "chunk_id": chunk.chunk_id,
                "similarity_score": round(rc.score, 3),
                "citation_tag": rc.citation_tag,
                "preview": preview,
                "full_text": chunk.text
            })
        return citations

    def generate(self, retrieval_result: RetrievalResult) -> RAGResponse:
        """Generates answer using configured provider with strict hallucination checks."""
        # 1. Check if retrieval had sufficient context
        if not retrieval_result.has_sufficient_context or len(retrieval_result.chunks) == 0:
            return RAGResponse(
                answer=STRICT_FALLBACK_MESSAGE,
                citations=[],
                is_answerable=False,
                model_used=f"{self.provider} (Threshold Filtered)",
                retrieval_result=retrieval_result
            )

        citations = self._extract_citations(retrieval_result.chunks)
        query = retrieval_result.query
        context = retrieval_result.formatted_context

        prompt = f"""Context Passages:
{context}

Question:
{query}

Answer (Remember to cite [Document, Page X] for every claim, or reply that you cannot answer if the context does not contain the answer):"""

        provider_lower = self.provider.lower()

        # 2. Provider Routing
        try:
            if "openrouter" in provider_lower:
                return self._call_openrouter(query, prompt, citations, retrieval_result)
            elif "gemini" in provider_lower or "google" in provider_lower:
                return self._call_gemini(query, prompt, citations, retrieval_result)
            elif "openai" in provider_lower:
                return self._call_openai(query, prompt, citations, retrieval_result)
            else:
                return self._call_extractive(query, citations, retrieval_result)
        except Exception as e:
            # Fallback to extractive if API call errors (e.g., quota or network error)
            print(f"[RAGGenerator Warning] LLM call failed with error: {e}. Falling back to Extractive QA.")
            return self._call_extractive(query, citations, retrieval_result, fallback_reason=str(e))

    def _call_openrouter(
        self,
        query: str,
        prompt: str,
        citations: List[Dict[str, Any]],
        retrieval_result: RetrievalResult
    ) -> RAGResponse:
        key = self.api_key or os.getenv("OPENROUTER_API_KEY")
        if not key:
            return self._call_extractive(query, citations, retrieval_result, fallback_reason="No OPENROUTER_API_KEY provided")

        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
            default_headers={
                "HTTP-Referer": "https://github.com/Sadiraja/PDF-Question-Answering-Chatbot-RAG-",
                "X-Title": "PDF-RAG-Chatbot"
            }
        )
        model_name = self.model_name or "openai/gpt-4o-mini"

        response = client.chat.completions.create(
            model=model_name,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        answer_text = response.choices[0].message.content.strip()
        is_answerable = "cannot answer this question" not in answer_text.lower()

        return RAGResponse(
            answer=answer_text,
            citations=citations if is_answerable else [],
            is_answerable=is_answerable,
            model_used=f"OpenRouter ({model_name})",
            retrieval_result=retrieval_result
        )

    def _call_gemini(
        self,
        query: str,
        prompt: str,
        citations: List[Dict[str, Any]],
        retrieval_result: RetrievalResult
    ) -> RAGResponse:
        key = self.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            return self._call_extractive(query, citations, retrieval_result, fallback_reason="No GEMINI_API_KEY provided")

        import google.generativeai as genai
        genai.configure(api_key=key)
        model_name = self.model_name or "gemini-2.5-flash"
        
        # Configure model with low temperature for factual grounding
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config={"temperature": 0.1, "top_p": 0.8}
        )

        response = model.generate_content(prompt)
        answer_text = response.text.strip() if response and response.text else STRICT_FALLBACK_MESSAGE
        is_answerable = "cannot answer this question" not in answer_text.lower()

        return RAGResponse(
            answer=answer_text,
            citations=citations if is_answerable else [],
            is_answerable=is_answerable,
            model_used=f"Google Gemini ({model_name})",
            retrieval_result=retrieval_result
        )

    def _call_openai(
        self,
        query: str,
        prompt: str,
        citations: List[Dict[str, Any]],
        retrieval_result: RetrievalResult
    ) -> RAGResponse:
        key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            return self._call_extractive(query, citations, retrieval_result, fallback_reason="No OPENAI_API_KEY provided")

        from openai import OpenAI
        client = OpenAI(api_key=key)
        model_name = self.model_name or "gpt-4o-mini"

        response = client.chat.completions.create(
            model=model_name,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        answer_text = response.choices[0].message.content.strip()
        is_answerable = "cannot answer this question" not in answer_text.lower()

        return RAGResponse(
            answer=answer_text,
            citations=citations if is_answerable else [],
            is_answerable=is_answerable,
            model_used=f"OpenAI ({model_name})",
            retrieval_result=retrieval_result
        )

    def _call_extractive(
        self,
        query: str,
        citations: List[Dict[str, Any]],
        retrieval_result: RetrievalResult,
        fallback_reason: Optional[str] = None
    ) -> RAGResponse:
        """Intelligent extractive QA fallback for local/offline execution without requiring API keys."""
        query_words = set(re.findall(r'\w+', query.lower()))
        stop_words = {"what", "is", "the", "of", "and", "in", "to", "a", "for", "are", "how", "many", "does", "do", "which"}
        keywords = query_words - stop_words

        if not keywords:
            return RAGResponse(
                answer=STRICT_FALLBACK_MESSAGE,
                citations=[],
                is_answerable=False,
                model_used="Local Extractive Engine",
                retrieval_result=retrieval_result
            )

        best_sentence = ""
        best_match_count = 0
        best_chunk_info = None

        for rc in retrieval_result.chunks:
            sentences = re.split(r'(?<=[.!?])\s+', rc.chunk.text)
            for s in sentences:
                s_words = set(re.findall(r'\w+', s.lower()))
                overlap = len(keywords.intersection(s_words))
                if overlap > best_match_count:
                    best_match_count = overlap
                    best_sentence = s.strip()
                    best_chunk_info = rc

        # Minimum keyword overlap requirement for confidence
        min_overlap = 2 if len(keywords) >= 3 else 1
        if best_match_count >= min_overlap and best_sentence and best_chunk_info:
            citation_tag = best_chunk_info.citation_tag
            formatted_answer = f"{best_sentence} {citation_tag}"
            notice = f" *(Generated via Local Extractive Engine)*" if not fallback_reason else f" *(Generated via Local Extractive Engine: {fallback_reason})*"
            return RAGResponse(
                answer=formatted_answer + notice,
                citations=citations,
                is_answerable=True,
                model_used="Local Extractive Fallback",
                retrieval_result=retrieval_result
            )
        else:
            return RAGResponse(
                answer=STRICT_FALLBACK_MESSAGE,
                citations=[],
                is_answerable=False,
                model_used="Local Extractive Fallback",
                retrieval_result=retrieval_result
            )
