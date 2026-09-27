# NegotiatorAI

**AI-powered supplier negotiation intelligence for small businesses.**

NegotiatorAI is a multi-agent agentic RAG system that helps small business owners negotiate better deals with suppliers. Given a supplier quote, it retrieves evidence-backed negotiation tactics, generates a grounded counter-offer strategy, lets you rehearse against a realistic AI vendor, scores your performance, and saves every deal to a persistent history.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the App](#running-the-app)
- [Knowledge Base](#knowledge-base)
- [RAG Modes](#rag-modes)
- [Supported LLM Models](#supported-llm-models)
- [Evaluation Framework](#evaluation-framework)
- [API Reference (Agents)](#api-reference-agents)
- [Security Notes](#security-notes)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Overview

Small businesses often enter supplier negotiations underprepared — without benchmark data, rehearsed arguments, or knowledge of standard industry discounts. NegotiatorAI addresses this by:

1. **Researching** negotiation tactics relevant to the specific deal category and leverage situation
2. **Drafting** a grounded counter-offer backed by retrieved evidence, not hallucinated figures
3. **Letting you edit** the AI's strategy before committing (Human-in-the-Loop checkpoint)
4. **Rehearsing** the negotiation against an adversarial AI supplier that pushes back realistically
5. **Scoring** your rehearsal across 5 dimensions with actionable coaching notes
6. **Remembering** every deal so patterns build over time

---

## Architecture

```
User Input (quoted price, item, leverage facts)
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                  LangGraph Pipeline                      │
│                                                         │
│  load_history ──► analyst_retrieve ──► strategist_draft │
│                          ▲                    │         │
│                          │           reflection_check   │
│                   re_retrieve ◄──── (if confidence low) │
│                                         │               │
│                                    END (HITL pause)     │
└─────────────────────────────────────────────────────────┘
          │
          ▼
  Human-in-the-Loop (user edits strategy in Streamlit)
          │
          ▼
  Vendor Rehearsal (multi-turn adversarial chat loop)
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│              Post-Rehearsal Pipeline                     │
│   strategist_score ──► save_memory ──► END              │
└─────────────────────────────────────────────────────────┘
          │
          ▼
  Scorecard + PDF Export + SQLite History
```

### Agent Roles

| Agent | Role | Persona |
|---|---|---|
| **Analyst** | Neutral evidence researcher | Retrieves and synthesises negotiation tactics from the knowledge base. Never recommends — only reports facts. |
| **Strategist** | User's advocate | Turns Analyst evidence into a concrete counter-offer. Self-reflects to verify every claim is grounded. |
| **Vendor** | Adversarial supplier rep | Defends the original quote, makes concessions only under sustained pressure. Maximum concession: 15% off quote. |

### Reflection Loop (Agentic RAG)

The Strategist performs a self-critique after drafting. If the counter-offer percentage or leverage points are not traceable to retrieved evidence or user-stated facts, the pipeline loops back to the Analyst with a narrower query. Maximum 2 re-retrieval iterations before proceeding.

---

## Features

- **7-screen Streamlit UI** — onboarding, deal entry, research status, strategy review, rehearsal chat, scorecard, history dashboard
- **Agentic RAG** — adaptive multi-step retrieval with conditional loyalty queries, payment-term queries, and Tavily web fallback
- **Human-in-the-Loop** — fully editable strategy form before rehearsal; the AI draft is a starting point, not a final answer
- **Adversarial rehearsal** — vendor follows a realistic concession ladder (round 1: defend; round 2: 2–3%; round 3: 5–7%; round 4+: check management)
- **5-dimension scorecard** — Overall, Assertiveness, Leverage Use, Pushback Handling, Closing Technique
- **PDF export** — downloadable negotiation brief with deal summary, counter-offer, leverage points, opening script, evidence benchmarks, and scorecard
- **Persistent memory** — SQLite store keyed by `business_id`; history dashboard with savings by category chart
- **Local embeddings** — `sentence-transformers/all-MiniLM-L6-v2` runs on CPU, no OpenAI key needed for KB search
- **OpenRouter integration** — single API key routes to GPT-4o, Claude, Gemini, Llama, DeepSeek, and 450+ models
- **Evaluation framework** — automated tests across 10 deals × 3 RAG modes × multiple LLMs with accuracy, reasoning, and consistency metrics

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit ≥ 1.39 |
| Agentic pipeline | LangGraph ≥ 0.2.45 |
| LLM orchestration | LangChain ≥ 0.3.7 |
| LLM routing | OpenRouter (via `langchain-openai` with custom `base_url`) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local, CPU, no API key) |
| Vector store | ChromaDB ≥ 0.5.15 |
| Web search fallback | Tavily |
| Persistent memory | SQLite (stdlib) |
| PDF export | fpdf2 ≥ 2.8.1 |
| Evaluation | pandas, matplotlib, scipy |

---

## Project Structure

```
negotiator_ai/
│
├── app.py                          # Streamlit UI — 7 screens
├── config.py                       # Central config + LLM factory (get_llm)
├── requirements.txt
├── setup.sh                        # One-command setup script
├── .env                            # Your API keys (gitignored)
├── .env.example                    # Template — copy to .env
│
├── agents/
│   ├── analyst.py                  # Neutral researcher — adaptive agentic retrieval
│   ├── strategist.py               # User's advocate — counter-offer + reflection loop
│   └── vendor.py                   # Adversarial supplier + post-rehearsal scoring
│
├── graph/
│   ├── state.py                    # LangGraph TypedDict: NegotiationState, DealFacts
│   ├── nodes.py                    # All LangGraph node functions
│   └── pipeline.py                 # StateGraph wiring + conditional edges
│
├── knowledge_base/
│   ├── docs/                       # 25 curated negotiation tactic documents (.md)
│   ├── build_kb.py                 # Embed docs into ChromaDB (run once)
│   └── retrieval.py                # retrieve_tactics(), web_search_fallback()
│
├── memory/
│   ├── sqlite_store.py             # save_negotiation(), load_history(), get_summary_stats()
│   └── negotiations.db             # Auto-created SQLite database
│
├── export/
│   └── pdf_export.py               # PDF cheat sheet generator (fpdf2)
│
├── evaluation/
│   ├── test_deals.py               # 10 representative test deals
│   ├── metrics.py                  # score_accuracy(), score_reasoning_quality(), score_consistency()
│   └── eval_runner.py              # Full evaluation loop with charts + CSV export
│
└── .streamlit/
    └── config.toml                 # Theme configuration
```

---

## Setup & Installation

### Prerequisites

- Python 3.10 or higher
- An [OpenRouter API key](https://openrouter.ai/keys) (required)
- Tavily API key (optional — only needed for web search fallback)

### 1. Clone and install dependencies

```bash
cd negotiator_ai
pip install -r requirements.txt
```

The first run will also download the local embedding model (~90 MB, cached automatically).

### 2. Configure API keys

```bash
cp .env.example .env
```

Open `.env` and add your OpenRouter key:

```env
OPENROUTER_API_KEY=sk-or-v1-...your key here...
```

All other keys are optional. See [Configuration](#configuration) for details.

### 3. Build the knowledge base

This embeds the 25 negotiation tactic documents into ChromaDB. Runs entirely locally — no API calls, no cost. Takes about 30 seconds.

```bash
python3 knowledge_base/build_kb.py
```

Expected output:
```
Loaded 25 documents
Split into ~180 chunks
Embedding 180 chunks ...
Vector store built: 180 chunks persisted
Smoke tests complete
```

> **You only need to run this once.** Re-run it if you add or edit documents in `knowledge_base/docs/`.

### 4. Launch the app

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Configuration

All configuration lives in `.env`. The app reads it at startup via `python-dotenv`.

```env
# ── Required ──────────────────────────────────────────────────────────────
OPENROUTER_API_KEY=sk-or-v1-...        # Get at openrouter.ai/keys

# ── Optional: direct provider keys (leave blank when using OpenRouter) ────
OPENAI_API_KEY=                         # Only if bypassing OpenRouter for OpenAI
ANTHROPIC_API_KEY=                      # Only if bypassing OpenRouter for Anthropic
GROQ_API_KEY=                           # Only if bypassing OpenRouter for Groq

# ── Optional: Tavily web search ───────────────────────────────────────────
TAVILY_API_KEY=                         # tavily.com — free tier available

# ── Pipeline defaults (overridable via Streamlit sidebar at runtime) ──────
RAG_MODE=agentic_rag                    # no_rag | basic_rag | agentic_rag
LLM_MODEL=openai/gpt-4o-mini           # Any OpenRouter model identifier
```

### Key configuration options in `config.py`

| Constant | Default | Description |
|---|---|---|
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model — no API key needed |
| `CONFIDENCE_THRESHOLD` | `0.60` | Min similarity score before web search fallback triggers |
| `MAX_REQUERY_ITERATIONS` | `2` | Max analyst re-retrieval loops per negotiation |
| `DEFAULT_K` | `4` | Number of KB chunks retrieved per query |

---

## Running the App

### Application flow

```
Screen 1 — Business Profile
   Enter your business name, industry, and a unique ID.
   Returning users see their past negotiation stats.

Screen 2 — Deal Entry
   Enter the supplier quote: item, category, quantity, price, payment terms.
   Check your leverage factors: repeat customer, competing quotes, volume commitment.

Screen 3 — Research
   The pipeline runs automatically.
   Shows retrieval queries, evidence chunks, benchmarks, and analyst summary.

Screen 4 — Strategy (Human-in-the-Loop)
   The AI pre-fills a counter-offer, leverage points, alternative asks, and opening script.
   Edit any field freely before proceeding — your edits are what carry forward.

Screen 5 — Rehearsal
   Multi-turn chat against the AI vendor.
   Type your opening, respond to pushbacks, use your leverage points.
   End when you feel ready.

Screen 6 — Scorecard
   5-dimension performance score with coaching notes and an improved opening script.
   Download the full negotiation brief as a PDF.

Screen 7 — History
   Table of all past negotiations for your business ID.
   Summary stats: total deals, estimated savings, average score.
   Bar chart of savings by category.
```

---

## Knowledge Base

The `knowledge_base/docs/` directory contains 25 curated markdown documents covering the full negotiation tactics landscape:

| # | Topic |
|---|---|
| 01–02 | Bulk and volume discount norms — industry benchmarks, tiered pricing |
| 03 | Payment term negotiation — extending Net 15 to Net 30/60 |
| 04 | Early payment discounts — 2/10 Net 30 structures |
| 05 | Delivery and quality penalty clauses |
| 06 | Service contract and AMC negotiation |
| 07 | Loyalty and repeat customer leverage |
| 08 | Competing quote leverage tactics |
| 09 | Anchoring tactics |
| 10 | BATNA and walkaway leverage |
| 11 | Silence tactics and psychology |
| 12 | Framing and reframing tactics |
| 13 | Equipment rental vs. purchase decisions |
| 14 | Raw materials and F&B ingredients negotiation |
| 15 | Packaging materials negotiation |
| 16 | Logistics and freight negotiation |
| 17 | Office supplies and furniture procurement |
| 18 | Opening and closing scripts |
| 19 | First-time buyer strategies |
| 20 | Supplier relationship management |
| 21 | Bracketing and concession strategy |
| 22 | Handling supplier pushbacks |
| 23 | Negotiation psychology and cognitive biases |
| 24 | Preparation checklist and scoring |
| 25 | Counter-offer benchmarks by category |

Documents are chunked at 600 characters with 80-character overlap using `RecursiveCharacterTextSplitter`, prioritising markdown heading boundaries.

---

## RAG Modes

Three retrieval modes are selectable from the sidebar at any time:

### Agentic RAG (recommended)

Multi-step conditional retrieval:

1. **Primary retrieval** — category + item + deal type query
2. **Loyalty retrieval** — triggered only when `is_repeat_customer=True`
3. **Re-query** — triggered when Strategist reflection fails; uses the Strategist's critique as the new query
4. **Payment terms retrieval** — always runs as a secondary pass
5. **Web search fallback** — triggered when top similarity score < 0.60 (Tavily)

Each step deduplicates by document content. Maximum 8 chunks per pipeline run.

### Basic RAG

Single fixed query from deal facts. No reflection, no re-retrieval, no web fallback. Faster and cheaper — useful for simple deals.

### No RAG

Skips retrieval entirely. The Strategist uses only parametric knowledge (what the LLM was trained on). Useful for comparison and offline demos.

---

## Supported LLM Models

All models route through OpenRouter unless you set a direct provider key. Use any OpenRouter model identifier in the sidebar or `.env`:

**Recommended for NegotiatorAI:**

| Model | ID | Cost |
|---|---|---|
| GPT-4o Mini | `openai/gpt-4o-mini` | $0.15/1M tokens |
| GPT-4o | `openai/gpt-4o` | $2.50/1M tokens |
| Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | $1.00/1M tokens |
| Claude Sonnet 5 | `anthropic/claude-sonnet-5` | $2.00/1M tokens |
| Gemini 2.5 Flash | `google/gemini-2.5-flash` | $0.30/1M tokens |
| Llama 3.1 8B | `meta-llama/llama-3.1-8b-instruct` | $0.05/1M tokens |
| DeepSeek V4 Flash | `deepseek/deepseek-v4-flash` | $0.05/1M tokens |
| Qwen 3.7 Flash | `qwen/qwen3.7-flash` | $0.03/1M tokens |

**Free tier models (no cost):**

| Model | ID |
|---|---|
| Gemma 4 31B | `google/gemma-4-31b-it:free` |
| Qwen 3.8 27B | `qwen/qwen3.8-27b:free` |
| Nemotron Ultra | `nvidia/nemotron-3-ultra-550b-a55b:free` |

Browse all 458 available models at [openrouter.ai/models](https://openrouter.ai/models).

---

## Evaluation Framework

The evaluation suite tests pipeline quality across all combinations:

- **10 test deals** — covering all 6 categories (packaging, raw materials, equipment, service, logistics, office supplies) × leverage types (first-time buyer, repeat customer, competing quotes, combined)
- **3 RAG modes** — no_rag, basic_rag, agentic_rag
- **3 consistency runs** per combination — measures output variance

### Running the evaluation

```bash
# Full evaluation (requires LLM API calls — can be expensive)
python3 evaluation/eval_runner.py

# Single RAG mode only
python3 evaluation/eval_runner.py --mode agentic_rag

# Single deal only
python3 evaluation/eval_runner.py --deal D01

# Validate setup without API calls
python3 evaluation/eval_runner.py --dry-run
```

Results are saved to `evaluation/results/` as JSON and CSV. Charts are saved to `evaluation/results/charts/`.

### Metrics

| Metric | Weight | Description |
|---|---|---|
| **Accuracy** | 35% | Does retrieved evidence match the deal category and leverage type? |
| **Reasoning quality** | 40% | Is the counter-offer grounded? Are leverage points specific and cited? |
| **Consistency** | 25% | Variance of `counter_offer_pct` across 3 identical runs (std dev < 1% = score 5) |

Composite score = `0.35 × accuracy + 0.40 × reasoning + 0.25 × consistency`

---

## API Reference (Agents)

### `agents/analyst.py`

```python
run_analyst(state: dict) -> dict
```

Returns partial state with: `retrieved_evidence`, `retrieved_evidence_text`, `retrieval_queries`, `analyst_summary`, `web_search_used`, `web_search_results`.

### `agents/strategist.py`

```python
run_strategist(state: dict) -> dict
```

Returns partial state with: `strategist_draft` (counter_offer_pct, opening_script, leverage_points, alt_asks, reasoning, confidence), `reflection_passed`, `reflection_notes`.

### `agents/vendor.py`

```python
run_vendor_turn(
    user_message: str,
    transcript: list,
    deal_facts: dict,
    hitl_proposal: dict,
    llm_model: str
) -> str

run_strategist_scoring(
    transcript: list,
    deal_facts: dict,
    hitl_proposal: dict,
    llm_model: str
) -> dict
```

### `graph/pipeline.py`

```python
run_pipeline(initial_state: dict) -> dict        # main pipeline → HITL pause
run_post_rehearsal(state: dict) -> dict          # scoring + save after rehearsal
```

### `memory/sqlite_store.py`

```python
save_negotiation(record: dict) -> int
load_history(business_id: str, limit: int = 20) -> list[dict]
get_summary_stats(business_id: str) -> dict
update_final_outcome(record_id: int, outcome: str)
get_all_businesses() -> list[str]
```

---

## Security Notes

- **`.env` is gitignored** — API keys are never committed.
- **SQL injection** — all SQLite queries use parameterised placeholders (`?`), no f-string interpolation.
- **XSS** — all user-supplied and LLM-generated text rendered inside `unsafe_allow_html=True` blocks is escaped with `html.escape()`.
- **No shell execution** — no `os.system()` or `subprocess` calls in the app or agent code.
- **PDF path safety** — `output_path` in `generate_scorecard_pdf()` is only used internally in evaluation scripts, never exposed to end users via the UI.
- **Key rotation** — If your OpenRouter key is ever exposed, rotate it immediately at [openrouter.ai/keys](https://openrouter.ai/keys) and update `.env`.

---

## Known Limitations

- **Knowledge base scope** — The 25 documents cover Indian SME market norms (prices in Rs.). Benchmarks may not directly translate to other geographies without document updates.
- **Embedding model** — `all-MiniLM-L6-v2` (384-dim) is fast and lightweight but has lower semantic accuracy than OpenAI `text-embedding-3-large`. Retrieval quality is good for this domain but not state-of-the-art.
- **Vendor agent concessions** — The vendor's maximum concession is hardcoded at 15% off the original quote. Edit `VENDOR_SYSTEM_PROMPT` in `agents/vendor.py` to adjust.
- **No authentication** — The app uses `business_id` as a lightweight identifier, not a secure login. Not suitable for multi-tenant production deployment without adding authentication.
- **LLM non-determinism** — Even at `temperature=0.1`, LLMs produce slightly different outputs across runs. The consistency metric in the evaluation framework measures this variance.
- **Web search fallback** — Tavily results are capped at 500 characters per result and 3 results total. For obscure items with no KB match, quality depends on what Tavily returns.

---

## Roadmap

- [ ] Real-time market price integration (e.g. commodity price APIs for F&B raw materials)
- [ ] Multi-user support with authentication
- [ ] Outcome tracking — record actual negotiation results vs. AI predictions
- [ ] Email/WhatsApp export of negotiation brief
- [ ] Voice rehearsal mode (speech-to-text input)
- [ ] Supplier database — save supplier profiles and historical concession patterns
- [ ] Multi-language support (Hindi, Tamil, Telugu for Indian market)

---

## License

This project is for educational and demonstration purposes.

---

*Built with LangGraph, LangChain, ChromaDB, Streamlit, and OpenRouter.*
