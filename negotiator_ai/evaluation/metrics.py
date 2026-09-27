"""
metrics.py — Scoring helpers for Phase 6 evaluation.
"""

import json
import statistics
from typing import List


def score_accuracy(retrieved_queries: list, deal_facts: dict, analyst_summary: str) -> dict:
    """
    Score retrieval accuracy: does the retrieved tactic match the deal's category and leverage type?
    Manual rubric (1–5) approximated programmatically.

    Returns dict with score and rationale.
    """
    category = deal_facts.get("category", "")
    is_repeat = deal_facts.get("is_repeat_customer", False)
    has_competing = deal_facts.get("has_competing_quotes", False)

    if isinstance(analyst_summary, str):
        try:
            parsed = json.loads(analyst_summary)
            summary_text = parsed.get("analyst_summary", analyst_summary)
            evidence_strength = parsed.get("evidence_strength", "unknown")
            applicable_tactics = parsed.get("applicable_tactics", [])
        except Exception:
            summary_text = analyst_summary
            evidence_strength = "unknown"
            applicable_tactics = []
    else:
        summary_text = str(analyst_summary)
        evidence_strength = "unknown"
        applicable_tactics = []

    # Heuristic scoring
    score = 3  # baseline

    # +1 if evidence strength is strong
    if evidence_strength == "strong":
        score += 1
    elif evidence_strength == "weak":
        score -= 1

    # +1 if category-specific tactic found
    category_keywords = {
        "packaging": ["packaging", "box", "container", "label"],
        "raw_materials": ["raw material", "ingredient", "commodity", "food"],
        "equipment": ["equipment", "rental", "machinery", "amc"],
        "service": ["service", "contract", "amc", "maintenance"],
        "logistics": ["logistics", "freight", "shipping", "delivery"],
        "office_supplies": ["office", "supplies", "furniture", "consumable"],
    }
    kws = category_keywords.get(category, [])
    if any(kw in summary_text.lower() for kw in kws):
        score += 0.5

    # +0.5 if loyalty tactic retrieved for repeat customer
    if is_repeat and any("loyal" in t.lower() or "repeat" in t.lower() for t in applicable_tactics):
        score += 0.5

    # +0.5 if competing quote tactic retrieved when user has competing quotes
    if has_competing and any("compet" in t.lower() or "quote" in t.lower() for t in applicable_tactics):
        score += 0.5

    score = min(5.0, max(1.0, score))

    return {
        "accuracy_score": round(score, 2),
        "evidence_strength": evidence_strength,
        "applicable_tactics_count": len(applicable_tactics),
        "category_matched": any(kw in summary_text.lower() for kw in kws),
    }


def score_reasoning_quality(strategist_draft: dict) -> dict:
    """
    Score reasoning quality: does the Strategist cite specific evidence vs. generic advice?
    1–5 manual rubric approximated from draft content.
    """
    reasoning = strategist_draft.get("reasoning", "")
    confidence = strategist_draft.get("confidence", "low")
    ungrounded = strategist_draft.get("ungrounded_items", [])
    leverage_points = strategist_draft.get("leverage_points", [])

    score = 3  # baseline

    # +1 if confidence is high
    if confidence == "high":
        score += 1
    elif confidence == "low":
        score -= 1

    # -1 if many ungrounded items
    if len(ungrounded) >= 3:
        score -= 1
    elif not ungrounded:
        score += 0.5

    # +0.5 if reasoning is substantial (>100 chars)
    if len(reasoning) > 100:
        score += 0.5

    # +0.5 if leverage points are specific (not generic)
    specific_signals = ["₹", "%", "months", "orders", "quote", "competing", "cumulative"]
    if any(sig in " ".join(leverage_points) for sig in specific_signals):
        score += 0.5

    score = min(5.0, max(1.0, score))

    return {
        "reasoning_score": round(score, 2),
        "confidence_level": confidence,
        "ungrounded_count": len(ungrounded),
        "leverage_point_count": len(leverage_points),
    }


def score_consistency(runs: List[dict]) -> dict:
    """
    Score response consistency: run same deal 3×, measure variance of
    the counter-offer percentage across runs.

    Args:
        runs: List of result dicts from run_single() — each has a top-level
              "counter_offer_pct" field (flat, not nested under strategist_draft).
              Also accepts the old nested format {"strategist_draft": {"counter_offer_pct": ...}}
              for backwards compatibility.

    Returns:
        consistency metrics dict.

    Bug fix: the original code looked for r["strategist_draft"]["counter_offer_pct"]
    but run_single() returns counter_offer_pct at the top level. This meant
    score_consistency always returned the default 3.0 regardless of real variance.
    Now checks both locations so it works with both the eval pipeline and direct calls.
    """
    if not runs:
        return {"consistency_score": 0, "std_dev_pct": 0, "pct_values": []}

    pct_values = []
    for r in runs:
        # Check top-level first (run_single output), then nested (direct draft dict)
        pct = r.get("counter_offer_pct") or r.get("strategist_draft", {}).get("counter_offer_pct", 0)
        if pct:
            pct_values.append(float(pct))

    if len(pct_values) < 2:
        return {"consistency_score": 3.0, "std_dev_pct": 0, "pct_values": pct_values}

    std_dev = statistics.stdev(pct_values)
    mean_pct = statistics.mean(pct_values)

    # Convert std_dev to score: <1% = 5, 1-2% = 4, 2-4% = 3, 4-7% = 2, >7% = 1
    if std_dev < 1.0:
        consistency_score = 5.0
    elif std_dev < 2.0:
        consistency_score = 4.0
    elif std_dev < 4.0:
        consistency_score = 3.0
    elif std_dev < 7.0:
        consistency_score = 2.0
    else:
        consistency_score = 1.0

    return {
        "consistency_score": consistency_score,
        "std_dev_pct": round(std_dev, 3),
        "mean_counter_offer_pct": round(mean_pct, 2),
        "pct_values": pct_values,
        "range_pct": round(max(pct_values) - min(pct_values), 2),
    }


def compute_composite_score(accuracy: dict, reasoning: dict, consistency: dict) -> float:
    """Weighted composite: accuracy 35%, reasoning 40%, consistency 25%."""
    a = accuracy.get("accuracy_score", 0)
    r = reasoning.get("reasoning_score", 0)
    c = consistency.get("consistency_score", 0)
    return round(0.35 * a + 0.40 * r + 0.25 * c, 3)
