"""
vendor.py — The Vendor (adversary) agent for NegotiatorAI.

ROLE: A realistic, mildly resistant supplier representative who argues AGAINST
      the user's interest. This is a DISTINCT ADVERSARIAL PERSONA — not a reused
      prompt with different framing. It defends the original quote, makes limited
      concessions only under sustained pressure, and uses realistic supplier arguments.

Per plan Section 2: "must argue against the user's interest to create a realistic
rehearsal; a single agent cannot simultaneously advocate for and against the user."

Assumption: powered by the same LLM as the rest of the pipeline (GPT-4o-mini default),
but with an entirely separate system prompt. See code comment in config.py.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from config import get_llm, LLM_MODEL

# ---------------------------------------------------------------------------
# Vendor system prompt — adversarial but realistic
# ---------------------------------------------------------------------------
VENDOR_SYSTEM_PROMPT = """You are playing the role of a supplier sales representative in a negotiation rehearsal.

YOUR PERSONA:
- Name: Vendor/Supplier Rep (adapt to the specific supplier context)
- You represent the supplier's interests — NOT the buyer's
- You are professional, polite, but firm and resistant to discounting
- You believe your pricing is fair and justified
- You are experienced at handling negotiation tactics

YOUR BEHAVIOR RULES:
1. DEFEND YOUR QUOTE: Start by defending the original quoted price. Do not offer discounts without sustained pressure.
2. BE REALISTIC: Use real supplier arguments (cost increases, quality justification, market demand, thin margins).
3. CONCEDE SLOWLY: Only make concessions after 2-3 rounds of pressure. Start with small non-price concessions (free delivery, better payment terms) before touching price.
4. MAXIMUM PRICE CONCESSION: Never go below 85% of original quote without extraordinary pressure (competing quotes + volume commitment + repeat customer all combined).
5. SHOW PERSONALITY: You can be mildly frustrated, use slight hesitation, reference needing to "check with management" — make it feel real.
6. DO NOT CAPITULATE: This is a rehearsal — the user needs to practice handling resistance. Don't give in easily.

CONCESSION LADDER (follow this order):
- Round 1: Defend price. Maybe offer free delivery or slight payment term flexibility.
- Round 2: Acknowledge competitive market. Offer 2-3% discount maximum.
- Round 3: Under strong pressure (competing quotes + volume): offer 5-7% maximum.
- Round 4+: "I need to check with management" — then maybe 8-10% if deal facts strongly justify.

REALISTIC PUSHBACK PHRASES TO USE:
- "That's quite a bit below what we can do. Our costs have really gone up."
- "I appreciate you sharing that, but our margins are already very tight."
- "I'm not sure I can justify that to my management."
- "That competing quote doesn't match our quality level."
- "I'd need to check with my supervisor — can I get back to you?"
- "We treat all customers consistently — it's hard to make exceptions."

KEEP RESPONSES: Conversational length (2-4 sentences). Don't lecture. React to what the user just said."""


def run_vendor_turn(
    user_message: str,
    transcript: list,
    deal_facts: dict,
    hitl_proposal: dict,
    llm_model: str = LLM_MODEL,
) -> str:
    """
    Generate one Vendor agent response in the rehearsal loop.

    Args:
        user_message:   The buyer's (user's) latest message
        transcript:     Full conversation history so far [{"role": ..., "content": ...}]
        deal_facts:     Original deal context
        hitl_proposal:  The user's edited counter-offer and leverage points
        llm_model:      LLM to use

    Returns:
        Vendor's response string
    """
    llm = get_llm(model=llm_model, temperature=0.7)  # higher temp = more natural variation

    # Build context message for the vendor
    quoted_price = deal_facts.get("quoted_price", "our standard rate")
    item = deal_facts.get("item", "the goods")
    counter_pct = hitl_proposal.get("counter_offer_pct", 90)
    counter_amount = hitl_proposal.get("counter_offer_amount", 0)

    context = f"""[REHEARSAL CONTEXT — not visible to buyer]
Item being negotiated: {item}
Your (supplier's) original quoted price: {quoted_price} {deal_facts.get('quoted_price_unit', '')}
Buyer is pushing for: {counter_pct}% of your quote (approximately {counter_amount} {deal_facts.get('quoted_price_unit', '')})
Buyer's stated leverage: {hitl_proposal.get('leverage_points', [])}
Rounds of negotiation so far: {len([t for t in transcript if t.get('role') == 'vendor'])}

Remember: be resistant, defend your price, make the buyer work for any concession."""

    # Build message history for the LLM
    messages = [SystemMessage(content=VENDOR_SYSTEM_PROMPT + "\n\n" + context)]

    # Add conversation history
    for turn in transcript:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "vendor":
            messages.append(AIMessage(content=content))

    # Add the latest user message
    messages.append(HumanMessage(content=user_message))

    response = llm.invoke(messages)
    return response.content.strip()


def run_strategist_scoring(
    transcript: list,
    deal_facts: dict,
    hitl_proposal: dict,
    llm_model: str = LLM_MODEL,
) -> dict:
    """
    After rehearsal: Strategist scores the user's performance and generates coaching.

    Returns scorecard dict with:
      overall_score, assertiveness, leverage_use, pushback_handling,
      closing_technique, coaching_notes, strengths, improvements, final_script
    """
    import json

    llm = get_llm(model=llm_model, temperature=0.3)

    SCORING_PROMPT = """You are the Strategist coach reviewing a negotiation rehearsal.

Score the BUYER's performance (not the vendor's) on a 1-5 scale for each dimension.
Be honest and specific — this feedback helps the user improve.

OUTPUT JSON:
{
  "overall_score": <1-5 float>,
  "assertiveness": <1-5>,
  "leverage_use": <1-5>,
  "pushback_handling": <1-5>,
  "closing_technique": <1-5>,
  "coaching_notes": "<2-3 sentences: what the buyer did well and what to improve>",
  "strengths": ["<specific thing done well>", ...],
  "improvements": ["<specific thing to do differently>", ...],
  "final_script": "<A polished 3-4 sentence version of the buyer's best negotiation opening, incorporating improvements>",
  "estimated_outcome": "<what outcome this performance would likely achieve in a real negotiation>"
}"""

    # Format transcript for review
    transcript_text = "\n".join(
        f"{'BUYER' if t['role'] == 'user' else 'VENDOR'}: {t['content']}"
        for t in transcript
    )

    user_msg = f"""Negotiation Rehearsal Transcript:
{transcript_text}

Deal Context:
- Item: {deal_facts.get('item', 'N/A')}
- Original quote: {deal_facts.get('quoted_price', 'N/A')} {deal_facts.get('quoted_price_unit', '')}
- Target counter-offer: {hitl_proposal.get('counter_offer_pct', 'N/A')}% of quote
- Leverage points available: {hitl_proposal.get('leverage_points', [])}

Score the buyer's performance. Be specific — cite actual lines from the transcript."""

    messages = [
        SystemMessage(content=SCORING_PROMPT),
        HumanMessage(content=user_msg),
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    try:
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                try:
                    return json.loads(part)
                except Exception:
                    continue
        return json.loads(raw)
    except Exception:
        return {
            "overall_score": 3.0,
            "assertiveness": 3,
            "leverage_use": 3,
            "pushback_handling": 3,
            "closing_technique": 3,
            "coaching_notes": raw[:400],
            "strengths": [],
            "improvements": [],
            "final_script": "",
            "estimated_outcome": "Unable to parse scoring response.",
        }
