"""LangGraph consensus flow for Hive-Mind decisions."""

from __future__ import annotations

import asyncio
import inspect
import logging
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, TypedDict

try:
    from langgraph.graph import END, StateGraph
    _LANGGRAPH_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001
    END = None  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]
    _LANGGRAPH_IMPORT_ERROR = exc

from app.agents.base import MessagePriority

logger = logging.getLogger(__name__)


class ConsensusState(TypedDict, total=False):
    send_message_fn: Callable[..., Any]
    fetch_votes_fn: Optional[Callable[..., Any]]
    decision_topic: str
    decision_data: Dict[str, Any]
    agents: List[str]
    min_participants: int
    consensus_threshold: float
    correlation_ids: Dict[str, Optional[str]]
    votes: Dict[str, Dict[str, Any]]
    poll_attempts: int
    max_poll_attempts: int
    poll_delay_seconds: float
    result: Dict[str, Any]


def _load_default_agents() -> List[str]:
    try:
        from app.agents.registry import ALERT_ANALYZER_ID, PATIENT_MONITOR_ID
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Default agent registry unavailable; pass 'agents' explicitly."
        ) from exc
    return [ALERT_ANALYZER_ID, PATIENT_MONITOR_ID]


async def prepare_consensus(state: ConsensusState) -> ConsensusState:
    """Prepare consensus inputs and defaults."""
    agents = state.get("agents") or _load_default_agents()
    min_participants = state.get("min_participants") or len(agents)
    if min_participants > len(agents):
        min_participants = len(agents)
    consensus_threshold = state.get("consensus_threshold")
    if consensus_threshold is None:
        consensus_threshold = 0.7
    max_poll_attempts = state.get("max_poll_attempts")
    if max_poll_attempts is None:
        max_poll_attempts = 1
    poll_delay_seconds = state.get("poll_delay_seconds") or 0.0
    if poll_delay_seconds < 0:
        poll_delay_seconds = 0.0
    poll_attempts = state.get("poll_attempts") or 0
    if poll_attempts < 0:
        poll_attempts = 0

    return {
        **state,
        "agents": agents,
        "min_participants": min_participants,
        "consensus_threshold": consensus_threshold,
        "max_poll_attempts": max_poll_attempts,
        "poll_delay_seconds": poll_delay_seconds,
        "poll_attempts": poll_attempts,
    }


async def dispatch_consensus_requests(state: ConsensusState) -> ConsensusState:
    """Send consensus requests to agents and collect correlation ids."""
    send_message_fn = state.get("send_message_fn")
    if send_message_fn is None:
        return {
            **state,
            "result": {
                "consensus_reached": False,
                "error": "send_message_fn not provided",
            },
        }

    agents = state.get("agents") or []
    decision_topic = state.get("decision_topic") or "unknown"
    decision_data = state.get("decision_data") or {}

    correlation_ids: Dict[str, Optional[str]] = dict(state.get("correlation_ids") or {})
    for agent_id in agents:
        if agent_id in correlation_ids:
            continue
        try:
            correlation_ids[agent_id] = await send_message_fn(
                agent_id,
                "consensus_request",
                {
                    "decision_topic": decision_topic,
                    "decision_data": decision_data,
                },
                MessagePriority.HIGH,
                requires_response=True,
            )
        except Exception as exc:
            logger.error("Failed to request consensus from %s: %s", agent_id, exc)
            correlation_ids[agent_id] = None

    return {**state, "correlation_ids": correlation_ids}


async def collect_votes(state: ConsensusState) -> ConsensusState:
    """Collect votes from agents if a fetch function is provided."""
    if state.get("result"):
        return state

    fetch_votes_fn = state.get("fetch_votes_fn")
    if fetch_votes_fn is None:
        return state

    attempts = (state.get("poll_attempts") or 0) + 1
    delay = state.get("poll_delay_seconds") or 0.0
    if delay > 0:
        await asyncio.sleep(delay)

    correlation_ids = state.get("correlation_ids") or {}
    existing_votes = dict(state.get("votes") or {})
    try:
        votes_result = fetch_votes_fn(correlation_ids)
        if inspect.isawaitable(votes_result):
            votes_result = await votes_result
    except Exception as exc:
        logger.error("Failed to fetch consensus votes: %s", exc)
        return {**state, "poll_attempts": attempts}

    if isinstance(votes_result, dict) and votes_result:
        allowed_agents = set(state.get("agents") or []) or set(correlation_ids.keys())
        if allowed_agents:
            votes_result = {key: value for key, value in votes_result.items() if key in allowed_agents}
        merged_votes = {**existing_votes, **votes_result}
        return {**state, "votes": merged_votes, "poll_attempts": attempts}
    return {**state, "poll_attempts": attempts}


async def evaluate_consensus(state: ConsensusState) -> ConsensusState:
    """Evaluate consensus outcome based on votes or default behavior."""
    if state.get("result"):
        return state

    agents = state.get("agents") or []
    votes = state.get("votes")
    correlation_ids = state.get("correlation_ids") or {}

    if not votes:
        if correlation_ids and all(value is None for value in correlation_ids.values()):
            return {
                **state,
                "result": {
                    "consensus_reached": False,
                    "error": "No agent responses",
                    "votes": {},
                },
            }
        return {
            **state,
            "result": {
                "consensus_reached": False,
                "error": "Consensus pending: no votes collected",
                "votes": {},
            },
        }

    approvals = sum(1 for vote in votes.values() if vote.get("vote") == "approve")
    total_votes = len(votes)
    min_participants = state.get("min_participants", total_votes)
    threshold = state.get("consensus_threshold", 0.7)

    consensus_reached = (
        total_votes >= min_participants
        and total_votes > 0
        and approvals / total_votes >= threshold
    )

    return {
        **state,
        "result": {
            "consensus_reached": consensus_reached,
            "votes": votes,
            "approval_rate": approvals / total_votes if total_votes > 0 else 0.0,
        },
    }

def _route_after_collect(state: ConsensusState) -> str:
    if state.get("result"):
        return "end"
    if not state.get("fetch_votes_fn"):
        return "evaluate_consensus"
    votes = state.get("votes") or {}
    min_participants = state.get("min_participants") or 0
    if votes and (min_participants <= 0 or len(votes) >= min_participants):
        return "evaluate_consensus"
    max_attempts = state.get("max_poll_attempts", 1)
    attempts = state.get("poll_attempts", 0)
    return "collect_votes" if attempts < max_attempts else "evaluate_consensus"


def build_consensus_graph() -> Any:
    """Build consensus graph."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed") from _LANGGRAPH_IMPORT_ERROR
    graph = StateGraph(ConsensusState)
    graph.add_node("prepare_consensus", prepare_consensus)
    graph.add_node("dispatch_consensus_requests", dispatch_consensus_requests)
    graph.add_node("collect_votes", collect_votes)
    graph.add_node("evaluate_consensus", evaluate_consensus)
    graph.set_entry_point("prepare_consensus")
    graph.add_edge("prepare_consensus", "dispatch_consensus_requests")
    graph.add_edge("dispatch_consensus_requests", "collect_votes")
    graph.add_conditional_edges(
        "collect_votes",
        _route_after_collect,
        {
            "collect_votes": "collect_votes",
            "evaluate_consensus": "evaluate_consensus",
            "end": END,
        },
    )
    graph.add_edge("evaluate_consensus", END)
    return graph.compile()


@lru_cache(maxsize=1)
def get_consensus_graph() -> Any:
    """Return cached consensus graph."""
    return build_consensus_graph()
