"""
eval_runner.py — Phase 6 evaluation: runs all 10 test deals × 3 RAG modes × 3 LLMs.

Usage:
    python eval_runner.py                    # full run
    python eval_runner.py --mode agentic_rag # single mode
    python eval_runner.py --deal D01         # single deal
    python eval_runner.py --dry-run          # validate setup only

Results saved to: evaluation/results/raw/ (JSON) and evaluation/results/charts/ (PNG)
"""

import os
import sys
import json
import time
import argparse
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.test_deals import TEST_DEALS
from evaluation.metrics import score_accuracy, score_reasoning_quality, score_consistency, compute_composite_score
from graph.pipeline import run_pipeline

# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------
RAG_MODES = ["no_rag", "basic_rag", "agentic_rag"]
LLM_MODELS = ["gpt-4o-mini"]  # Add "claude-haiku-20240307" and "llama-3.1-8b-instant" when keys available
CONSISTENCY_RUNS = 3           # Run each deal N times for consistency measurement

RESULTS_DIR = Path(os.path.dirname(__file__)) / "results"
RAW_DIR = RESULTS_DIR / "raw"
CHARTS_DIR = RESULTS_DIR / "charts"
RAW_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------
# Single run
# -----------------------------------------------------------------------
def run_single(deal: dict, rag_mode: str, llm_model: str, run_index: int = 1) -> dict:
    """
    Run one deal through the pipeline with given mode and model.
    Returns a result dict with all metrics.
    """
    initial_state = {
        "business_id": deal["business_id"],
        "business_name": deal["business_name"],
        "deal_facts": deal["deal_facts"],
        "rag_mode": rag_mode,
        "llm_model": llm_model,
        "eval_run_index": run_index,
        "history": [],
    }

    start_time = time.time()
    try:
        state = run_pipeline(initial_state)
        latency_ms = round((time.time() - start_time) * 1000, 1)
        error = None
    except Exception as e:
        state = {}
        latency_ms = round((time.time() - start_time) * 1000, 1)
        error = traceback.format_exc()
        print(f"    ERROR: {e}")

    # Extract outputs
    draft = state.get("strategist_draft", {})
    analyst_summary = state.get("analyst_summary", "")
    queries = state.get("retrieval_queries", [])
    web_used = state.get("web_search_used", False)

    # Compute metrics
    acc = score_accuracy(queries, deal["deal_facts"], analyst_summary)
    rsn = score_reasoning_quality(draft)

    result = {
        "deal_id": deal["deal_id"],
        "deal_description": deal["description"],
        "rag_mode": rag_mode,
        "llm_model": llm_model,
        "run_index": run_index,
        "timestamp": datetime.now().isoformat(),
        "latency_ms": latency_ms,
        "error": error,

        # Outputs
        "counter_offer_pct": draft.get("counter_offer_pct", 0),
        "counter_offer_amount": draft.get("counter_offer_amount", 0),
        "confidence": draft.get("confidence", ""),
        "reflection_passed": state.get("reflection_passed", None),
        "requery_iteration": state.get("requery_iteration", 0),
        "retrieval_query_count": len(queries),
        "web_search_used": web_used,

        # Metrics
        "accuracy_score": acc["accuracy_score"],
        "accuracy_evidence_strength": acc["evidence_strength"],
        "reasoning_score": rsn["reasoning_score"],
        "reasoning_ungrounded_count": rsn["ungrounded_count"],

        # Raw for analysis
        "retrieval_queries": queries,
        "analyst_summary_raw": analyst_summary[:300] if analyst_summary else "",
        "leverage_points": draft.get("leverage_points", []),
        "alt_asks": draft.get("alt_asks", []),
    }

    return result


