"""
Distributed Memory System for Hive-Mind Architecture

This package provides shared memory and knowledge management for the agent swarm:
- KnowledgeGraph: Graph-based knowledge storage
- PatientMemory: Patient-specific context and history
- QuizContextMemory: Quiz personalization and adaptation
- CollectiveLearning: Cross-agent learning and improvement
"""

from .knowledge_graph import KnowledgeGraph, get_knowledge_graph

__all__ = [
    "KnowledgeGraph",
    "get_knowledge_graph"
]