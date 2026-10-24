import os
import time
import json
import streamlit as st
from typing import List

from config import (
    DEFAULT_VECTOR_DB,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_TOP_K,
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_HF_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_MODEL,
    STRICT_FALLBACK_MESSAGE
)
from rag.document_loader import PDFLoader, DocumentPage
from rag.chunker import RecursiveChunker, Chunk
from rag.embeddings import get_embedder
from rag.vector_store import get_vector_store, FAISSVectorStore, ChromaVectorStore
from rag.retriever import RAGRetriever
from rag.generator import RAGGenerator

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="PDF Question-Answering Chatbot (RAG)",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .stat-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .stat-number {
        font-size: 1.6rem;
        font-weight: 700;
        color: #2563EB;
    }
    .stat-label {
        font-size: 0.85rem;
        color: #64748B;
    }
    .citation-card {
        background-color: #F0FDF4;
        border-left: 4px solid #16A34A;
        padding: 10px 14px;
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 0.9rem;
    }
    .fallback-card {
        background-color: #FEF2F2;
        border-left: 4px solid #DC2626;
        padding: 10px 14px;
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chunks" not in st.session_state:
    st.session_state.chunks = []
if "indexed_docs" not in st.session_state:
    st.session_state.indexed_docs = {}
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "embedder" not in st.session_state:
    st.session_state.embedder = None
if "current_vdb" not in st.session_state:
    st.session_state.current_vdb = DEFAULT_VECTOR_DB
if "embedder_key" not in st.session_state:
    st.session_state.embedder_key = DEFAULT_EMBEDDING_PROVIDER

# --- SIDEBAR: CONFIGURATION & CONTROLS ---
with st.sidebar:
    st.header("⚙️ RAG Configuration")

    # 1. Vector Database
    vdb_choice = st.selectbox(
        "Vector Database",
        options=["FAISS", "ChromaDB"],
        index=0 if st.session_state.current_vdb == "FAISS" else 1,
        help="Select vector index backend: FAISS for high-speed indexing or ChromaDB for persistent document collections."
    )

    # 2. Embedding Provider
    emb_choice = st.selectbox(
        "Embedding Model",
        options=["HuggingFace (all-MiniLM-L6-v2)", "Google Gemini", "OpenAI"],
        index=0,
        help="HuggingFace runs 100% locally and free. Gemini/OpenAI require API keys."
    )

    # 3. LLM Generation Provider
    llm_choice = st.selectbox(
        "LLM Provider",
        options=["OpenRouter", "Google Gemini", "OpenAI", "Local Extractive Mode"],
        index=0,
        help="Select LLM backend. OpenRouter supports hundreds of models (GPT-4o-mini, Gemini, Llama, DeepSeek)."
    )

    # Model and API Key selection
    selected_model = None
    api_key_input = ""

    if "openrouter" in llm_choice.lower():
        selected_model = st.selectbox(
            "OpenRouter Model",
            options=[
                "openai/gpt-4o-mini",
                "google/gemini-2.0-flash-exp:free",
                "meta-llama/llama-3.3-70b-instruct",
                "deepseek/deepseek-chat",
                "anthropic/claude-3.5-haiku"
            ],
            index=0,
            help="Choose model available on OpenRouter."
        )
        env_key = os.getenv("OPENROUTER_API_KEY") or ""
        api_key_input = st.text_input(
            "OpenRouter API Key",
            value=env_key,
            type="password",
            placeholder="sk-or-v1-...",
            help="Get your key at https://openrouter.ai/keys"
        )
    elif "gemini" in llm_choice.lower() or "gemini" in emb_choice.lower():
        selected_model = DEFAULT_GEMINI_MODEL
        env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        api_key_input = st.text_input(
            "Gemini API Key",
            value=env_key,
            type="password",
            placeholder="AIzaSy...",
            help="Get your key at https://aistudio.google.com/app/apikey"
        )
    elif "openai" in llm_choice.lower() or "openai" in emb_choice.lower():
        selected_model = DEFAULT_OPENAI_MODEL
        env_key = os.getenv("OPENAI_API_KEY") or ""
        api_key_input = st.text_input(
            "OpenAI API Key",
            value=env_key,
            type="password",
            placeholder="sk-proj-...",
            help="Get your key at https://platform.openai.com/api-keys"
        )

    st.markdown("---")
    st.subheader("📑 Document Ingestion")

    chunk_size = st.slider("Chunk Size (characters)", min_value=300, max_value=1500, value=DEFAULT_CHUNK_SIZE, step=50)
    chunk_overlap = st.slider("Chunk Overlap (characters)", min_value=0, max_value=300, value=DEFAULT_CHUNK_OVERLAP, step=10)

    st.markdown("---")
    st.subheader("🔍 Retrieval Tuning")

    top_k = st.slider("Top-K Passages", min_value=1, max_value=8, value=DEFAULT_TOP_K)
    score_threshold = st.slider(
        "Min Similarity Threshold",
        min_value=0.1,
        max_value=0.9,
        value=DEFAULT_SCORE_THRESHOLD,
        step=0.05,
        help="Chunks with similarity below this threshold are discarded to prevent hallucination."
    )

    st.markdown("---")
    st.subheader("📂 Upload Documents")

    uploaded_files = st.file_uploader(
        "Upload one or more PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        load_samples = st.button("📁 Load Samples", use_container_width=True, help="Load bundled Healthcare and Company Policy sample PDFs")
    with col_btn2:
        clear_all = st.button("🗑️ Reset All", use_container_width=True)

    if clear_all:
        st.session_state.messages = []
        st.session_state.chunks = []
        st.session_state.indexed_docs = {}
        if st.session_state.vector_store:
            st.session_state.vector_store.clear()
        st.session_state.vector_store = None
        st.rerun()

# --- HELPER FUNCTIONS ---
def get_active_embedder(provider_str: str, api_key: str):
    if "gemini" in provider_str.lower():
        return get_embedder("Google Gemini", api_key=api_key)
    elif "openai" in provider_str.lower():
        return get_embedder("OpenAI", api_key=api_key)
    else:
        return get_embedder("HuggingFace", model_name=DEFAULT_HF_MODEL)

def process_and_index_documents(pages: List[DocumentPage], vdb_type: str, emb_provider: str, key: str, c_size: int, c_overlap: int):
    with st.spinner("Extracting and chunking text..."):
        chunker = RecursiveChunker(chunk_size=c_size, chunk_overlap=c_overlap)
        chunks = chunker.chunk_pages(pages)

    if not chunks:
        st.error("No extractable text found in the provided PDF(s).")
        return

    with st.spinner("Generating embeddings & building vector index..."):
        embedder = get_active_embedder(emb_provider, key)
        texts = [c.text for c in chunks]
        embeddings = embedder.embed_documents(texts)

        vector_store = get_vector_store(store_type=vdb_type, dimension=embedder.dimension)
        vector_store.clear()
        vector_store.add_chunks(chunks, embeddings)

        st.session_state.embedder = embedder
        st.session_state.vector_store = vector_store
        st.session_state.chunks = chunks
        st.session_state.current_vdb = vdb_type

        # Track documents
        doc_stats = {}
        for p in pages:
            if p.source not in doc_stats:
                doc_stats[p.source] = {"pages": p.total_pages, "chunks": 0}
        for c in chunks:
            if c.source in doc_stats:
                doc_stats[c.source]["chunks"] += 1
        st.session_state.indexed_docs = doc_stats

    st.success(f"Successfully indexed {len(pages)} pages into {len(chunks)} chunks using {vdb_type}!")

# Process file uploads
if uploaded_files:
    # Check if newly uploaded
    new_files = [f for f in uploaded_files if f.name not in st.session_state.indexed_docs]
    if new_files:
        all_pages = []
        for uf in uploaded_files:
            pages = PDFLoader.load_from_bytes(uf.getvalue(), file_name=uf.name)
            all_pages.extend(pages)
        process_and_index_documents(all_pages, vdb_choice, emb_choice, api_key_input, chunk_size, chunk_overlap)

if load_samples:
    sample_files = [
        os.path.join("sample_docs", "AI_Healthcare_Whitepaper.pdf"),
        os.path.join("sample_docs", "Company_Policy_Handbook.pdf")
    ]
    all_pages = []
    for sf in sample_files:
        if os.path.exists(sf):
            pages = PDFLoader.load_from_path(sf)
            all_pages.extend(pages)
    if all_pages:
        process_and_index_documents(all_pages, vdb_choice, emb_choice, api_key_input, chunk_size, chunk_overlap)
        st.rerun()

# --- MAIN CONTENT TABS ---
tab_chat, tab_docs, tab_eval = st.tabs(["💬 Chat & QA", "📑 Document Index", "🧪 Automated Benchmarks"])

# ==========================================
# TAB 1: CHAT & QA
# ==========================================
with tab_chat:
    st.markdown('<div class="main-header">📚 PDF Question-Answering Chatbot (RAG)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Ask questions from your documents. Answers include verified page citations and strict hallucination defense.</div>',
        unsafe_allow_html=True
    )

    # Document Status Bar
    if st.session_state.chunks and st.session_state.vector_store:
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.markdown(f'<div class="stat-box"><div class="stat-number">{len(st.session_state.indexed_docs)}</div><div class="stat-label">Documents</div></div>', unsafe_allow_html=True)
        with col_s2:
            total_pages = sum(d["pages"] for d in st.session_state.indexed_docs.values())
            st.markdown(f'<div class="stat-box"><div class="stat-number">{total_pages}</div><div class="stat-label">Total Pages</div></div>', unsafe_allow_html=True)
        with col_s3:
            st.markdown(f'<div class="stat-box"><div class="stat-number">{len(st.session_state.chunks)}</div><div class="stat-label">Indexed Chunks</div></div>', unsafe_allow_html=True)
        with col_s4:
            st.markdown(f'<div class="stat-box"><div class="stat-number">{vdb_choice}</div><div class="stat-label">Active Vector DB</div></div>', unsafe_allow_html=True)
    else:
        st.info("💡 **Getting Started:** Click **'📁 Load Samples'** in the sidebar or upload your own PDF documents to start querying.")

    st.write("")

    # Quick sample question pills
    if st.session_state.chunks:
        st.caption("Quick test questions:")
        q_cols = st.columns(3)
        with q_cols[0]:
            if st.button("🔍 CheXNet sensitivity rate?", use_container_width=True):
                st.session_state.prompt_query = "What is the sensitivity and specificity of the CheXNet-Pro engine for detecting pulmonary nodules?"
        with q_cols[1]:
            if st.button("🌴 Annual vacation leave days?", use_container_width=True):
                st.session_state.prompt_query = "How many days of paid annual vacation do full-time employees receive?"
        with q_cols[2]:
            if st.button("🚫 Capital of Mars? (Unanswerable)", use_container_width=True):
                st.session_state.prompt_query = "What is the capital city of planet Mars?"

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "citations" in msg and msg["citations"]:
                with st.expander(f"📖 View {len(msg['citations'])} Verified Source Passages"):
                    for c in msg["citations"]:
                        st.markdown(
                            f"**Document:** `{c['source']}` | **Page:** `{c['page']}` | **Score:** `{c['similarity_score']}`\n\n"
                            f"> *\"{c['full_text']}\"*"
                        )
            if "grounded" in msg:
                if msg["grounded"]:
                    st.caption("✅ **Grounded:** Answer corroborated by retrieved document passages.")
                else:
                    st.caption("⚠️ **Safety Refusal:** Question falls outside indexed documents. Hallucination strictly prevented.")

    # Process user query
    user_input = st.chat_input("Ask a question about the uploaded PDF document(s)...")
    if "prompt_query" in st.session_state and st.session_state.prompt_query:
        user_input = st.session_state.prompt_query
        st.session_state.prompt_query = None

    if user_input:
        if not st.session_state.vector_store or st.session_state.vector_store.count() == 0:
            st.warning("Please upload and index a PDF document before asking questions.")
        else:
            # 1. User Message
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # 2. Assistant Generation
            with st.chat_message("assistant"):
                with st.spinner("Searching document index and synthesizing answer..."):
                    retriever = RAGRetriever(
                        embedder=st.session_state.embedder,
                        vector_store=st.session_state.vector_store,
                        top_k=top_k,
                        score_threshold=score_threshold
                    )
                    retrieval_res = retriever.retrieve(user_input)

                    generator = RAGGenerator(
                        provider=llm_choice,
                        model_name=selected_model,
                        api_key=api_key_input
                    )
                    rag_res = generator.generate(retrieval_res)

                    st.markdown(rag_res.answer)

                    if rag_res.citations:
                        with st.expander(f"📖 View {len(rag_res.citations)} Verified Source Passages"):
                            for c in rag_res.citations:
                                st.markdown(
                                    f"**Document:** `{c['source']}` | **Page:** `{c['page']}` | **Score:** `{c['similarity_score']}`\n\n"
                                    f"> *\"{c['full_text']}\"*"
                                )

                    if rag_res.is_answerable:
                        st.caption(f"✅ **Grounded** | Model: {rag_res.model_used} | Top Similarity: {retrieval_res.top_score:.3f}")
                    else:
                        st.caption("⚠️ **Safety Refusal** | Question cannot be answered from document. Hallucination avoided.")

                    # Save to chat history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": rag_res.answer,
                        "citations": rag_res.citations,
                        "grounded": rag_res.is_answerable,
                        "model": rag_res.model_used
                    })

    # Clear chat button
    if st.session_state.messages:
        col_c1, col_c2 = st.columns([6, 1])
        with col_c2:
            if st.button("🧹 Clear Chat"):
                st.session_state.messages = []
                st.rerun()