# -----------------------------------------------------------------------
# Consistency run (3× same deal)
# -----------------------------------------------------------------------
def run_consistency(deal: dict, rag_mode: str, llm_model: str) -> dict:
    """Run deal 3× and compute consistency metrics."""
    runs = []
    for i in range(1, CONSISTENCY_RUNS + 1):
        print(f"      Consistency run {i}/{CONSISTENCY_RUNS}...")
        r = run_single(deal, rag_mode, llm_model, run_index=i)
        runs.append(r)
        time.sleep(1)  # Rate limit buffer

    consistency = score_consistency(runs)
    composite = compute_composite_score(
        {"accuracy_score": runs[0].get("accuracy_score", 0)},
        {"reasoning_score": runs[0].get("reasoning_score", 0)},
        consistency,
    )

    return {
        "deal_id": deal["deal_id"],
        "rag_mode": rag_mode,
        "llm_model": llm_model,
        "runs": runs,
        "consistency": consistency,
        "composite_score": composite,
        "mean_accuracy": sum(r["accuracy_score"] for r in runs) / len(runs),
        "mean_reasoning": sum(r["reasoning_score"] for r in runs) / len(runs),
        "mean_latency_ms": sum(r["latency_ms"] for r in runs) / len(runs),
    }


# -----------------------------------------------------------------------
# Full evaluation loop
# -----------------------------------------------------------------------
def run_full_evaluation(mode_filter=None, deal_filter=None, dry_run=False):
    """Run all deals × modes × models. Save results."""
    deals = [d for d in TEST_DEALS if deal_filter is None or d["deal_id"] == deal_filter]
    modes = [m for m in RAG_MODES if mode_filter is None or m == mode_filter]

    all_results = []
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print(f"NegotiatorAI Evaluation Run: {run_id}")
    print(f"  Deals: {len(deals)} | Modes: {len(modes)} | Models: {len(LLM_MODELS)}")
    print(f"  Consistency runs per combo: {CONSISTENCY_RUNS}")
    print(f"  Dry run: {dry_run}")
    print(f"{'='*60}\n")

    for llm_model in LLM_MODELS:
        for rag_mode in modes:
            for deal in deals:
                print(f"\n[{rag_mode.upper()} | {llm_model} | {deal['deal_id']}] {deal['description']}")

                if dry_run:
                    print("  (dry-run — skipping actual pipeline call)")
                    continue

                combo_result = run_consistency(deal, rag_mode, llm_model)
                all_results.append(combo_result)

                # Save raw result
                fname = RAW_DIR / f"{run_id}_{rag_mode}_{llm_model.replace('-','_')}_{deal['deal_id']}.json"
                with open(fname, "w") as f:
                    json.dump(combo_result, f, indent=2, default=str)
                print(f"  ✅ Saved to {fname.name}")
                print(f"     accuracy={combo_result['mean_accuracy']:.2f} | reasoning={combo_result['mean_reasoning']:.2f} | consistency={combo_result['consistency']['consistency_score']:.1f} | composite={combo_result['composite_score']:.3f}")

                time.sleep(2)  # Rate limit between combos

    # Save aggregate results
    if all_results and not dry_run:
        agg_file = RESULTS_DIR / f"aggregate_{run_id}.json"
        with open(agg_file, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\n✅ Aggregate results saved to {agg_file}")

        # Generate comparison tables and charts
        generate_comparison_charts(all_results, run_id)

    return all_results


# -----------------------------------------------------------------------
# Chart generation
# -----------------------------------------------------------------------
def generate_comparison_charts(results: list, run_id: str):
    """Generate comparison tables and charts from evaluation results."""
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np

        # Flatten results into rows
        rows = []
        for r in results:
            rows.append({
                "deal_id": r["deal_id"],
                "rag_mode": r["rag_mode"],
                "llm_model": r["llm_model"],
                "accuracy": r["mean_accuracy"],
                "reasoning": r["mean_reasoning"],
                "consistency": r["consistency"]["consistency_score"],
                "composite": r["composite_score"],
                "latency_ms": r["mean_latency_ms"],
                "std_dev_pct": r["consistency"]["std_dev_pct"],
            })

        df = pd.DataFrame(rows)

        # ── Chart 1: RAG mode comparison (bar chart) ──────────────────────
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        metrics = ["accuracy", "reasoning", "consistency"]
        metric_labels = ["Accuracy (1-5)", "Reasoning Quality (1-5)", "Consistency (1-5)"]
        colors = {"no_rag": "#ef4444", "basic_rag": "#f59e0b", "agentic_rag": "#22c55e"}

        for ax, metric, label in zip(axes, metrics, metric_labels):
            mode_means = df.groupby("rag_mode")[metric].mean()
            bars = ax.bar(mode_means.index, mode_means.values,
                          color=[colors.get(m, "#6b7280") for m in mode_means.index])
            ax.set_title(label, fontweight="bold")
            ax.set_ylim(0, 5.5)
            ax.set_ylabel("Score")
            for bar, val in zip(bars, mode_means.values):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                        f"{val:.2f}", ha="center", fontsize=10)

        plt.suptitle("RAG Condition Comparison", fontsize=14, fontweight="bold")
        plt.tight_layout()
        chart1_path = CHARTS_DIR / f"rag_comparison_{run_id}.png"
        plt.savefig(chart1_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  📊 Saved RAG comparison chart: {chart1_path.name}")

        # ── Chart 2: LLM comparison (if multiple models) ──────────────────
        if df["llm_model"].nunique() > 1:
            fig, axes = plt.subplots(1, 4, figsize=(18, 5))
            for ax, metric, label in zip(axes, metrics + ["latency_ms"], metric_labels + ["Avg Latency (ms)"]):
                model_means = df.groupby("llm_model")[metric].mean()
                ax.bar(model_means.index, model_means.values, color="#6366f1")
                ax.set_title(label, fontweight="bold")
                if metric != "latency_ms":
                    ax.set_ylim(0, 5.5)
                for bar, val in zip(ax.patches, model_means.values):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                            f"{val:.1f}", ha="center", fontsize=9)
                ax.set_xticklabels(model_means.index, rotation=15, ha="right")

            plt.suptitle("LLM Model Comparison", fontsize=14, fontweight="bold")
            plt.tight_layout()
            chart2_path = CHARTS_DIR / f"llm_comparison_{run_id}.png"
            plt.savefig(chart2_path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"  📊 Saved LLM comparison chart: {chart2_path.name}")

        # ── Chart 3: Per-deal composite scores heatmap ────────────────────
        if "deal_id" in df.columns:
            pivot = df.pivot_table(index="deal_id", columns="rag_mode", values="composite", aggfunc="mean")
            fig, ax = plt.subplots(figsize=(10, 8))
            im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=1, vmax=5, aspect="auto")
            ax.set_xticks(range(len(pivot.columns)))
            ax.set_yticks(range(len(pivot.index)))
            ax.set_xticklabels(pivot.columns, fontweight="bold")
            ax.set_yticklabels(pivot.index)
            for i in range(len(pivot.index)):
                for j in range(len(pivot.columns)):
                    val = pivot.values[i, j]
                    if not np.isnan(val):
                        ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=9)
            plt.colorbar(im, ax=ax, label="Composite Score (1-5)")
            ax.set_title("Per-Deal Composite Score by RAG Mode", fontsize=13, fontweight="bold")
            plt.tight_layout()
            chart3_path = CHARTS_DIR / f"heatmap_{run_id}.png"
            plt.savefig(chart3_path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"  📊 Saved heatmap: {chart3_path.name}")

        # ── Save summary CSV ──────────────────────────────────────────────
        csv_path = RESULTS_DIR / f"summary_{run_id}.csv"
        df.to_csv(csv_path, index=False)
        print(f"  📄 Saved summary CSV: {csv_path.name}")

    except Exception as e:
        print(f"  ⚠️  Chart generation error: {e}")
        traceback.print_exc()


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NegotiatorAI Evaluation Runner")
    parser.add_argument("--mode", choices=RAG_MODES, help="Run only this RAG mode")
    parser.add_argument("--deal", help="Run only this deal ID (e.g. D01)")
    parser.add_argument("--model", help="Run only this LLM model")
    parser.add_argument("--dry-run", action="store_true", help="Validate setup without API calls")
    args = parser.parse_args()

    if args.model:
        LLM_MODELS.clear()
        LLM_MODELS.append(args.model)

    run_full_evaluation(
        mode_filter=args.mode,
        deal_filter=args.deal,
        dry_run=args.dry_run,
    )
