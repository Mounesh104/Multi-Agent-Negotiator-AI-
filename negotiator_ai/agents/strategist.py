"""
strategist.py — The Strategist agent for NegotiatorAI.

ROLE: The user's advocate and coach. Persuasive, self-reflective.
      MUST ground every recommendation in retrieved evidence + user-stated leverage.
      If ungrounded → triggers reflection failure → Analyst re-retrieves.

REFLECTION LOOP (mandatory per plan Section 3):
  - Checks draft counter-offer against (a) retrieved evidence, (b) user's leverage facts
  - Sets reflection_passed = False if the draft is not evidence-grounded
  - Passes reflection_notes back to Analyst for narrower re-query
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage
from config import get_llm, LLM_MODEL

# ---------------------------------------------------------------------------
# Strategist system prompt — user's advocate, self-reflective
# ---------------------------------------------------------------------------
STRATEGIST_SYSTEM_PROMPT = """You are the Strategist for NegotiatorAI.

YOUR ROLE: You are the user's negotiation coach and advocate. Your job is to turn the Analyst's evidence into a concrete, actionable counter-offer and negotiation strategy that the user can use.

MANDATORY RULES:
1. GROUND EVERY CLAIM. Every recommended counter-offer percentage, every tactic, every leverage point MUST be traceable to either:
   (a) Specific evidence in the Analyst's retrieved documents, OR
   (b) Facts the user explicitly provided (leverage info, volume, repeat status, etc.)
   
2. DO NOT GUESS OR INVENT. If you cannot ground a recommendation in evidence or user facts, do NOT make it up. Instead flag it with: "[UNGROUNDED — needs more evidence]"

3. SELF-REFLECTION. Before finalizing your draft, check each major recommendation:
   - "Is this counter-offer percentage backed by a specific document or benchmark?"
   - "Is this leverage point real (user told us this) or assumed?"
   - If either answer is "no" → mark as ungrounded and trigger re-retrieval

4. BE SPECIFIC AND PRACTICAL. Don't give generic advice. Reference the actual deal facts.

5. PERSUASION APPROACH: Use professional, confident framing. The user should feel prepared and empowered, not aggressive.

OUTPUT FORMAT — Return valid JSON with these exact fields:
{
  "counter_offer_pct": <float — percentage of quoted price to counter at, e.g. 85.0 means 15% discount>,
  "counter_offer_amount": <float — calculated counter-offer price>,
  "primary_tactic": "<main negotiation approach in 1-2 sentences>",
  "alt_asks": [
    "<alternative ask 1 — non-price term>",
    "<alternative ask 2>",
    "<alternative ask 3>"
  ],
  "leverage_points": [
    "<leverage point 1 with specific source: user-stated fact or document reference>",
    "<leverage point 2>",
    "<leverage point 3>"
  ],
  "opening_script": "<2-3 sentence opening statement the user can use verbatim>",
  "reasoning": "<brief explanation of why this counter-offer is grounded — cite specific evidence>",
  "confidence": "high | medium | low",
  "ungrounded_items": ["<list any items that could not be grounded — empty list if all grounded>"],
  "reflection_notes": "<if confidence is low or items ungrounded, describe what additional information or evidence would help>"
}
"""

REFLECTION_SYSTEM_PROMPT = """You are performing a critical self-review of a negotiation strategy draft.

YOUR TASK: Evaluate whether the draft counter-offer and strategy are properly grounded.

Check each item against TWO standards:
1. EVIDENCE GROUNDING: Is this backed by retrieved negotiation tactic documents?
2. LEVERAGE GROUNDING: Is this traceable to leverage facts the user actually provided?

Return a JSON with:
{
  "reflection_passed": <true | false>,
  "confidence_score": <float 0.0-1.0>,
  "grounding_issues": ["<issue 1>", ...],
  "reflection_notes": "<specific narrower query or clarification needed if reflection failed>"
}

PASS criteria: confidence_score >= 0.65 AND no major ungrounded price claims.
FAIL criteria: counter-offer percentage has no evidence support, OR leverage points are invented.
"""


def run_strategist(state: dict) -> dict:
    """
    Strategist agent node.
    Generates draft counter-offer + reflection check.

    Returns partial state:
      - strategist_draft (dict)
      - reflection_passed (bool)
      - reflection_notes (str)
    """
    deal_facts = state.get("deal_facts", {})
    rag_mode = state.get("rag_mode", "agentic_rag")
    llm_model = state.get("llm_model", LLM_MODEL)
    analyst_summary = state.get("analyst_summary", "")
    evidence_text = state.get("retrieved_evidence_text", "")
    history = state.get("history", [])

    llm = get_llm(model=llm_model, temperature=0.4)

    # Build history context
    history_context = ""
    if history:
        recent = history[-3:]  # last 3 negotiations
        history_context = "Past negotiations with this supplier:\n"
        for h in recent:
            history_context += (
                f"- {h.get('item', '?')}: quoted {h.get('quoted_price', '?')}, "
                f"settled at {h.get('counter_offer', '?')}, "
                f"savings: {h.get('estimated_savings', '?')}\n"
            )

    # Build user message
    user_msg = f"""Deal Facts:
