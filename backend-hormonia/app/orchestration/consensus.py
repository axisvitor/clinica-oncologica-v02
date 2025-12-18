"""
Consensus protocols for Hive-Mind decision making.

Implements various consensus algorithms for distributed decision making
among agents in the swarm.
"""

import asyncio
from typing import Dict, List, Set, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, Counter

from app.utils.logging import get_logger


class ConsensusType(Enum):
    """Types of consensus protocols."""

    SIMPLE_MAJORITY = "simple_majority"
    WEIGHTED_VOTING = "weighted_voting"
    BYZANTINE_FAULT_TOLERANT = "byzantine_fault_tolerant"
    RAFT_LEADER_BASED = "raft_leader_based"
    QUORUM_BASED = "quorum_based"


class VoteType(Enum):
    """Types of votes."""

    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass
class Vote:
    """Individual vote in consensus process."""

    voter_id: str
    vote_type: VoteType
    confidence: float
    reasoning: Optional[str] = None
    timestamp: datetime = None
    additional_data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ConsensusProposal:
    """Proposal for consensus voting."""

    proposal_id: str
    proposer_id: str
    proposal_type: str
    proposal_data: Dict[str, Any]
    required_consensus: ConsensusType
    min_participants: int
    timeout_seconds: int
    created_at: datetime
    critical_decision: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            **asdict(self),
            "required_consensus": self.required_consensus.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ConsensusResult:
    """Result of consensus process."""

    proposal_id: str
    consensus_reached: bool
    decision: VoteType
    votes: List[Vote]
    confidence_score: float
    participants: int
    consensus_method: ConsensusType
    completed_at: datetime
    reasoning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            **asdict(self),
            "decision": self.decision.value,
            "consensus_method": self.consensus_method.value,
            "completed_at": self.completed_at.isoformat(),
            "votes": [asdict(vote) for vote in self.votes],
        }


