"""Unified AI state definitions for LangGraph."""

from typing import Any, Dict, List, Optional, TypedDict


class AIState(TypedDict, total=False):
    """
    Unified state for AI orchestration.
    Used for humanization, sentiment analysis, classification, etc.
    """

    # Input data
    input_text: str
    template: Optional[str]
    context: Dict[str, Any]
    history: List[str]
    hints: List[str]

    # Processing parameters
    message_type: Optional[str]
    output_kind: str  # e.g., 'message', 'json', 'question'
    
    # Results
    output: Any
    confidence: float
    metadata: Dict[str, Any]
    
    # Error handling
    error: Optional[str]
