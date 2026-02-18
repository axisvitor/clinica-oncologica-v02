"""
Query optimization with eager loading strategies.

This module provides optimized eager loading strategies for patient
queries to prevent N+1 query problems and improve performance.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Query, joinedload, selectinload

from app.models.patient import Patient

logger = logging.getLogger(__name__)


class PatientEagerLoadingMixin:
    """
    Mixin for optimized eager loading strategies.

    Provides methods to apply optimal eager loading based on
    relationship types to prevent N+1 queries.

    Strategy:
    - joinedload for 1:1 relationships (single query via JOIN)
    - selectinload for 1:many relationships (separate optimized queries)

    Methods:
        _apply_eager_loading: Apply eager loading to query.
    """

    def _apply_eager_loading(
        self, query: Query, eager_load: Optional[List[str]] = None
    ) -> Query:
        """
        Apply optimal eager loading strategies based on relationship types.

        PERFORMANCE STRATEGY:
        - joinedload for 1:1 relationships (doctor) - single query via JOIN
        - selectinload for 1:many relationships - separate optimized queries

        Args:
            query: SQLAlchemy query object
            eager_load: List of relationship names to load

        Returns:
            Query with eager loading applied
        """
        if not eager_load:
            return query

        # Always load doctor to prevent N+1 (1:1 relationship)
        query = query.options(joinedload(Patient.doctor))

        # Use selectinload for 1:many to avoid cartesian products
        if "quiz_sessions" in eager_load or "quizzes" in eager_load:
            query = query.options(selectinload(Patient.quiz_sessions))

        # Eager loading for messages (Message model has no sender relationship)
        if "messages" in eager_load:
            query = query.options(selectinload(Patient.messages))

        # Load flow states efficiently
        if "flow_states" in eager_load or "flow_executions" in eager_load:
            query = query.options(selectinload(Patient.flow_states))

        # Additional relationships for comprehensive loading
        if "treatments" in eager_load:
            query = query.options(selectinload(Patient.treatments))
        if "appointments" in eager_load:
            query = query.options(selectinload(Patient.appointments))
        if "medications" in eager_load:
            query = query.options(selectinload(Patient.medications))

        return query
