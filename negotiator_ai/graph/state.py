"""
state.py — LangGraph TypedDict state definition for NegotiatorAI.

Every field in this state is passed between graph nodes.
All agents READ from state; each node returns a PARTIAL dict to update state.
"""

from typing import TypedDict, List, Optional, Any


class DealFacts(TypedDict, total=False):
    """Structured deal information entered by the user."""
    item: str                   # What is being purchased
    category: str               # Derived category: packaging / raw_materials / equipment / service / logistics / office
    quantity: str               # Quantity / order size description
    quoted_price: float         # Supplier's quoted price per unit or total
    quoted_price_unit: str      # "per unit" | "total" | "per kg" | "per month"
    payment_terms: str          # Supplier's quoted payment terms (e.g., "Net 30")
    delivery_days: int          # Supplier's quoted lead time in days
    supplier_name: str          # Supplier name (optional)
    industry: str               # User's industry

    # Leverage facts — critical for agent decision-making
    is_repeat_customer: bool    # Has the user bought from this supplier before?
    repeat_order_count: int     # Number of previous orders (if repeat)
    cumulative_spend: float     # Total historical spend with this supplier
    has_competing_quotes: bool  # Does the user have quotes from other suppliers?
    competing_quote_price: float  # Best competing price (if available)
    competing_quote_count: int  # Number of competing quotes
    can_commit_volume: bool     # Can user offer a volume commitment?
    commitment_months: int      # Duration of potential volume commitment
    urgency: str                # "low" | "medium" | "high" (keep internal, don't reveal to Vendor)
    additional_context: str     # Free text: any other relevant context


class NegotiationState(TypedDict, total=False):
    """
    Full LangGraph state for one negotiation session.
    Passed through the entire pipeline: load_history → analyst → strategist →
    reflection → [re_retrieve] → hitl → vendor_rehearsal → scoring → save.
    """

    # -----------------------------------------------------------------------
    # Session metadata
    # -----------------------------------------------------------------------
    business_id: str            # Unique identifier for the business
    business_name: str
    rag_mode: str               # "no_rag" | "basic_rag" | "agentic_rag"
    llm_model: str              # LLM model name for this run
    session_id: str             # UUID for this specific negotiation session

    # -----------------------------------------------------------------------
    # Deal information (Phase 2: user input)
    # -----------------------------------------------------------------------
    deal_facts: DealFacts

    # -----------------------------------------------------------------------
    # Analyst outputs (Phase 2)
    # -----------------------------------------------------------------------
    retrieval_queries: List[str]         # Audit trail of all queries made
    retrieved_evidence: List[Any]        # List of langchain Document objects
    retrieved_evidence_text: str         # Formatted text version for LLM prompts
    web_search_used: bool                # Whether web search fallback was triggered
    web_search_results: str             # Formatted web search results (if used)
    analyst_summary: str                 # Analyst's synthesis of retrieved evidence

    # -----------------------------------------------------------------------
    # Strategist / reflection (Phase 2)
    # -----------------------------------------------------------------------
    strategist_draft: dict               # counter_offer_pct, alt_asks, leverage_points, reasoning
    reflection_passed: bool              # Did Strategist's confidence check pass?
    reflection_notes: str                # Why reflection failed (if it did)
    requery_iteration: int               # Loop counter (max MAX_REQUERY_ITERATIONS)

    # -----------------------------------------------------------------------
    # HITL step (Phase 5 — user edits the Strategist's draft)
    # -----------------------------------------------------------------------
    hitl_edited: dict                    # User-edited version of strategist_draft
    # Fields: counter_offer_pct, alt_asks (list), leverage_points (list), notes

    # -----------------------------------------------------------------------
    # Vendor rehearsal (Phase 4)
    # -----------------------------------------------------------------------
    rehearsal_transcript: List[dict]     # [{"role": "user"|"vendor", "content": "..."}]
    rehearsal_complete: bool

    # -----------------------------------------------------------------------
    # Scoring / scorecard (Phase 4)
    # -----------------------------------------------------------------------
    scorecard: dict
    # Fields: overall_score (1–5), assertiveness (1–5), leverage_use (1–5),
    #         pushback_handling (1–5), coaching_notes (str), final_script (str)

    # -----------------------------------------------------------------------
    # Memory (Phase 3)
    # -----------------------------------------------------------------------
    history: List[dict]                  # Past negotiations loaded from SQLite

    # -----------------------------------------------------------------------
    # Evaluation metadata (Phase 6 — only populated by eval_runner.py)
    # -----------------------------------------------------------------------
    eval_latency_ms: float
    eval_token_count: int
    eval_run_index: int                  # 1, 2, or 3 (for consistency measurement)
