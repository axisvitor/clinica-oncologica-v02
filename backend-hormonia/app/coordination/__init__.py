"""
Swarm Coordination System for Hive-Mind Architecture

This package provides the coordination layer for multi-agent systems including:
- SwarmManager: Central coordination and orchestration
- Consensus protocols: Decision-making algorithms
- Topology management: Agent discovery and communication
- Task distribution: Load balancing and assignment
- Health monitoring: System and agent health tracking
"""

from .swarm_manager import SwarmManager, get_swarm_manager
from .consensus import ConsensusManager, ConsensusType
from .health_monitor import SystemHealthMonitor, get_system_health_monitor
# from .topology import TopologyManager, TopologyType  # Not yet implemented

__all__ = [
    "SwarmManager",
    "get_swarm_manager",
    "ConsensusManager",
    "ConsensusType",
    "SystemHealthMonitor",
    "get_system_health_monitor",
    # "TopologyManager",
    # "TopologyType"
]