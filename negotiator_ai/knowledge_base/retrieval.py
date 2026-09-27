"""
retrieval.py -- Core retrieval functions used by the Analyst agent and evaluation scripts.

Key functions:
  retrieve_tactics(query, k)         -- semantic similarity search, returns Documents
  retrieve_with_score(query, k)      -- same but with (Document, score) tuples for confidence checks
  web_search_fallback(query)         -- Tavily search when KB has no good match

Embeddings: local sentence-transformers model (no API key required).
Model: sentence-transformers/all-MiniLM-L6-v2  |  384-dim  |  ~90 MB cached locally
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Tuple
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from config import CHROMA_DB_PATH, EMBEDDING_MODEL, TAVILY_API_KEY, CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Singleton vectorstore — initialized once per process
# ---------------------------------------------------------------------------
_vectorstore: Chroma | None = None


def _get_vectorstore() -> Chroma:
    """
    Lazy-initialize the Chroma vector store.
    Reuses the same instance across calls (no repeated disk I/O).

    Embeddings use a local HuggingFace model — no API key required.
    The model is downloaded once and cached in ~/.cache/huggingface/.
    """
    global _vectorstore
    if _vectorstore is None:
        # Local embeddings — no OpenAI key needed
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},  # cosine-friendly L2 scores
        )
        _vectorstore = Chroma(
            persist_directory=CHROMA_DB_PATH,
            embedding_function=embeddings,
            collection_name="negotiation_tactics",
        )
        # Warn if the KB is empty so the issue is visible in logs
        try:
            count = _vectorstore._collection.count()
            if count == 0:
                import warnings
                warnings.warn(
                    "NegotiatorAI: Knowledge base is empty! "
                    "Run `python3 knowledge_base/build_kb.py` to embed the 25 tactic documents. "
                    "Until then, all RAG retrievals return nothing and web search fires every time.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            else:
                # Verify the stored metric is L2 so the score=1-(dist/2) formula holds.
                meta = _vectorstore._collection.metadata or {}
                stored_space = meta.get("hnsw:space", "l2")  # default when absent = l2
                if stored_space not in ("l2", ""):
                    import warnings
                    warnings.warn(
                        f"NegotiatorAI: Chroma collection uses metric '{stored_space}' "
                        "but the score conversion formula assumes L2. "
                        "Rebuild the KB (build_kb.py) to switch to L2.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
        except Exception:
            pass  # checks are best-effort; don't block startup
    return _vectorstore


def retrieve_tactics(query: str, k: int = 4) -> List[Document]:
    """
    Semantic similarity search over the negotiation knowledge base.

    Args:
        query: Natural language query describing the negotiation situation
        k:     Number of top documents to return (default 4)

    Returns:
        List of Document objects with .page_content and .metadata
    """
    vs = _get_vectorstore()
    results = vs.similarity_search(query, k=k)
    return results


def retrieve_with_score(query: str, k: int = 4) -> List[Tuple[Document, float]]:
    """
    Semantic similarity search with relevance scores.
    Used by the Strategist's reflection step to check retrieval confidence.

    Args:
        query: Natural language query
        k:     Number of results

    Returns:
        List of (Document, score) tuples.
        Score is cosine similarity [0, 1] — higher = more relevant.
        Note: Chroma returns distance (lower = better) which we convert to similarity.
    """
    vs = _get_vectorstore()
    # similarity_search_with_score returns (doc, distance) where distance ∈ [0, 2]
    raw = vs.similarity_search_with_score(query, k=k)
    # Convert Chroma L2 distance to a 0–1 similarity score
    # score = 1 - (distance / 2) approximates cosine similarity for normalized vectors
    scored = [(doc, round(1 - (dist / 2), 4)) for doc, dist in raw]
    return scored


def get_top_score(query: str, k: int = 4) -> float:
    """
    Return the best (highest) similarity score for a query.
    Used by the Analyst to decide whether to fall back to web search.
    """
    scored = retrieve_with_score(query, k=k)
    if not scored:
        return 0.0
    return max(score for _, score in scored)


def format_retrieved_context(docs: List[Document]) -> str:
    """
    Format a list of retrieved Documents into a readable context string.
    Passed into agent prompts as 'retrieved_evidence'.
    """
    if not docs:
        return "No relevant evidence retrieved from the knowledge base."

    sections = []
    for i, doc in enumerate(docs, 1):
        source = os.path.basename(doc.metadata.get("source", "unknown"))
        sections.append(f"[Evidence {i} — Source: {source}]\n{doc.page_content.strip()}")

    return "\n\n---\n\n".join(sections)


def web_search_fallback(query: str, max_results: int = 3) -> List[dict]:
    """
    Web search using Tavily — only called when KB has no strong match.
    Returns list of {"title": ..., "url": ..., "content": ...} dicts.

    Assumption: web_search is a fallback tool, not the primary retrieval path.
    Per plan Section 4: used only when KB confidence < CONFIDENCE_THRESHOLD.
    """
    if not TAVILY_API_KEY:
        return [{"title": "Web search unavailable", "url": "", "content": "TAVILY_API_KEY not set."}]

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=f"small business supplier negotiation {query}",
            max_results=max_results,
            search_depth="basic",
        )
        results = response.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],  # cap length
            }
            for r in results
        ]
    except Exception as e:
        return [{"title": "Web search error", "url": "", "content": str(e)}]


def format_web_results(results: List[dict]) -> str:
    """Format web search results into a context string."""
    if not results:
        return "No web search results available."

    sections = []
    for i, r in enumerate(results, 1):
        sections.append(
            f"[Web Result {i} — {r['title']}]\nSource: {r['url']}\n{r['content']}"
        )
    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# CLI test — run directly to verify retrieval is working
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing retrieve_tactics()...")
    test_cases = [
        "bulk discount packaging materials 500 units",
        "repeat customer loyalty discount negotiation",
        "payment terms Net 60 extension",
        "competing quote leverage BATNA",
        "silence tactic negotiation",
        "first time buyer no competing quotes",
        "equipment rental 6 month commitment",
        "raw materials food ingredients price lock",
    ]

    for query in test_cases:
        print(f"\nQuery: '{query}'")
        scored = retrieve_with_score(query, k=3)
        for doc, score in scored:
            src = os.path.basename(doc.metadata.get("source", "?"))
            preview = doc.page_content[:120].replace("\n", " ").strip()
            flag = "✅" if score >= CONFIDENCE_THRESHOLD else "⚠️ low"
            print(f"  {flag} score={score:.3f} [{src}] {preview}...")

    print("\n\nTesting web_search_fallback()...")
    web_results = web_search_fallback("unique item unusual pricing no KB match")
    for r in web_results:
        print(f"  - {r['title']}: {r['content'][:100]}...")
