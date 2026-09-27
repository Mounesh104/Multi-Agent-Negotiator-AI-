"""
nodes.py — All LangGraph node functions for NegotiatorAI.

Each node function receives the full NegotiationState dict and returns
a PARTIAL dict with only the fields it modifies (LangGraph merges them).
"""

import os
import sys
import uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.analyst import run_analyst
from agents.strategist import run_strategist
from agents.vendor import run_strategist_scoring
from memory.sqlite_store import load_history, save_negotiation
from config import MAX_REQUERY_ITERATIONS, LLM_MODEL


def node_load_history(state: dict) -> dict:
    """
    Load past negotiation history from SQLite for this business_id.
    Injects history into state for Strategist to reference.
    """
    business_id = state.get("business_id", "default")
    history = load_history(business_id)

    # Generate session_id if not set
    session_id = state.get("session_id") or str(uuid.uuid4())[:8]

    return {
        "history": history,
        "session_id": session_id,
        "requery_iteration": 0,  # reset loop counter
        "rehearsal_transcript": [],
        "rehearsal_complete": False,
        "web_search_used": False,
    }


def node_analyst_retrieve(state: dict) -> dict:
    """
    Analyst agent node — adaptive retrieval (or skip for no_rag).
    Delegates to agents/analyst.py for all logic.
    """
    return run_analyst(state)


def node_strategist_draft(state: dict) -> dict:
    """
    Strategist agent node — generates counter-offer draft with reflection.
    Delegates to agents/strategist.py for all logic.
    """
    return run_strategist(state)


def node_reflection_check(state: dict) -> dict:
    """
    Reflection check node — determines whether to re-retrieve or proceed.
    In no_rag and basic_rag modes, always passes (no reflection loop).

    This node is a routing checkpoint — it increments the loop counter
    but doesn't call any LLM. The routing decision is made by the
    conditional edge function in pipeline.py.
    """
    rag_mode = state.get("rag_mode", "agentic_rag")
    current_iter = state.get("requery_iteration", 0)
    reflection_passed = state.get("reflection_passed", True)

    # Force pass if not in agentic mode or max iterations reached
    if rag_mode != "agentic_rag" or current_iter >= MAX_REQUERY_ITERATIONS:
        return {"reflection_passed": True, "requery_iteration": current_iter}

    # If failed, increment loop counter
    if not reflection_passed:
        return {"requery_iteration": current_iter + 1}

    return {"requery_iteration": current_iter}


def node_re_retrieve(state: dict) -> dict:
    """
    Re-retrieve node — triggered when Strategist reflection fails.
    Sets a flag so Analyst uses the narrower re-query path.
    The actual retrieval happens in node_analyst_retrieve on the next iteration.
    """
    iteration = state.get("requery_iteration", 1)
    reflection_notes = state.get("reflection_notes", "")

    print(f"[Pipeline] Re-retrieval triggered (iteration {iteration}). Notes: {reflection_notes}")

    # State update: analyst will see requery_iteration > 0 and use rephrased query
    return {
        "requery_iteration": iteration,
        # Clear previous evidence so analyst starts fresh on re-query
        "retrieved_evidence": [],
        "retrieved_evidence_text": "",
    }


def node_strategist_score(state: dict) -> dict:
    """
    Strategist scoring node — called after rehearsal completes.
    Scores the user's rehearsal performance and generates coaching.
    """
    transcript = state.get("rehearsal_transcript", [])
    deal_facts = state.get("deal_facts", {})
    hitl_proposal = state.get("hitl_edited") or state.get("strategist_draft", {})
    llm_model = state.get("llm_model", LLM_MODEL)

    if not transcript:
        # No rehearsal performed — generate a pre-rehearsal scorecard
        scorecard = {
            "overall_score": 0,
            "assertiveness": 0,
            "leverage_use": 0,
            "pushback_handling": 0,
            "closing_technique": 0,
            "coaching_notes": "No rehearsal performed. Start the rehearsal to get scored.",
            "strengths": [],
            "improvements": [],
            "final_script": hitl_proposal.get("opening_script", ""),
            "estimated_outcome": "Complete rehearsal first.",
        }
    else:
        scorecard = run_strategist_scoring(transcript, deal_facts, hitl_proposal, llm_model)

    return {"scorecard": scorecard}


def node_save_memory(state: dict) -> dict:
    """
    Save negotiation record to SQLite persistent memory.
    Called after scoring completes.
    """
    import json

    business_id = state.get("business_id", "default")
    deal_facts = state.get("deal_facts", {})
    scorecard = state.get("scorecard", {})
    hitl = state.get("hitl_edited") or state.get("strategist_draft", {})

    # Build the record to save
    record = {
        "business_id": business_id,
        "session_id": state.get("session_id", ""),
        "item": deal_facts.get("item", ""),
        "category": deal_facts.get("category", ""),
        "supplier_name": deal_facts.get("supplier_name", ""),
        "quoted_price": deal_facts.get("quoted_price", 0),
        "quoted_price_unit": deal_facts.get("quoted_price_unit", ""),
        "counter_offer": hitl.get("counter_offer_amount", 0),
        "counter_offer_pct": hitl.get("counter_offer_pct", 0),
        "final_outcome": "",  # to be filled in by user after real negotiation
        "tactics_used": json.dumps(hitl.get("leverage_points", [])),
        "estimated_savings": _calc_savings(deal_facts, hitl),
        "overall_score": scorecard.get("overall_score", 0),
        "rag_mode": state.get("rag_mode", "agentic_rag"),
        "llm_model": state.get("llm_model", LLM_MODEL),
        "retrieval_queries": json.dumps(state.get("retrieval_queries", [])),
        "web_search_used": state.get("web_search_used", False),
    }

    save_negotiation(record)

    return {}  # no state changes — just side effect


def _calc_savings(deal_facts: dict, hitl: dict) -> float:
    """
    Estimate total savings vs. quoted price.

    Fix #2: When price_unit is 'total', 'per month', or 'per shipment', the
    quoted_price is already a lump-sum figure — multiplying savings by
    quantity would inflate the result massively (e.g. Rs.50,000 total x 500
    units = Rs.25,000,000). Only multiply by quantity for per-unit pricing.
    """
    try:
        quoted = float(deal_facts.get("quoted_price", 0))
        counter_pct = float(hitl.get("counter_offer_pct", 100))
        counter_amount = quoted * (counter_pct / 100)
        savings = quoted - counter_amount

        # Units where quoted_price is already a total — do NOT multiply by qty
        lump_sum_units = {"total", "per month", "per shipment", "per set"}
        price_unit = str(deal_facts.get("quoted_price_unit", "")).strip().lower()
        if price_unit in lump_sum_units:
            return round(savings, 2)

        # Per-unit pricing: multiply savings by quantity
        qty_str = str(deal_facts.get("quantity", "1")).replace(",", "").split()[0]
        qty = float(qty_str) if qty_str.replace(".", "").isdigit() else 1
        return round(savings * qty, 2)
    except Exception:
        return 0.0
