"""
Lightweight A/B test manager placeholder.

The production system will eventually persist experiments in the database,
but the orchestrator currently just needs an object with a few helper
methods. This in-memory manager keeps the same public surface so the rest
of the domain layer can evolve without crashing when the module imports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ABTestDefinition:
    """Represents a simple in-memory A/B test definition."""

    id: str
    flow_name: str
    variants: List[str]
    allocation: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "draft"
    results: Dict[str, int] = field(default_factory=dict)


class ABTestManager:
    """
    Minimal A/B test manager used by the FlowOrchestrator.

    Responsibilities (placeholder version):
    - Create in-memory experiment definitions
    - Retrieve experiments by ID
    - Track simple result counters for debugging
    """

    def __init__(self):
        self._tests: Dict[str, ABTestDefinition] = {}
        logger.info("ABTestManager initialized (placeholder implementation)")

    def create_test(
        self,
        flow_name: str,
        variants: List[str],
        allocation: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Create a new in-memory A/B test and return its ID."""
        test_id = str(uuid4())
        definition = ABTestDefinition(
            id=test_id,
            flow_name=flow_name,
            variants=variants,
            allocation=allocation or {},
            metadata=metadata or {},
            status="active" if variants else "draft",
        )
        self._tests[test_id] = definition
        logger.debug("Created A/B test %s for flow %s", test_id, flow_name)
        return test_id

    def get_test(self, test_id: str) -> Optional[ABTestDefinition]:
        """Fetch a test definition if it exists."""
        return self._tests.get(test_id)

    def list_tests(self) -> List[ABTestDefinition]:
        """Return all known tests (for debugging endpoints)."""
        return list(self._tests.values())

    def record_result(self, test_id: str, variant: str) -> None:
        """Increment a simple counter for the given variant."""
        test = self._tests.get(test_id)
        if not test:
            logger.warning("Attempted to record result for unknown test %s", test_id)
            return
        test.results[variant] = test.results.get(variant, 0) + 1
        logger.debug("Recorded result for test %s variant %s", test_id, variant)
