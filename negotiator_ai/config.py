"""
config.py -- Central configuration for NegotiatorAI.

RAG_MODE and LLM_MODEL can be set via:
  1. Environment variables (for headless eval scripts)
  2. The Streamlit sidebar (overrides env at runtime via session_state)

OpenRouter support: set OPENROUTER_API_KEY in .env to use any model available
on https://openrouter.ai/models without needing individual provider keys.
Embeddings run locally via sentence-transformers (no API key required).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# RAG mode
# Possible values: "no_rag" | "basic_rag" | "agentic_rag"
# ---------------------------------------------------------------------------
RAG_MODE: str = os.getenv("RAG_MODE", "agentic_rag")

# ---------------------------------------------------------------------------
# LLM model selection
#
# OpenRouter models (recommended — one key, hundreds of models):
#   "openai/gpt-4o-mini"                  -> GPT-4o Mini via OpenRouter
#   "openai/gpt-4o"                       -> GPT-4o via OpenRouter
#   "anthropic/claude-3-5-haiku"          -> Claude 3.5 Haiku via OpenRouter
#   "anthropic/claude-3-5-sonnet"         -> Claude 3.5 Sonnet via OpenRouter
#   "meta-llama/llama-3.1-8b-instruct"    -> Llama 3.1 8B via OpenRouter (free tier)
#   "google/gemini-flash-1.5"             -> Gemini Flash via OpenRouter
#   "mistralai/mistral-7b-instruct"       -> Mistral 7B via OpenRouter (free tier)
#
# Direct provider models (need their own API keys):
#   "gpt-4o-mini"               -> OpenAI direct
#   "claude-haiku-3-5-20241022" -> Anthropic direct
#   "llama-3.1-8b-instant"      -> Groq direct
# ---------------------------------------------------------------------------
LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

# ---------------------------------------------------------------------------
# Chroma / KB paths
# ---------------------------------------------------------------------------
CHROMA_DB_PATH: str = os.path.join(os.path.dirname(__file__), "chroma_db")
KB_DOCS_PATH: str = os.path.join(os.path.dirname(__file__), "knowledge_base", "docs")

# ---------------------------------------------------------------------------
# SQLite path
# ---------------------------------------------------------------------------
SQLITE_DB_PATH: str = os.path.join(os.path.dirname(__file__), "memory", "negotiations.db")

# ---------------------------------------------------------------------------
# Retrieval settings
# ---------------------------------------------------------------------------
DEFAULT_K: int = 4                  # top-k docs for retrieval
CONFIDENCE_THRESHOLD: float = 0.60  # min similarity score to pass reflection
MAX_REQUERY_ITERATIONS: int = 2     # max Analyst re-retrieval loops

# ---------------------------------------------------------------------------
# Embedding model — LOCAL via sentence-transformers (no API key needed)
# Model is downloaded once and cached in ~/.cache/huggingface/
# Dimension: 384  |  Size: ~90 MB  |  Fast CPU inference
# ---------------------------------------------------------------------------
EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Web search (Tavily) — optional
# ---------------------------------------------------------------------------
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

# ---------------------------------------------------------------------------
# API keys
# OPENROUTER_API_KEY is the primary key — routes to any LLM provider.
# Direct provider keys are only needed if you bypass OpenRouter.
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")        # direct OpenAI (optional)
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")  # direct Anthropic (optional)
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")            # direct Groq (optional)

# OpenRouter base URL for LangChain's ChatOpenAI (OpenRouter is OpenAI-compatible)
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"


def get_llm(model: str = LLM_MODEL, temperature: float = 0.3):
    """
    Factory function — returns the right LangChain LLM object for the given model name.

    Routing logic:
      1. If OPENROUTER_API_KEY is set  -> always use OpenRouter (covers any model name)
      2. If model starts with "gpt"    -> direct OpenAI
      3. If model starts with "claude" -> direct Anthropic
      4. If model contains "llama"     -> direct Groq
      5. Anything else with OpenRouter key -> OpenRouter

    OpenRouter is OpenAI-API-compatible, so ChatOpenAI works with just
    base_url and api_key overridden. The model name must match the OpenRouter
    identifier (e.g. "openai/gpt-4o-mini", not "gpt-4o-mini").
    """
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_groq import ChatGroq

    # OpenRouter path — preferred when key is set
    if OPENROUTER_API_KEY and not OPENROUTER_API_KEY.startswith("your_"):
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://github.com/negotiatorai",  # OpenRouter attribution
                "X-Title": "NegotiatorAI",
            },
        )

    # Direct provider fallback (legacy / when OpenRouter key not set)
    if model.startswith("gpt"):
        return ChatOpenAI(model=model, temperature=temperature, api_key=OPENAI_API_KEY)
    elif model.startswith("claude"):
        return ChatAnthropic(model=model, temperature=temperature, api_key=ANTHROPIC_API_KEY)
    elif "llama" in model or "mixtral" in model:
        return ChatGroq(model=model, temperature=temperature, api_key=GROQ_API_KEY)
    else:
        raise ValueError(
            f"Unknown model '{model}' and OPENROUTER_API_KEY not set. "
            "Either set OPENROUTER_API_KEY in .env, or use a model name "
            "starting with 'gpt', 'claude', or containing 'llama'."
        )
