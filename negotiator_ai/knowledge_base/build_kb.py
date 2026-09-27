"""
build_kb.py -- Chunk and embed all knowledge base documents into Chroma.

Run once (or whenever docs are updated):
    python3 knowledge_base/build_kb.py

Embeddings use a local sentence-transformers model -- no API key required.
Model: sentence-transformers/all-MiniLM-L6-v2 (~90 MB, downloaded and cached once)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CHROMA_DB_PATH, KB_DOCS_PATH, EMBEDDING_MODEL
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma


def load_documents(docs_path: str):
    """Load all markdown files from the docs directory."""
    loader = DirectoryLoader(
        docs_path,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    docs = loader.load()
    print(f"[KB Builder] Loaded {len(docs)} documents from {docs_path}")
    return docs


def chunk_documents(docs):
    """
    Split documents into overlapping chunks.
    Chunk size 600 chars / overlap 80 chars:
    - Small enough for precise semantic matching
    - Large enough to contain complete tactical guidance
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80,
        separators=["\n## ", "\n### ", "\n\n", "\n", " ", ""],
        length_function=len,
    )
    chunks = splitter.split_documents(docs)
    print(f"[KB Builder] Split into {len(chunks)} chunks")
    return chunks


def build_vector_store(chunks, db_path: str):
    """Embed chunks with local HuggingFace model and persist to Chroma."""
    print(f"[KB Builder] Loading local embedding model: {EMBEDDING_MODEL}")
    print("[KB Builder] (Model downloads ~90 MB on first run, then cached locally)")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    print(f"[KB Builder] Embedding {len(chunks)} chunks ...")

    # If DB already exists, delete and rebuild (schema may have changed)
    if os.path.exists(db_path) and os.listdir(db_path):
        print(f"[KB Builder] Existing DB found at {db_path} -- rebuilding...")
        import shutil
        shutil.rmtree(db_path)
        os.makedirs(db_path, exist_ok=True)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=db_path,
        collection_name="negotiation_tactics",
        # Lock distance metric to L2 at creation time.
        # retrieval.py score formula (score = 1 - dist/2) assumes L2 distances in [0, 2].
        collection_metadata={"hnsw:space": "l2"},
    )
    count = vectorstore._collection.count()
    print(f"[KB Builder] Vector store built: {count} chunks persisted to {db_path}")
    return vectorstore


def run_test_query(vectorstore):
    """Quick smoke test -- verify retrieval works after build."""
    test_queries = [
        "bulk discount packaging materials",
        "repeat customer loyalty leverage",
        "payment terms Net 60",
        "competing quote BATNA walkaway",
        "silence tactic anchoring",
    ]
    print("\n[KB Builder] Running smoke test queries...")
    for q in test_queries:
        results = vectorstore.similarity_search(q, k=2)
        print(f"  Query: '{q}'")
        for r in results:
            src = os.path.basename(r.metadata.get("source", "unknown"))
            print(f"    [{src}] {r.page_content[:100].strip()}...")
    print("\n[KB Builder] Smoke tests complete")


if __name__ == "__main__":
    print("=" * 60)
    print("NegotiatorAI -- Knowledge Base Builder")
    print("No API key required -- embeddings run locally")
    print("=" * 60)

    docs = load_documents(KB_DOCS_PATH)
    chunks = chunk_documents(docs)
    vectorstore = build_vector_store(chunks, CHROMA_DB_PATH)
    run_test_query(vectorstore)

    print("\n[KB Builder] Done. Run `python3 knowledge_base/retrieval.py` to test retrieval.")
