"""
Knowledge Graph for Hive-Mind System

Provides graph-based storage and retrieval of patient knowledge,
interaction patterns, and learned insights across all agents.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

import redis.asyncio as redis
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.config import settings
from app.utils.logging import get_logger
from app.models.patient import Patient
from app.models.quiz import QuizSession, QuizResponse
from app.models.message import Message
from app.utils.timezone import now_sao_paulo


class NodeType(Enum):
    """Types of nodes in the knowledge graph."""
    PATIENT = "patient"
    INTERACTION = "interaction"
    QUIZ_SESSION = "quiz_session"
    QUIZ_RESPONSE = "quiz_response"
    PATTERN = "pattern"
    INSIGHT = "insight"
    SYMPTOM = "symptom"
    MEDICATION = "medication"
    INTERVENTION = "intervention"
    OUTCOME = "outcome"


class EdgeType(Enum):
    """Types of relationships in the knowledge graph."""
    HAS_INTERACTION = "has_interaction"
    PARTICIPATED_IN = "participated_in"
    RESPONDED_TO = "responded_to"
    TRIGGERED_BY = "triggered_by"
    CORRELATES_WITH = "correlates_with"
    IMPROVED_AFTER = "improved_after"
    PRECEDED_BY = "preceded_by"
    CAUSES = "causes"
    SIMILAR_TO = "similar_to"
    LEARNED_FROM = "learned_from"


@dataclass
class GraphNode:
    """Node in the knowledge graph."""
    node_id: str
    node_type: NodeType
    entity_id: str  # Original entity ID (patient_id, session_id, etc.)
    properties: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            **asdict(self),
            'node_type': self.node_type.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


@dataclass
class GraphEdge:
    """Edge in the knowledge graph."""
    edge_id: str
    edge_type: EdgeType
    source_node: str
    target_node: str
    properties: Dict[str, Any]
    created_at: datetime
    strength: float = 1.0
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            **asdict(self),
            'edge_type': self.edge_type.value,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class PatternInsight:
    """Discovered pattern or insight."""
    pattern_id: str
    pattern_type: str
    description: str
    affected_entities: List[str]
    confidence: float
    supporting_evidence: List[str]
    discovered_at: datetime
    agent_source: str


class KnowledgeGraph:
    """
    Distributed knowledge graph for patient care insights.
    
    Stores and manages relationships between patients, interactions,
    quiz responses, symptoms, and discovered patterns.
    """
    
    def __init__(self, db_session: Session):
        """Initialize knowledge graph."""
        self.db_session = db_session
        self.logger = get_logger("knowledge_graph")
        
        # Redis for fast access and caching
        self.redis_client = None
        self.redis_prefix = "kg:"
        
        # In-memory graph structures for fast queries
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        self.node_edges: Dict[str, Set[str]] = defaultdict(set)  # node_id -> edge_ids
        self.patterns: Dict[str, PatternInsight] = {}
        
        # Indexing for fast lookups
        self.nodes_by_type: Dict[NodeType, Set[str]] = defaultdict(set)
        self.nodes_by_entity: Dict[str, str] = {}  # entity_id -> node_id
        self.edges_by_type: Dict[EdgeType, Set[str]] = defaultdict(set)
        
        # Configuration
        self.max_memory_nodes = settings.get('KG_MAX_MEMORY_NODES', 10000)
        self.pattern_confidence_threshold = 0.7
        self.auto_cleanup_days = 90
        
    async def initialize(self):
        """Initialize the knowledge graph."""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            
            # Load existing graph from storage
            await self._load_graph_from_storage()
            
            self.logger.info("Knowledge graph initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize knowledge graph: {e}")
            raise
    
    async def close(self):
        """Close the knowledge graph and connections."""
        if self.redis_client:
            await self.redis_client.aclose()
    
    # Node Management
    async def add_node(
        self,
        node_type: NodeType,
        entity_id: str,
        properties: Dict[str, Any],
        confidence: float = 1.0
    ) -> str:
        """Add node to the knowledge graph."""
        node_id = f"{node_type.value}_{entity_id}_{uuid4().hex[:8]}"
        
        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            entity_id=entity_id,
            properties=properties,
            created_at=now_sao_paulo(),
            updated_at=now_sao_paulo(),
            confidence=confidence
        )
        
        # Store in memory
        self.nodes[node_id] = node
        self.nodes_by_type[node_type].add(node_id)
        self.nodes_by_entity[entity_id] = node_id
        
        # Store in Redis
        await self._store_node_in_redis(node)
        
        self.logger.debug(f"Added node {node_id} ({node_type.value})")
        return node_id
    
    async def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get node by ID."""
        # Try memory first
        if node_id in self.nodes:
            return self.nodes[node_id]
        
        # Try Redis
        node_data = await self.redis_client.hget(f"{self.redis_prefix}nodes", node_id)
        if node_data:
            node_dict = json.loads(node_data)
            node = self._dict_to_node(node_dict)
            self.nodes[node_id] = node
            return node
        
        return None
    
    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any],
        confidence: Optional[float] = None
    ):
        """Update node properties."""
        node = await self.get_node(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        
        node.properties.update(properties)
        node.updated_at = now_sao_paulo()
        
        if confidence is not None:
            node.confidence = confidence
        
        # Update storage
        await self._store_node_in_redis(node)
        
        self.logger.debug(f"Updated node {node_id}")
    
    async def get_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        """Get all nodes of specific type."""
        node_ids = self.nodes_by_type[node_type]
        nodes = []
        
        for node_id in node_ids:
            node = await self.get_node(node_id)
            if node:
                nodes.append(node)
        
        return nodes
    
    async def get_node_by_entity(self, entity_id: str) -> Optional[GraphNode]:
        """Get node by entity ID."""
        node_id = self.nodes_by_entity.get(entity_id)
        if node_id:
            return await self.get_node(node_id)
        return None
    
    # Edge Management
    async def add_edge(
        self,
        edge_type: EdgeType,
        source_node_id: str,
        target_node_id: str,
        properties: Dict[str, Any],
        strength: float = 1.0,
        confidence: float = 1.0
    ) -> str:
        """Add edge to the knowledge graph."""
        # Verify nodes exist
        source = await self.get_node(source_node_id)
        target = await self.get_node(target_node_id)
        
        if not source or not target:
            raise ValueError("Source or target node not found")
        
        edge_id = f"{edge_type.value}_{uuid4().hex[:8]}"
        
        edge = GraphEdge(
            edge_id=edge_id,
            edge_type=edge_type,
            source_node=source_node_id,
            target_node=target_node_id,
            properties=properties,
            created_at=now_sao_paulo(),
            strength=strength,
            confidence=confidence
        )
        
        # Store in memory
        self.edges[edge_id] = edge
        self.edges_by_type[edge_type].add(edge_id)
        self.node_edges[source_node_id].add(edge_id)
        self.node_edges[target_node_id].add(edge_id)
        
        # Store in Redis
        await self._store_edge_in_redis(edge)
        
        self.logger.debug(f"Added edge {edge_id} ({edge_type.value})")
        return edge_id
    
    async def get_edges_for_node(self, node_id: str) -> List[GraphEdge]:
        """Get all edges connected to a node."""
        edge_ids = self.node_edges[node_id]
        edges = []
        
        for edge_id in edge_ids:
            edge = self.edges.get(edge_id)
            if edge:
                edges.append(edge)
        
        return edges
    
    async def get_connected_nodes(
        self,
        node_id: str,
        edge_types: Optional[List[EdgeType]] = None,
        direction: str = "both"  # "incoming", "outgoing", "both"
    ) -> List[Tuple[GraphNode, GraphEdge]]:
        """Get nodes connected to given node."""
        edges = await self.get_edges_for_node(node_id)
        connected = []
        
        for edge in edges:
            if edge_types and edge.edge_type not in edge_types:
                continue
            
            target_node_id = None
            
            if direction in ["outgoing", "both"] and edge.source_node == node_id:
                target_node_id = edge.target_node
            elif direction in ["incoming", "both"] and edge.target_node == node_id:
                target_node_id = edge.source_node
            
            if target_node_id:
                target_node = await self.get_node(target_node_id)
                if target_node:
                    connected.append((target_node, edge))
        
        return connected
    
    # Patient-Specific Methods
    async def add_patient_node(self, patient: Patient) -> str:
        """Add patient node to graph."""
        properties = {
            "name": patient.name,
            "email": patient.email,
            "phone": patient.phone,
            "enrollment_date": patient.enrollment_date.isoformat() if patient.enrollment_date else None,
            "treatment_type": patient.treatment_type,
            "is_active": patient.is_active,
            "created_at": patient.created_at.isoformat()
        }
        
        return await self.add_node(
            NodeType.PATIENT,
            str(patient.id),
            properties
        )
    
    async def add_quiz_session_node(self, session: QuizSession) -> str:
        """Add quiz session node to graph."""
        properties = {
            "quiz_template_id": str(session.quiz_template_id),
            "is_completed": session.is_completed,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "current_question_index": session.current_question_index,
            "session_metadata": session.session_metadata or {}
        }
        
        session_node_id = await self.add_node(
            NodeType.QUIZ_SESSION,
            str(session.id),
            properties
        )
        
        # Link to patient
        patient_node = await self.get_node_by_entity(str(session.patient_id))
        if patient_node:
            await self.add_edge(
                EdgeType.PARTICIPATED_IN,
                patient_node.node_id,
                session_node_id,
                {"session_type": "quiz"}
            )
        
        return session_node_id
    
    async def add_quiz_response_node(self, response: QuizResponse) -> str:
        """Add quiz response node to graph."""
        properties = {
            "question_id": response.question_id,
            "question_text": response.question_text,
            "response_type": response.response_type,
            "response_value": response.response_value,
            "response_metadata": response.response_metadata or {},
            "responded_at": response.responded_at.isoformat() if response.responded_at else None
        }
        
        response_node_id = await self.add_node(
            NodeType.QUIZ_RESPONSE,
            str(response.id),
            properties
        )
        
        # Link to session and patient
        session_node = await self.get_node_by_entity(str(response.quiz_template_id))
        if session_node:
            await self.add_edge(
                EdgeType.RESPONDED_TO,
                response_node_id,
                session_node.node_id,
                {"question_index": properties.get("question_index", 0)}
            )
        
        # Link to patient
        patient_node = await self.get_node_by_entity(str(response.patient_id))
        if patient_node:
            await self.add_edge(
                EdgeType.HAS_INTERACTION,
                patient_node.node_id,
                response_node_id,
                {"interaction_type": "quiz_response"}
            )
        
        return response_node_id
    
    # Pattern Recognition and Insights
    async def discover_patterns(self, patient_id: UUID) -> List[PatternInsight]:
        """Discover patterns for specific patient."""
        patterns = []
        
        # Get patient node
        patient_node = await self.get_node_by_entity(str(patient_id))
        if not patient_node:
            return patterns
        
        # Analyze quiz response patterns
        quiz_patterns = await self._analyze_quiz_patterns(patient_node)
        patterns.extend(quiz_patterns)
        
        # Analyze symptom patterns
        symptom_patterns = await self._analyze_symptom_patterns(patient_node)
        patterns.extend(symptom_patterns)
        
        # Store significant patterns
        for pattern in patterns:
            if pattern.confidence >= self.pattern_confidence_threshold:
                self.patterns[pattern.pattern_id] = pattern
                await self._store_pattern_in_redis(pattern)
        
        return patterns
    
    async def _analyze_quiz_patterns(self, patient_node: GraphNode) -> List[PatternInsight]:
        """Analyze quiz response patterns."""
        patterns = []
        
        # Get quiz responses for patient
        connected = await self.get_connected_nodes(
            patient_node.node_id,
            [EdgeType.HAS_INTERACTION],
            "outgoing"
        )
        
        quiz_responses = [
            node for node, edge in connected
            if node.node_type == NodeType.QUIZ_RESPONSE
        ]
        
        if len(quiz_responses) < 3:  # Need minimum responses for pattern
            return patterns
        
        # Analyze mood trends
        mood_scores = []
        for response in quiz_responses:
            if "mood" in response.properties.get("question_id", ""):
                try:
                    score = float(response.properties.get("response_value", 0))
                    mood_scores.append((response.properties.get("responded_at"), score))
                except:
                    continue
        
        if len(mood_scores) >= 3:
            # Sort by date
            mood_scores.sort(key=lambda x: x[0])
            scores = [score for _, score in mood_scores]
            
            # Detect trend
            if len(scores) >= 3:
                recent_avg = sum(scores[-3:]) / 3
                earlier_avg = sum(scores[:-3]) / len(scores[:-3]) if len(scores) > 3 else scores[0]
                
                if recent_avg - earlier_avg > 1.0:
                    patterns.append(PatternInsight(
                        pattern_id=f"mood_improvement_{uuid4().hex[:8]}",
                        pattern_type="mood_improvement",
                        description="Patient shows improving mood trend over recent assessments",
                        affected_entities=[patient_node.entity_id],
                        confidence=min(0.9, abs(recent_avg - earlier_avg) / 2.0),
                        supporting_evidence=[r.node_id for r in quiz_responses[-3:]],
                        discovered_at=now_sao_paulo(),
                        agent_source="knowledge_graph"
                    ))
                elif earlier_avg - recent_avg > 1.0:
                    patterns.append(PatternInsight(
                        pattern_id=f"mood_decline_{uuid4().hex[:8]}",
                        pattern_type="mood_decline",
                        description="Patient shows declining mood trend over recent assessments",
                        affected_entities=[patient_node.entity_id],
                        confidence=min(0.9, abs(earlier_avg - recent_avg) / 2.0),
                        supporting_evidence=[r.node_id for r in quiz_responses[-3:]],
                        discovered_at=now_sao_paulo(),
                        agent_source="knowledge_graph"
                    ))
        
        return patterns
    
    async def _analyze_symptom_patterns(self, patient_node: GraphNode) -> List[PatternInsight]:
        """Analyze symptom patterns."""
        patterns = []
        
        # Get quiz responses mentioning symptoms
        connected = await self.get_connected_nodes(
            patient_node.node_id,
            [EdgeType.HAS_INTERACTION],
            "outgoing"
        )
        
        symptom_responses = []
        for node, edge in connected:
            if node.node_type == NodeType.QUIZ_RESPONSE:
                question_text = node.properties.get("question_text", "").lower()
                if any(keyword in question_text for keyword in ["sintoma", "efeito", "dor", "nausea"]):
                    symptom_responses.append(node)
        
        # Analyze for recurring symptoms
        if len(symptom_responses) >= 2:
            symptom_mentions = defaultdict(int)
            
            for response in symptom_responses:
                response_text = response.properties.get("response_value", "").lower()
                
                # Simple keyword detection (could be enhanced with NLP)
                symptoms = ["dor", "náusea", "fadiga", "insônia", "ansiedade", "irritação"]
                for symptom in symptoms:
                    if symptom in response_text:
                        symptom_mentions[symptom] += 1
            
            # Identify recurring symptoms
            for symptom, count in symptom_mentions.items():
                if count >= 2:
                    confidence = min(0.8, count / len(symptom_responses))
                    patterns.append(PatternInsight(
                        pattern_id=f"recurring_symptom_{symptom}_{uuid4().hex[:8]}",
                        pattern_type="recurring_symptom",
                        description=f"Patient frequently reports {symptom}",
                        affected_entities=[patient_node.entity_id],
                        confidence=confidence,
                        supporting_evidence=[r.node_id for r in symptom_responses],
                        discovered_at=now_sao_paulo(),
                        agent_source="knowledge_graph"
                    ))
        
        return patterns
    
    # Storage Methods
    async def _store_node_in_redis(self, node: GraphNode):
        """Store node in Redis."""
        if self.redis_client:
            await self.redis_client.hset(
                f"{self.redis_prefix}nodes",
                node.node_id,
                json.dumps(node.to_dict())
            )
    
    async def _store_edge_in_redis(self, edge: GraphEdge):
        """Store edge in Redis."""
        if self.redis_client:
            await self.redis_client.hset(
                f"{self.redis_prefix}edges",
                edge.edge_id,
                json.dumps(edge.to_dict())
            )
    
    async def _store_pattern_in_redis(self, pattern: PatternInsight):
        """Store pattern in Redis."""
        if self.redis_client:
            await self.redis_client.hset(
                f"{self.redis_prefix}patterns",
                pattern.pattern_id,
                json.dumps(asdict(pattern))
            )
    
    async def _load_graph_from_storage(self):
        """Load existing graph from Redis."""
        if not self.redis_client:
            return
        
        try:
            # Load nodes
            nodes_data = await self.redis_client.hgetall(f"{self.redis_prefix}nodes")
            for node_id, node_json in nodes_data.items():
                node_dict = json.loads(node_json)
                node = self._dict_to_node(node_dict)
                self.nodes[node_id] = node
                self.nodes_by_type[node.node_type].add(node_id)
                self.nodes_by_entity[node.entity_id] = node_id
            
            # Load edges
            edges_data = await self.redis_client.hgetall(f"{self.redis_prefix}edges")
            for edge_id, edge_json in edges_data.items():
                edge_dict = json.loads(edge_json)
                edge = self._dict_to_edge(edge_dict)
                self.edges[edge_id] = edge
                self.edges_by_type[edge.edge_type].add(edge_id)
                self.node_edges[edge.source_node].add(edge_id)
                self.node_edges[edge.target_node].add(edge_id)
            
            self.logger.info(f"Loaded {len(self.nodes)} nodes and {len(self.edges)} edges from storage")
            
        except Exception as e:
            self.logger.error(f"Error loading graph from storage: {e}")
    
    def _dict_to_node(self, node_dict: Dict[str, Any]) -> GraphNode:
        """Convert dictionary to GraphNode."""
        return GraphNode(
            node_id=node_dict["node_id"],
            node_type=NodeType(node_dict["node_type"]),
            entity_id=node_dict["entity_id"],
            properties=node_dict["properties"],
            created_at=datetime.fromisoformat(node_dict["created_at"]),
            updated_at=datetime.fromisoformat(node_dict["updated_at"]),
            confidence=node_dict.get("confidence", 1.0)
        )
    
    def _dict_to_edge(self, edge_dict: Dict[str, Any]) -> GraphEdge:
        """Convert dictionary to GraphEdge."""
        return GraphEdge(
            edge_id=edge_dict["edge_id"],
            edge_type=EdgeType(edge_dict["edge_type"]),
            source_node=edge_dict["source_node"],
            target_node=edge_dict["target_node"],
            properties=edge_dict["properties"],
            created_at=datetime.fromisoformat(edge_dict["created_at"]),
            strength=edge_dict.get("strength", 1.0),
            confidence=edge_dict.get("confidence", 1.0)
        )
    
    # Query Methods
    async def get_patient_context(self, patient_id: UUID) -> Dict[str, Any]:
        """Get comprehensive patient context from graph."""
        patient_node = await self.get_node_by_entity(str(patient_id))
        if not patient_node:
            return {}
        
        # Get all connected nodes
        connected = await self.get_connected_nodes(patient_node.node_id)
        
        # Organize by type
        context = {
            "patient": patient_node.properties,
            "quiz_sessions": [],
            "quiz_responses": [],
            "patterns": [],
            "insights": []
        }
        
        for node, edge in connected:
            if node.node_type == NodeType.QUIZ_SESSION:
                context["quiz_sessions"].append({
                    "properties": node.properties,
                    "relationship": edge.properties
                })
            elif node.node_type == NodeType.QUIZ_RESPONSE:
                context["quiz_responses"].append({
                    "properties": node.properties,
                    "relationship": edge.properties
                })
        
        # Get patterns for this patient
        patterns = [
            pattern for pattern in self.patterns.values()
            if str(patient_id) in pattern.affected_entities
        ]
        context["patterns"] = [asdict(pattern) for pattern in patterns]
        
        return context
    
    async def find_similar_patients(
        self,
        patient_id: UUID,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """Find patients with similar patterns."""
        patient_patterns = [
            pattern for pattern in self.patterns.values()
            if str(patient_id) in pattern.affected_entities
        ]
        
        if not patient_patterns:
            return []
        
        similar_patients = []
        patient_pattern_types = set(p.pattern_type for p in patient_patterns)
        
        # Compare with other patients
        for other_patient_id in self.nodes_by_entity:
            if other_patient_id == str(patient_id):
                continue
            
            other_patterns = [
                pattern for pattern in self.patterns.values()
                if other_patient_id in pattern.affected_entities
            ]
            
            if not other_patterns:
                continue
            
            # Calculate similarity based on common pattern types
            other_pattern_types = set(p.pattern_type for p in other_patterns)
            common_patterns = patient_pattern_types & other_pattern_types
            
            if common_patterns:
                similarity = len(common_patterns) / len(patient_pattern_types | other_pattern_types)
                
                if similarity >= similarity_threshold:
                    similar_patients.append((other_patient_id, similarity))
        
        # Sort by similarity
        similar_patients.sort(key=lambda x: x[1], reverse=True)
        return similar_patients
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Get knowledge graph statistics."""
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": {
                node_type.value: len(node_ids)
                for node_type, node_ids in self.nodes_by_type.items()
            },
            "edges_by_type": {
                edge_type.value: len(edge_ids)
                for edge_type, edge_ids in self.edges_by_type.items()
            },
            "total_patterns": len(self.patterns),
            "high_confidence_patterns": len([
                p for p in self.patterns.values()
                if p.confidence >= self.pattern_confidence_threshold
            ])
        }


# Singleton instance
_knowledge_graph: Optional[KnowledgeGraph] = None


def get_knowledge_graph(db: Session) -> KnowledgeGraph:
    """Get or create singleton knowledge graph instance."""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph(db)
    return _knowledge_graph