- Business: {state.get('business_name', 'N/A')} | Industry: {deal_facts.get('industry', 'N/A')}
- Item: {deal_facts.get('item', 'N/A')} | Category: {deal_facts.get('category', 'N/A')}
- Quantity: {deal_facts.get('quantity', 'N/A')}
- Quoted Price: {deal_facts.get('quoted_price', 'N/A')} {deal_facts.get('quoted_price_unit', '')}
- Quoted Payment Terms: {deal_facts.get('payment_terms', 'N/A')}
- Delivery Days: {deal_facts.get('delivery_days', 'N/A')}
- Supplier: {deal_facts.get('supplier_name', 'Not specified')}

User's Leverage:
- Repeat Customer: {deal_facts.get('is_repeat_customer', False)}
  (Orders: {deal_facts.get('repeat_order_count', 0)}, Cumulative spend: ₹{deal_facts.get('cumulative_spend', 0):,.0f})
- Has Competing Quotes: {deal_facts.get('has_competing_quotes', False)}
  (Count: {deal_facts.get('competing_quote_count', 0)}, Best price: {deal_facts.get('competing_quote_price', 'not stated')})
- Volume Commitment: {deal_facts.get('can_commit_volume', False)} for {deal_facts.get('commitment_months', 0)} months
- Additional Context: {deal_facts.get('additional_context', 'None')}

{history_context}

RAG Mode: {rag_mode}

Analyst Evidence Summary:
{analyst_summary}

Full Retrieved Evidence:
{evidence_text if rag_mode != 'no_rag' else 'No retrieval performed (No-RAG mode) — use parametric knowledge only.'}

Generate a grounded counter-offer strategy. Remember: cite your sources for every major claim."""

    messages = [
        SystemMessage(content=STRATEGIST_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    # Parse the draft
    draft = _parse_json_response(raw)

    # Run reflection check (only in agentic_rag mode)
    if rag_mode == "agentic_rag":
        reflection_result = _run_reflection(draft, deal_facts, evidence_text, analyst_summary, llm_model)
        reflection_passed = reflection_result.get("reflection_passed", True)
        reflection_notes = reflection_result.get("reflection_notes", "")

        # Update draft confidence based on reflection
        if not reflection_passed:
            draft["confidence"] = "low"
    else:
        # For no_rag and basic_rag: skip reflection loop
        reflection_passed = True
        reflection_notes = ""

    return {
        "strategist_draft": draft,
        "reflection_passed": reflection_passed,
        "reflection_notes": reflection_notes,
    }


def _run_reflection(draft: dict, deal_facts: dict, evidence_text: str, analyst_summary: str, llm_model: str) -> dict:
    """
    Self-reflection check: verify the draft is grounded in evidence and user facts.
    Returns reflection result dict.
    """
    llm = get_llm(model=llm_model, temperature=0.1)

    reflection_msg = f"""Draft strategy to evaluate:
{json.dumps(draft, indent=2)}

Evidence available:
{evidence_text[:2000]}  

Analyst summary:
{analyst_summary[:500]}

User's actual leverage facts:
- Repeat customer: {deal_facts.get('is_repeat_customer', False)} (orders: {deal_facts.get('repeat_order_count', 0)})
- Has competing quotes: {deal_facts.get('has_competing_quotes', False)}
- Volume commitment: {deal_facts.get('can_commit_volume', False)}
- Quoted price: {deal_facts.get('quoted_price', 'N/A')} {deal_facts.get('quoted_price_unit', '')}

Evaluate: is the counter_offer_pct backed by evidence? Are leverage_points real (not invented)?"""

    messages = [
        SystemMessage(content=REFLECTION_SYSTEM_PROMPT),
        HumanMessage(content=reflection_msg),
    ]

    response = llm.invoke(messages)
    return _parse_json_response(response.content.strip())


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from LLM response, handling markdown code fences."""
    try:
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    return json.loads(part)
                except Exception:
                    continue
        return json.loads(raw)
    except Exception:
        # Fallback: return structured error dict
        return {
            "counter_offer_pct": 90.0,
            "counter_offer_amount": 0,
            "primary_tactic": "Unable to parse response — review manually.",
            "alt_asks": [],
            "leverage_points": [],
            "opening_script": "",
            "reasoning": raw[:500],
            "confidence": "low",
            "ungrounded_items": ["parse_error"],
            "reflection_notes": "Response parsing failed — re-retrieve with broader query.",
            "reflection_passed": False,
        }