class ConsensusManager:
    """
    Manages consensus processes for distributed decision making.

    Handles different consensus protocols and coordinates voting
    among multiple agents in the swarm.
    """

    def __init__(self):
        """Initialize consensus manager."""
        self.logger = get_logger("consensus_manager")

        # Active consensus processes
        self.active_proposals: Dict[str, ConsensusProposal] = {}
        self.proposal_votes: Dict[str, List[Vote]] = defaultdict(list)
        self.proposal_participants: Dict[str, Set[str]] = defaultdict(set)

        # Consensus history
        self.completed_consensus: Dict[str, ConsensusResult] = {}

        # Agent weights for weighted voting
        self.agent_weights: Dict[str, float] = {}

        # Configuration
        self.default_timeout = 300  # 5 minutes
        self.min_confidence_threshold = 0.6
        self.byzantine_fault_tolerance = 0.33  # Up to 33% faulty nodes

    def set_agent_weight(self, agent_id: str, weight: float):
        """Set voting weight for an agent."""
        if 0.0 <= weight <= 1.0:
            self.agent_weights[agent_id] = weight
            self.logger.debug(f"Set weight {weight} for agent {agent_id}")
        else:
            raise ValueError("Agent weight must be between 0.0 and 1.0")

    async def propose_decision(
        self,
        proposer_id: str,
        proposal_type: str,
        proposal_data: Dict[str, Any],
        consensus_type: ConsensusType = ConsensusType.SIMPLE_MAJORITY,
        min_participants: int = 3,
        timeout_seconds: int = None,
        critical_decision: bool = False,
    ) -> str:
        """
        Propose a decision for consensus voting.

        Args:
            proposer_id: ID of the proposing agent
            proposal_type: Type of decision being proposed
            proposal_data: Data relevant to the decision
            consensus_type: Type of consensus protocol to use
            min_participants: Minimum number of participants needed
            timeout_seconds: Timeout for voting (uses default if None)
            critical_decision: Whether this is a critical decision

        Returns:
            Proposal ID for tracking
        """
        proposal_id = str(uuid4())

        if timeout_seconds is None:
            timeout_seconds = self.default_timeout
            if critical_decision:
                timeout_seconds *= 2  # Double timeout for critical decisions

        proposal = ConsensusProposal(
            proposal_id=proposal_id,
            proposer_id=proposer_id,
            proposal_type=proposal_type,
            proposal_data=proposal_data,
            required_consensus=consensus_type,
            min_participants=min_participants,
            timeout_seconds=timeout_seconds,
            created_at=datetime.utcnow(),
            critical_decision=critical_decision,
        )

        self.active_proposals[proposal_id] = proposal

        # Schedule timeout handling
        asyncio.create_task(self._handle_proposal_timeout(proposal_id, timeout_seconds))

        self.logger.info(
            f"Created consensus proposal {proposal_id} of type {proposal_type}"
        )

        return proposal_id

    async def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        vote_type: VoteType,
        confidence: float,
        reasoning: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Cast vote for a proposal.

        Args:
            proposal_id: ID of proposal to vote on
            voter_id: ID of voting agent
            vote_type: Type of vote (approve/reject/abstain)
            confidence: Confidence level (0.0 to 1.0)
            reasoning: Optional reasoning for the vote
            additional_data: Additional data supporting the vote

        Returns:
            True if vote was accepted, False otherwise
        """
        if proposal_id not in self.active_proposals:
            self.logger.warning(
                f"Vote rejected: proposal {proposal_id} not found or expired"
            )
            return False

        # Check if agent already voted
        existing_votes = [
            v for v in self.proposal_votes[proposal_id] if v.voter_id == voter_id
        ]
        if existing_votes:
            self.logger.warning(
                f"Vote rejected: agent {voter_id} already voted on {proposal_id}"
            )
            return False

        # Create and record vote
        vote = Vote(
            voter_id=voter_id,
            vote_type=vote_type,
            confidence=confidence,
            reasoning=reasoning,
            additional_data=additional_data,
        )

        self.proposal_votes[proposal_id].append(vote)
        self.proposal_participants[proposal_id].add(voter_id)

        self.logger.info(
            f"Recorded vote from {voter_id} for proposal {proposal_id}: {vote_type.value}"
        )

        # Check if consensus is reached
        await self._check_consensus_completion(proposal_id)

        return True

    async def _check_consensus_completion(self, proposal_id: str):
        """Check if consensus has been reached for a proposal."""
        proposal = self.active_proposals.get(proposal_id)
        if not proposal:
            return

        votes = self.proposal_votes[proposal_id]
        participants = len(self.proposal_participants[proposal_id])

        # Check minimum participants
        if participants < proposal.min_participants:
            return

        # Apply consensus algorithm
        consensus_result = None

        if proposal.required_consensus == ConsensusType.SIMPLE_MAJORITY:
            consensus_result = await self._apply_simple_majority(proposal, votes)
        elif proposal.required_consensus == ConsensusType.WEIGHTED_VOTING:
            consensus_result = await self._apply_weighted_voting(proposal, votes)
        elif proposal.required_consensus == ConsensusType.BYZANTINE_FAULT_TOLERANT:
            consensus_result = await self._apply_byzantine_consensus(proposal, votes)
        elif proposal.required_consensus == ConsensusType.QUORUM_BASED:
            consensus_result = await self._apply_quorum_consensus(proposal, votes)
        else:
            self.logger.error(
                f"Unsupported consensus type: {proposal.required_consensus}"
            )
            return

        # If consensus reached, complete the proposal
        if consensus_result and consensus_result.consensus_reached:
            await self._complete_consensus(proposal_id, consensus_result)

    async def _apply_simple_majority(
        self, proposal: ConsensusProposal, votes: List[Vote]
    ) -> ConsensusResult:
        """Apply simple majority consensus."""
        vote_counts = Counter(vote.vote_type for vote in votes)
        total_votes = len(votes)

        # Determine majority decision
        majority_threshold = total_votes // 2 + 1
        consensus_reached = False
        decision = VoteType.ABSTAIN

        if vote_counts[VoteType.APPROVE] >= majority_threshold:
            consensus_reached = True
            decision = VoteType.APPROVE
        elif vote_counts[VoteType.REJECT] >= majority_threshold:
            consensus_reached = True
            decision = VoteType.REJECT

        # Calculate confidence score
        if consensus_reached:
            winning_votes = [v for v in votes if v.vote_type == decision]
            confidence_score = sum(v.confidence for v in winning_votes) / len(
                winning_votes
            )
        else:
            confidence_score = 0.0

        return ConsensusResult(
            proposal_id=proposal.proposal_id,
            consensus_reached=consensus_reached,
            decision=decision,
            votes=votes,
            confidence_score=confidence_score,
            participants=len(votes),
            consensus_method=ConsensusType.SIMPLE_MAJORITY,
            completed_at=datetime.utcnow(),
            reasoning=f"Simple majority: {vote_counts[decision]}/{total_votes}"
            if consensus_reached
            else "No majority reached",
        )

    async def _apply_weighted_voting(
        self, proposal: ConsensusProposal, votes: List[Vote]
    ) -> ConsensusResult:
        """Apply weighted voting consensus."""
        weighted_scores = {
            VoteType.APPROVE: 0.0,
            VoteType.REJECT: 0.0,
            VoteType.ABSTAIN: 0.0,
        }
        total_weight = 0.0

        for vote in votes:
            weight = self.agent_weights.get(vote.voter_id, 1.0)
            weighted_score = weight * vote.confidence
            weighted_scores[vote.vote_type] += weighted_score
            total_weight += weight

        # Normalize scores
        if total_weight > 0:
            for vote_type in weighted_scores:
                weighted_scores[vote_type] /= total_weight

        # Determine winner
        decision = max(weighted_scores, key=weighted_scores.get)
        winning_score = weighted_scores[decision]

        # Consensus reached if winning score > 0.5 and above confidence threshold
        consensus_reached = (
            winning_score > 0.5 and winning_score >= self.min_confidence_threshold
        )

        return ConsensusResult(
            proposal_id=proposal.proposal_id,
            consensus_reached=consensus_reached,
            decision=decision,
            votes=votes,
            confidence_score=winning_score,
            participants=len(votes),
            consensus_method=ConsensusType.WEIGHTED_VOTING,
            completed_at=datetime.utcnow(),
            reasoning=f"Weighted voting: {decision.value} with score {winning_score:.2f}",
        )

    async def _apply_byzantine_consensus(
        self, proposal: ConsensusProposal, votes: List[Vote]
    ) -> ConsensusResult:
        """Apply Byzantine fault tolerant consensus."""
        n = len(votes)
        f = int(n * self.byzantine_fault_tolerance)  # Maximum faulty nodes
        required_agreement = n - f  # Minimum nodes that must agree

        vote_counts = Counter(vote.vote_type for vote in votes)

        # Check if any decision has sufficient agreement
        consensus_reached = False
        decision = VoteType.ABSTAIN

        for vote_type, count in vote_counts.items():
            if count >= required_agreement:
                consensus_reached = True
                decision = vote_type
                break

        # Calculate confidence (average of agreeing votes)
        if consensus_reached:
            agreeing_votes = [v for v in votes if v.vote_type == decision]
            confidence_score = sum(v.confidence for v in agreeing_votes) / len(
                agreeing_votes
            )
        else:
            confidence_score = 0.0

        return ConsensusResult(
            proposal_id=proposal.proposal_id,
            consensus_reached=consensus_reached,
            decision=decision,
            votes=votes,
            confidence_score=confidence_score,
            participants=n,
            consensus_method=ConsensusType.BYZANTINE_FAULT_TOLERANT,
            completed_at=datetime.utcnow(),
            reasoning=f"Byzantine consensus: {vote_counts[decision]}/{n} agree (required: {required_agreement})"
            if consensus_reached
            else "Insufficient agreement for Byzantine consensus",
        )

    async def _apply_quorum_consensus(
        self, proposal: ConsensusProposal, votes: List[Vote]
    ) -> ConsensusResult:
        """Apply quorum-based consensus."""
        n = len(votes)
        quorum_size = (n // 2) + 1  # Simple majority for quorum

        # Check if we have quorum
        if n < quorum_size:
            return ConsensusResult(
                proposal_id=proposal.proposal_id,
                consensus_reached=False,
                decision=VoteType.ABSTAIN,
                votes=votes,
                confidence_score=0.0,
                participants=n,
                consensus_method=ConsensusType.QUORUM_BASED,
                completed_at=datetime.utcnow(),
                reasoning=f"Quorum not reached: {n}/{quorum_size}",
            )

        # Apply simple majority within quorum
        return await self._apply_simple_majority(proposal, votes)

    async def _complete_consensus(self, proposal_id: str, result: ConsensusResult):
        """Complete consensus process."""
        # Move from active to completed
        proposal = self.active_proposals.pop(proposal_id, None)
        if proposal:
            self.completed_consensus[proposal_id] = result

            # Clean up votes
            del self.proposal_votes[proposal_id]
            del self.proposal_participants[proposal_id]

            self.logger.info(
                f"Consensus completed for {proposal_id}: {result.decision.value} (confidence: {result.confidence_score:.2f})"
            )

    async def _handle_proposal_timeout(self, proposal_id: str, timeout_seconds: int):
        """Handle proposal timeout."""
        await asyncio.sleep(timeout_seconds)

        if proposal_id in self.active_proposals:
            proposal = self.active_proposals[proposal_id]
            votes = self.proposal_votes.get(proposal_id, [])

            # Create timeout result
            result = ConsensusResult(
                proposal_id=proposal_id,
                consensus_reached=False,
                decision=VoteType.ABSTAIN,
                votes=votes,
                confidence_score=0.0,
                participants=len(votes),
                consensus_method=proposal.required_consensus,
                completed_at=datetime.utcnow(),
                reasoning=f"Consensus timed out after {timeout_seconds} seconds",
            )

            await self._complete_consensus(proposal_id, result)
            self.logger.warning(
                f"Proposal {proposal_id} timed out with {len(votes)} votes"
            )

    def get_proposal_status(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a proposal."""
        # Check active proposals
        if proposal_id in self.active_proposals:
            proposal = self.active_proposals[proposal_id]
            votes = self.proposal_votes.get(proposal_id, [])
            participants = len(self.proposal_participants.get(proposal_id, set()))

            return {
                "proposal": proposal.to_dict(),
                "status": "active",
                "votes_received": len(votes),
                "participants": participants,
                "votes": [asdict(vote) for vote in votes],
            }

        # Check completed proposals
        if proposal_id in self.completed_consensus:
            result = self.completed_consensus[proposal_id]
            return {"status": "completed", "result": result.to_dict()}

        return None

    def get_consensus_result(self, proposal_id: str) -> Optional[ConsensusResult]:
        """Get consensus result for completed proposal."""
        return self.completed_consensus.get(proposal_id)

    def get_active_proposals(self) -> List[Dict[str, Any]]:
        """Get all active proposals."""
        return [
            {
                "proposal": proposal.to_dict(),
                "votes_received": len(self.proposal_votes.get(proposal_id, [])),
                "participants": len(self.proposal_participants.get(proposal_id, set())),
            }
            for proposal_id, proposal in self.active_proposals.items()
        ]

    def cleanup_old_consensus(self, days_old: int = 7):
        """Clean up old completed consensus records."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        to_remove = [
            proposal_id
            for proposal_id, result in self.completed_consensus.items()
            if result.completed_at < cutoff_date
        ]

        for proposal_id in to_remove:
            del self.completed_consensus[proposal_id]

        self.logger.info(f"Cleaned up {len(to_remove)} old consensus records")

    def get_consensus_stats(self) -> Dict[str, Any]:
        """Get consensus statistics."""
        active_count = len(self.active_proposals)
        completed_count = len(self.completed_consensus)

        if completed_count > 0:
            successful_consensus = sum(
                1
                for result in self.completed_consensus.values()
                if result.consensus_reached
            )
            success_rate = successful_consensus / completed_count

            avg_participants = (
                sum(result.participants for result in self.completed_consensus.values())
                / completed_count
            )
            avg_confidence = (
                sum(
                    result.confidence_score
                    for result in self.completed_consensus.values()
                )
                / completed_count
            )
        else:
            success_rate = 0.0
            avg_participants = 0.0
            avg_confidence = 0.0

        return {
            "active_proposals": active_count,
            "completed_proposals": completed_count,
            "consensus_success_rate": success_rate,
            "average_participants": avg_participants,
            "average_confidence": avg_confidence,
            "registered_agents": len(self.agent_weights),
        }


# Global consensus manager instance
_consensus_manager: Optional[ConsensusManager] = None


def get_consensus_manager() -> ConsensusManager:
    """Get global consensus manager instance."""
    global _consensus_manager

    if _consensus_manager is None:
        _consensus_manager = ConsensusManager()

    return _consensus_manager
