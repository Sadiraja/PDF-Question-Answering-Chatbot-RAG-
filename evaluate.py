import os
import sys
import json
import time
from typing import List, Dict, Any

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    DEFAULT_VECTOR_DB,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_TOP_K,
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_HF_MODEL,
    DEFAULT_LLM_PROVIDER,
    STRICT_FALLBACK_MESSAGE
)
from rag.document_loader import PDFLoader
from rag.chunker import RecursiveChunker
from rag.embeddings import get_embedder
from rag.vector_store import get_vector_store
from rag.retriever import RAGRetriever
from rag.generator import RAGGenerator

# Standardized 10-Question Benchmark Suite
TEST_SUITE = [
    {
        "id": 1,
        "category": "In-Domain / Factual",
        "doc": "AI_Healthcare_Whitepaper.pdf",
        "page": 1,
        "question": "What are the sensitivity and specificity metrics of the CheXNet-Pro engine for identifying malignant pulmonary nodules?",
        "expected_facts": ["94.7%", "91.3%"],
        "expected_summary": "94.7% sensitivity and 91.3% specificity in identifying malignant pulmonary nodules (>6mm).",
        "must_refuse": False
    },
    {
        "id": 2,
        "category": "In-Domain / Factual",
        "doc": "AI_Healthcare_Whitepaper.pdf",
        "page": 2,
        "question": "What is the maximum processing latency permitted for thoracic CT series under the clinical workflow SLA?",
        "expected_facts": ["1.8 seconds"],
        "expected_summary": "Strictly governed under an SLA of less than 1.8 seconds per volumetric CT series.",
        "must_refuse": False
    },
    {
        "id": 3,
        "category": "In-Domain / Factual",
        "doc": "AI_Healthcare_Whitepaper.pdf",
        "page": 3,
        "question": "Under which FDA regulatory pathway and clearance number was the PulseVision-AI system cleared?",
        "expected_facts": ["510(k)", "K233912"],
        "expected_summary": "FDA 510(k) pathway under clearance number K233912 as Class II SaMD.",
        "must_refuse": False
    },
    {
        "id": 4,
        "category": "In-Domain / Factual",
        "doc": "AI_Healthcare_Whitepaper.pdf",
        "page": 4,
        "question": "What cryptographic algorithm and encryption standard are mandated for data at rest and data in transit?",
        "expected_facts": ["256-bit AES", "TLS 1.3"],
        "expected_summary": "256-bit AES-GCM for data at rest and TLS 1.3 for data in transit.",
        "must_refuse": False
    },
    {
        "id": 5,
        "category": "In-Domain / Factual",
        "doc": "Company_Policy_Handbook.pdf",
        "page": 1,
        "question": "What are the company's core collaboration working hours and how many on-site days are required for hybrid staff?",
        "expected_facts": ["10:00 AM", "4:00 PM", "2 days"],
        "expected_summary": "Core hours from 10:00 AM to 4:00 PM EST; minimum 2 days per week on-site.",
        "must_refuse": False
    },
    {
        "id": 6,
        "category": "In-Domain / Factual",
        "doc": "Company_Policy_Handbook.pdf",
        "page": 2,
        "question": "How many weeks of fully paid parental leave are provided for primary and secondary caregivers?",
        "expected_facts": ["16 weeks", "8 weeks"],
        "expected_summary": "16 weeks fully paid leave for primary caregiver, 8 weeks for secondary caregiver.",
        "must_refuse": False
    },
    {
        "id": 7,
        "category": "In-Domain / Factual",
        "doc": "Company_Policy_Handbook.pdf",
        "page": 3,
        "question": "Within how many calendar days must business expenses be submitted, and what is the home office stipend amount?",
        "expected_facts": ["30 calendar days", "1,200"],
        "expected_summary": "Submitted within 30 calendar days of purchase; one-time $1,200.00 USD stipend.",
        "must_refuse": False
    },
    {
        "id": 8,
        "category": "Out-of-Domain / Refusal Test",
        "doc": None,
        "page": None,
        "question": "What is the stock ticker symbol and quarterly revenue for Apex Innovations in 2023?",
        "expected_facts": [],
        "expected_summary": "System must safely refuse without guessing or hallucinating revenue data.",
        "must_refuse": True
    },
    {
        "id": 9,
        "category": "Out-of-Domain / Refusal Test",
        "doc": None,
        "page": None,
        "question": "What is the standard clinical dosage of Amoxicillin for pediatric bacterial pharyngitis?",
        "expected_facts": [],
        "expected_summary": "System must safely refuse medical dosage questions not in documents.",
        "must_refuse": True
    },
    {
        "id": 10,
        "category": "Out-of-Domain / Refusal Test",
        "doc": None,
        "page": None,
        "question": "What is the capital city of planet Mars and who was elected mayor?",
        "expected_facts": [],
        "expected_summary": "System must reject non-existent entity questions without hallucination.",
        "must_refuse": True
    }
]

