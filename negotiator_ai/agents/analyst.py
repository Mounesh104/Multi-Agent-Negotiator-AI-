"""
analyst.py — The Analyst agent for NegotiatorAI.

ROLE: Neutral, evidence-only researcher. No opinions. No recommendations.
      Retrieves and summarizes relevant negotiation tactics from the KB.

SYSTEM PROMPT defines a strictly neutral persona — the Analyst never tells
the user what to do; it only reports what the evidence says.

ADAPTIVE RETRIEVAL LOGIC (what makes this "agentic" vs. "basic RAG"):
  1. First retrieval: general tactics for item category + deal type
  2. Conditional second retrieval: if user is a repeat customer → loyalty tactics
  3. Re-query (triggered by Strategist reflection failure): narrower/rephrased query
  4. Fallback to web_search: if top KB similarity score < CONFIDENCE_THRESHOLD
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage
from config import get_llm, CONFIDENCE_THRESHOLD, LLM_MODEL
from knowledge_base.retrieval import (
    retrieve_tactics,
    retrieve_with_score,
    get_top_score,
    format_retrieved_context,
    web_search_fallback,
    format_web_results,
)

# ---------------------------------------------------------------------------
# Analyst system prompt — strictly neutral, evidence-only
# ---------------------------------------------------------------------------
ANALYST_SYSTEM_PROMPT = """You are the Analyst for NegotiatorAI.

YOUR ROLE: You are a neutral, objective research agent. You do not give opinions, recommendations, or advice. You ONLY:
1. Summarize what the retrieved evidence says about negotiation tactics relevant to this specific deal.
2. Highlight which tactics apply given the user's stated leverage (repeat customer, competing quotes, etc.).
3. Note gaps: if the evidence is thin or doesn't match the deal well, say so explicitly.
4. Report relevant benchmarks from the evidence (percentage ranges, industry norms).

STRICT RULES:
- Do NOT say "you should" or "I recommend" — report facts only.
- Do NOT guess or invent benchmarks — only cite what is in the retrieved evidence.
- Do NOT advocate for the user. That is the Strategist's job.
- If the evidence is weak or missing, say: "The evidence for this specific situation is limited. A web search or broader query may be needed."
- Keep your summary under 350 words. Be specific, not generic.