# ==========================================
# TAB 2: DOCUMENT & CHUNK INSPECTOR
# ==========================================
with tab_docs:
    st.subheader("📑 Document & Chunk Explorer")
    if not st.session_state.chunks:
        st.info("No documents indexed yet. Use the sidebar to load or upload documents.")
    else:
        st.markdown("### Indexed Files")
        doc_rows = []
        for name, stats in st.session_state.indexed_docs.items():
            doc_rows.append({"Filename": name, "Pages": stats["pages"], "Chunks Created": stats["chunks"]})
        st.table(doc_rows)

        st.markdown("### Chunk Inspector")
        doc_names = list(st.session_state.indexed_docs.keys())
        selected_doc = st.selectbox("Filter chunks by document:", options=["All"] + doc_names)
        
        filtered_chunks = st.session_state.chunks
        if selected_doc != "All":
            filtered_chunks = [c for c in filtered_chunks if c.source == selected_doc]

        st.write(f"Showing **{len(filtered_chunks)}** chunks:")
        for idx, c in enumerate(filtered_chunks[:30]):
            with st.expander(f"Chunk #{idx+1} — `{c.source}` (Page {c.page}, Length: {c.char_length} chars)"):
                st.code(c.text, language="markdown")

# ==========================================
# TAB 3: AUTOMATED BENCHMARKS (10 TEST QUESTIONS)
# ==========================================
with tab_eval:
    st.subheader("🧪 Automated 10-Question Benchmark Suite")
    st.markdown(
        "Run the standardized 10-question evaluation suite covering in-domain factual retrieval, "
        "page citations, and out-of-domain unanswerable question rejection."
    )

    if st.button("🚀 Run 10 Benchmark Questions Now", type="primary"):
        if not st.session_state.vector_store or st.session_state.vector_store.count() == 0:
            st.error("Please load the sample documents first using '📁 Load Samples' in the sidebar.")
        else:
            from evaluate import TEST_SUITE, run_evaluation
            with st.spinner("Evaluating 10 benchmark questions..."):
                retriever = RAGRetriever(
                    embedder=st.session_state.embedder,
                    vector_store=st.session_state.vector_store,
                    top_k=top_k,
                    score_threshold=score_threshold
                )
                generator = RAGGenerator(
                    provider=llm_choice,
                    model_name=selected_model,
                    api_key=api_key_input
                )
                results = run_evaluation(retriever, generator)

            passed_count = sum(1 for r in results if r["status"] == "PASS")
            st.success(f"Benchmark Complete! Accuracy Score: **{passed_count} / {len(results)} Passed** ({passed_count/len(results)*100:.0f}%)")

            for r in results:
                status_icon = "✅" if r["status"] == "PASS" else "❌"
                with st.expander(f"{status_icon} Q{r['id']}: {r['question']} ({r['category']})"):
                    st.markdown(f"**Expected Category:** `{r['category']}`")
                    st.markdown(f"**Expected Facts / Behavior:** *{r['expected_summary']}*")
                    st.markdown(f"**Generated Answer:**\n\n{r['generated_answer']}")
                    if r["citations"]:
                        st.markdown("**Citations Provided:**")
                        for cit in r["citations"]:
                            st.write(f"- `{cit['source']}` (Page {cit['page']}) | Similarity: {cit['similarity_score']}")
                    else:
                        st.markdown("*No citations returned (Appropriate for out-of-domain questions).*")