def run_evaluation(retriever: RAGRetriever, generator: RAGGenerator) -> List[Dict[str, Any]]:
    results = []

    for item in TEST_SUITE:
        qid = item["id"]
        q = item["question"]
        must_refuse = item["must_refuse"]

        retrieval_res = retriever.retrieve(q)
        rag_res = generator.generate(retrieval_res)

        ans = rag_res.answer
        is_answerable = rag_res.is_answerable
        citations = rag_res.citations

        # Check evaluation criteria
        if must_refuse:
            # Should have refused to answer
            refused = (not is_answerable) or ("cannot answer" in ans.lower()) or ("not found" in ans.lower())
            status = "PASS" if refused else "FAIL"
            notes = "Correctly refused out-of-domain query." if refused else "Failed: Hallucinated on unanswerable query."
        else:
            # Must contain expected key facts and citation
            contains_facts = any(fact.lower() in ans.lower() for fact in item["expected_facts"])
            has_citation = len(citations) > 0 or ("page" in ans.lower())
            status = "PASS" if (contains_facts and has_citation) else "FAIL"
            notes = "Verified fact with source citation." if status == "PASS" else f"Missing fact or citation. Ans: {ans[:80]}..."

        results.append({
            "id": qid,
            "category": item["category"],
            "question": q,
            "target_doc": item["doc"],
            "target_page": item["page"],
            "expected_summary": item["expected_summary"],
            "generated_answer": ans,
            "citations": citations,
            "is_answerable": is_answerable,
            "top_similarity": round(retrieval_res.top_score, 3),
            "status": status,
            "notes": notes
        })

    return results

