"""Canonical orchestration consensus entrypoint.

Consensus runtime is LangGraph-based and implemented in
``app.ai.langgraph.consensus``. This module keeps a stable import path for
orchestration code without carrying the removed legacy consensus manager.
"""

from app.ai.langgraph.consensus import (
    ConsensusState,
    build_consensus_graph,
    collect_votes,
    dispatch_consensus_requests,
    evaluate_consensus,
    get_consensus_graph,
    prepare_consensus,
)

__all__ = [
    "ConsensusState",
    "prepare_consensus",
    "dispatch_consensus_requests",
    "collect_votes",
    "evaluate_consensus",
    "build_consensus_graph",
    "get_consensus_graph",
]