OUTPUT FORMAT:
Return a JSON object with exactly these fields:
{
  "analyst_summary": "...(evidence summary, max 350 words)...",
  "applicable_tactics": ["tactic 1", "tactic 2", ...],
  "relevant_benchmarks": ["benchmark 1", "benchmark 2", ...],
  "evidence_strength": "strong | moderate | weak",
  "evidence_gaps": "...(what is missing or unclear from the evidence)..."
}
"""


def _build_analyst_query(deal_facts: dict, query_type: str = "primary", rephrase_hint: str = "") -> str:
    """
    Build a retrieval query from deal facts.
    query_type: "primary" | "loyalty" | "rephrased"
    """
    item = deal_facts.get("item", "goods")
    category = deal_facts.get("category", "general")
    qty = deal_facts.get("quantity", "standard")
    has_competing = deal_facts.get("has_competing_quotes", False)
    is_repeat = deal_facts.get("is_repeat_customer", False)

    if query_type == "primary":
        base = f"{category} {item} bulk discount negotiation tactics"
        if has_competing:
            base += " competing quote leverage"
        if deal_facts.get("can_commit_volume"):
            base += " volume commitment"
        return base

    elif query_type == "loyalty":
        # Second targeted retrieval for repeat customers
        months = deal_facts.get("commitment_months", 0)
        spend = deal_facts.get("cumulative_spend", 0)
        return f"repeat customer loyalty leverage {category} supplier negotiation tenure discount {spend} cumulative spend"

    elif query_type == "rephrased":
        # Narrower query after Strategist reflection fails
        if rephrase_hint:
            return rephrase_hint
        return f"specific negotiation tactics {item} {category} payment terms delivery penalty small business"

    elif query_type == "payment":
        terms = deal_facts.get("payment_terms", "Net 30")
        return f"payment terms negotiation {terms} extension early payment discount"

    return f"negotiation tactics {item}"


def run_analyst(state: dict) -> dict:
    """
    Analyst agent node — adaptive retrieval logic.
    Called from the LangGraph pipeline.

    Returns partial state dict with:
      - retrieved_evidence (list of Documents)
      - retrieved_evidence_text (formatted string)
      - retrieval_queries (audit trail)
      - analyst_summary (structured JSON parsed to dict)
      - web_search_used (bool)
      - web_search_results (str)
    """
    deal_facts = state.get("deal_facts", {})
    rag_mode = state.get("rag_mode", "agentic_rag")
    llm_model = state.get("llm_model", LLM_MODEL)
    rephrase_hint = state.get("reflection_notes", "")  # passed if Strategist triggered re-retrieve
    existing_queries = state.get("retrieval_queries", [])

    all_docs = []
    queries_used = list(existing_queries)
    web_search_used = False
    web_results_text = ""

    # ------------------------------------------------------------------
    # NO-RAG mode: skip all retrieval
    # ------------------------------------------------------------------
    if rag_mode == "no_rag":
        return {
            "retrieved_evidence": [],
            "retrieved_evidence_text": "No retrieval performed (No-RAG mode).",
            "retrieval_queries": queries_used,
            "analyst_summary": "No-RAG mode: evidence synthesis skipped.",
            "web_search_used": False,
            "web_search_results": "",
        }

    # ------------------------------------------------------------------
    # BASIC-RAG mode: exactly ONE fixed retrieval, no reflection/re-query
    # ------------------------------------------------------------------
    if rag_mode == "basic_rag":
        query = _build_analyst_query(deal_facts, query_type="primary")
        queries_used.append(query)
        docs = retrieve_tactics(query, k=4)
        evidence_text = format_retrieved_context(docs)
        summary = _synthesize_evidence(deal_facts, docs, evidence_text, llm_model)
        return {
            "retrieved_evidence": docs,
            "retrieved_evidence_text": evidence_text,
            "retrieval_queries": queries_used,
            "analyst_summary": summary,
            "web_search_used": False,
            "web_search_results": "",
        }

    # ------------------------------------------------------------------
    # AGENTIC-RAG mode: adaptive, multi-step, conditional retrieval
    # ------------------------------------------------------------------

    # Step 1: Primary retrieval (general category + deal type)
    primary_query = _build_analyst_query(deal_facts, query_type="primary")
    queries_used.append(primary_query)
    scored_docs = retrieve_with_score(primary_query, k=4)
    primary_docs = [doc for doc, _ in scored_docs]
    top_score = max((s for _, s in scored_docs), default=0.0)
    all_docs.extend(primary_docs)

    # Step 2: Conditional loyalty retrieval if repeat customer
    if deal_facts.get("is_repeat_customer", False):
        loyalty_query = _build_analyst_query(deal_facts, query_type="loyalty")
        queries_used.append(loyalty_query)
        loyalty_docs = retrieve_tactics(loyalty_query, k=3)
        # Deduplicate by page_content
        existing_contents = {d.page_content for d in all_docs}
        new_docs = [d for d in loyalty_docs if d.page_content not in existing_contents]
        all_docs.extend(new_docs)

    # Step 3: Re-query if this call was triggered by Strategist reflection failure
    requery_iter = state.get("requery_iteration", 0)
    if requery_iter > 0 and rephrase_hint:
        narrow_query = _build_analyst_query(deal_facts, query_type="rephrased", rephrase_hint=rephrase_hint)
        queries_used.append(narrow_query)
        narrow_docs = retrieve_tactics(narrow_query, k=3)
        existing_contents = {d.page_content for d in all_docs}
        new_docs = [d for d in narrow_docs if d.page_content not in existing_contents]
        all_docs.extend(new_docs)

    # Step 4: Payment terms secondary retrieval (always useful)
    payment_query = _build_analyst_query(deal_facts, query_type="payment")
    if payment_query not in queries_used:
        queries_used.append(payment_query)
        payment_docs = retrieve_tactics(payment_query, k=2)
        existing_contents = {d.page_content for d in all_docs}
        new_docs = [d for d in payment_docs if d.page_content not in existing_contents]
        all_docs.extend(new_docs)

    # Step 5: Web search fallback if KB confidence is low
    if top_score < CONFIDENCE_THRESHOLD:
        web_query = f"{deal_facts.get('item', '')} {deal_facts.get('category', '')} supplier pricing negotiation"
        web_results = web_search_fallback(web_query)
        web_results_text = format_web_results(web_results)
        web_search_used = True

    # Synthesize evidence into analyst summary
    evidence_text = format_retrieved_context(all_docs[:8])  # cap at 8 chunks for context window
    if web_search_used:
        evidence_text += f"\n\n=== WEB SEARCH RESULTS ===\n{web_results_text}"

    summary = _synthesize_evidence(deal_facts, all_docs, evidence_text, llm_model)

    return {
        "retrieved_evidence": all_docs,
        "retrieved_evidence_text": evidence_text,
        "retrieval_queries": queries_used,
        "analyst_summary": summary,
        "web_search_used": web_search_used,
        "web_search_results": web_results_text,
    }


def _synthesize_evidence(deal_facts: dict, docs, evidence_text: str, llm_model: str) -> str:
    """
    Call the LLM to synthesize retrieved docs into a structured analyst summary.
    Returns the raw JSON string from the model.
    """
    import json

    llm = get_llm(model=llm_model, temperature=0.1)  # low temp for factual reporting

    user_msg = f"""Deal Facts:
- Item: {deal_facts.get('item', 'N/A')}
- Category: {deal_facts.get('category', 'N/A')}
- Quantity: {deal_facts.get('quantity', 'N/A')}
- Quoted Price: {deal_facts.get('quoted_price', 'N/A')} {deal_facts.get('quoted_price_unit', '')}
- Payment Terms: {deal_facts.get('payment_terms', 'N/A')}
- Repeat Customer: {deal_facts.get('is_repeat_customer', False)} (orders: {deal_facts.get('repeat_order_count', 0)}, spend: {deal_facts.get('cumulative_spend', 0)})
- Has Competing Quotes: {deal_facts.get('has_competing_quotes', False)} (count: {deal_facts.get('competing_quote_count', 0)})
- Volume Commitment Available: {deal_facts.get('can_commit_volume', False)} for {deal_facts.get('commitment_months', 0)} months

Retrieved Evidence:
{evidence_text}

Based ONLY on the retrieved evidence above (not general knowledge), provide your structured analysis."""

    messages = [
        SystemMessage(content=ANALYST_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    # Attempt to parse JSON — if it fails, return raw string
    try:
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        return json.dumps(parsed)  # re-serialize as clean JSON
    except Exception:
        return raw  # return as-is, Strategist will handle gracefully