def generate_markdown_report(results: List[Dict[str, Any]], vdb_name: str, embedder_name: str, llm_name: str, out_file: str = "TEST_RESULTS.md"):
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    pass_rate = (passed / total) * 100

    md = []
    md.append("# 🧪 PDF Question-Answering Chatbot (RAG) — Test Evaluation Report\n")
    md.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ")
    md.append(f"**Vector Database:** `{vdb_name}`  ")
    md.append(f"**Embedding Model:** `{embedder_name}`  ")
    md.append(f"**LLM Generation Provider:** `{llm_name}`  ")
    md.append(f"**Overall Score:** **{passed} / {total} Passed ({pass_rate:.1f}%)**\n")
    md.append("---\n")

    md.append("## 📊 Summary of Test Results\n")
    md.append("| # | Category | Question | Expected Target | Similarity | Citations | Status |")
    md.append("|---|---|---|---|---|---|---|")

    for r in results:
        status_badge = "✅ PASS" if r["status"] == "PASS" else "❌ FAIL"
        doc_info = f"{r['target_doc']} (p.{r['target_page']})" if r['target_doc'] else "*N/A (Refusal)*"
        cit_count = len(r['citations'])
        md.append(f"| Q{r['id']} | {r['category']} | {r['question'][:45]}... | {doc_info} | {r['top_similarity']:.2f} | {cit_count} passage(s) | {status_badge} |")

    md.append("\n---\n")
    md.append("## 🔍 Detailed Question-by-Question Evaluation\n")

    for r in results:
        status_badge = "✅ PASS" if r["status"] == "PASS" else "❌ FAIL"
        md.append(f"### Question {r['id']}: {r['question']}\n")
        md.append(f"- **Category:** `{r['category']}`")
        if r['target_doc']:
            md.append(f"- **Target Document & Page:** `{r['target_doc']}` (Page {r['target_page']})")
        md.append(f"- **Expected Behavior / Ground Truth:** {r['expected_summary']}")
        md.append(f"- **Top Retrieval Similarity Score:** `{r['top_similarity']}`")
        md.append(f"- **Test Status:** {status_badge} — *{r['notes']}*")
        md.append(f"\n**Generated Answer:**\n> {r['generated_answer']}\n")

        if r['citations']:
            md.append("**Source Citations Attached:**")
            for cit in r['citations']:
                md.append(f"- **[{cit['source']}, Page {cit['page']}]** (Score: {cit['similarity_score']}): *\"{cit['preview']}\"*")
        else:
            md.append("*No citations attached (appropriate for out-of-domain/unanswerable questions).*")

        md.append("\n---\n")

    report_text = "\n".join(md)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"Saved evaluation markdown report to {out_file}")

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Initializing PDF RAG Benchmark Suite (10 Questions)")
    print("=" * 70)

    # 1. Load sample PDFs
    sample_paths = [
        os.path.join("sample_docs", "AI_Healthcare_Whitepaper.pdf"),
        os.path.join("sample_docs", "Company_Policy_Handbook.pdf")
    ]
    for p in sample_paths:
        if not os.path.exists(p):
            print(f"Generating missing sample docs: {p}")
            import subprocess
            subprocess.run([sys.executable, "sample_docs/generate_samples.py"], check=True)

    print("\n[Step 1/4] Loading PDF documents...")
    pages = PDFLoader.load_multiple_paths(sample_paths)
    print(f"Loaded {len(pages)} pages across {len(sample_paths)} documents.")

    print("\n[Step 2/4] Chunking documents...")
    chunker = RecursiveChunker(chunk_size=DEFAULT_CHUNK_SIZE, chunk_overlap=DEFAULT_CHUNK_OVERLAP)
    chunks = chunker.chunk_pages(pages)
    print(f"Generated {len(chunks)} text chunks.")

    print(f"\n[Step 3/4] Embedding with HuggingFace ('{DEFAULT_HF_MODEL}') & indexing with FAISS...")
    embedder = get_embedder("HuggingFace", model_name=DEFAULT_HF_MODEL)
    texts = [c.text for c in chunks]
    embeddings = embedder.embed_documents(texts)

    vector_store = get_vector_store("faiss", dimension=embedder.dimension)
    vector_store.clear()
    vector_store.add_chunks(chunks, embeddings)
    print(f"Indexed {vector_store.count()} chunks into FAISS vector database.")

    # Detect LLM provider
    if os.getenv("OPENROUTER_API_KEY"):
        provider = "OpenRouter"
        model_name = "openai/gpt-4o-mini"
    elif os.getenv("GEMINI_API_KEY"):
        provider = "Google Gemini"
        model_name = "gemini-2.5-flash"
    elif os.getenv("OPENAI_API_KEY"):
        provider = "OpenAI"
        model_name = "gpt-4o-mini"
    else:
        provider = "Local Extractive Mode"
        model_name = "Extractive-Rules"

    print(f"\n[Step 4/4] Executing benchmark suite with LLM Provider: {provider} ({model_name})...")
    retriever = RAGRetriever(embedder=embedder, vector_store=vector_store, top_k=DEFAULT_TOP_K, score_threshold=DEFAULT_SCORE_THRESHOLD)
    generator = RAGGenerator(provider=provider, model_name=model_name)

    results = run_evaluation(retriever, generator)

    # Print summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    print("\n" + "=" * 70)
    print(f"BENCHMARK RESULTS: {passed} / {len(results)} PASSED ({(passed/len(results))*100:.1f}%)")
    print("=" * 70)
    for r in results:
        status_icon = "PASS [OK]" if r["status"] == "PASS" else "FAIL [X]"
        print(f"Q{r['id']:02d}: {status_icon} | {r['category'][:15]:15s} | {r['question'][:40]}...")

    # Save outputs
    generate_markdown_report(results, "FAISS", DEFAULT_HF_MODEL, provider, "TEST_RESULTS.md")
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Saved test_results.json successfully.")
