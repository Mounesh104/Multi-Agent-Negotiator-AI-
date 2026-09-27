"""
pipeline.py -- LangGraph StateGraph wiring for NegotiatorAI.

Main pipeline (runs on deal submission):
  load_history -> analyst_retrieve -> strategist_draft -> reflection_check
    -> [conditional] re_retrieve (loops back to analyst) OR END (HITL checkpoint)

Scoring pipeline (runs after rehearsal, called separately by Streamlit):
  strategist_score -> save_memory -> END

Conditional edges:
  reflection_check -> re_retrieve   if reflection_passed == False AND requery_iteration < MAX
  reflection_check -> END (hitl_ready) if reflection_passed == True (or max iterations reached)

Fix #5: strategist_score and save_memory were previously added as orphan
nodes inside build_pipeline() where they had no incoming edges from the main
flow. They have been removed from the main pipeline entirely -- they belong
only in build_scoring_pipeline() which Streamlit calls after rehearsal.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from graph.state import NegotiationState
from graph.nodes import (
    node_load_history,
    node_analyst_retrieve,
    node_strategist_draft,
    node_reflection_check,
    node_re_retrieve,
    node_strategist_score,
    node_save_memory,
)
from config import MAX_REQUERY_ITERATIONS


def _should_re_retrieve(state: NegotiationState) -> str:
    """
    Conditional edge function after reflection_check.
    Returns "re_retrieve" or "hitl_ready".
    """
    if (
        not state.get("reflection_passed", True)
        and state.get("requery_iteration", 0) < MAX_REQUERY_ITERATIONS
    ):
        return "re_retrieve"
    return "hitl_ready"


def build_pipeline(rag_mode: str = "agentic_rag") -> StateGraph:
    """
    Build and compile the main LangGraph pipeline (runs to HITL checkpoint).
    The rag_mode is stored in state and respected by each node.
    Returns a compiled graph ready for .invoke() or .stream().

    Fix #5: Only the 5 nodes that are actually reachable in this pipeline are
    registered. strategist_score and save_memory are NOT added here -- they
    belong exclusively in build_scoring_pipeline().
    """
    graph = StateGraph(NegotiationState)

    # ------------------------------------------------------------------
    # Add nodes (only those reachable in the main pipeline)
    # ------------------------------------------------------------------
    graph.add_node("load_history", node_load_history)
    graph.add_node("analyst_retrieve", node_analyst_retrieve)
    graph.add_node("strategist_draft", node_strategist_draft)
    graph.add_node("reflection_check", node_reflection_check)
    graph.add_node("re_retrieve", node_re_retrieve)

    # ------------------------------------------------------------------
    # Set entry point
    # ------------------------------------------------------------------
    graph.set_entry_point("load_history")

    # ------------------------------------------------------------------
    # Add edges
    # ------------------------------------------------------------------
    graph.add_edge("load_history", "analyst_retrieve")
    graph.add_edge("analyst_retrieve", "strategist_draft")
    graph.add_edge("strategist_draft", "reflection_check")

    # Conditional: re-retrieve OR move to HITL (END)
    graph.add_conditional_edges(
        "reflection_check",
        _should_re_retrieve,
        {
            "re_retrieve": "re_retrieve",
            "hitl_ready": END,  # Pipeline pauses here; Streamlit handles HITL + rehearsal
        },
    )

    # Re-retrieve loops back through analyst -> strategist -> reflection
    graph.add_edge("re_retrieve", "analyst_retrieve")

    return graph.compile()


def build_scoring_pipeline() -> StateGraph:
    """
    Separate mini-pipeline for post-rehearsal scoring + saving.
    Called by Streamlit after the rehearsal loop completes.
    """
    graph = StateGraph(NegotiationState)
    graph.add_node("strategist_score", node_strategist_score)
    graph.add_node("save_memory", node_save_memory)
    graph.set_entry_point("strategist_score")
    graph.add_edge("strategist_score", "save_memory")
    graph.add_edge("save_memory", END)
    return graph.compile()


def run_pipeline(initial_state: dict) -> dict:
    """
    Convenience function: run the main pipeline to the HITL checkpoint.
    Returns the final state dict.
    """
    pipeline = build_pipeline(rag_mode=initial_state.get("rag_mode", "agentic_rag"))
    result = pipeline.invoke(initial_state)
    return dict(result)


def run_post_rehearsal(state: dict) -> dict:
    """
    Convenience function: run scoring + save after rehearsal completes.
    """
    pipeline = build_scoring_pipeline()
    result = pipeline.invoke(state)
    return dict(result)
