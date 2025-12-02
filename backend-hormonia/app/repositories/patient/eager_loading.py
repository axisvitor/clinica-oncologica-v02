"""
Query optimization with eager loading strategies.
"""
import logging
from typing import List

from sqlalchemy.orm import joinedload, selectinload

from app.models.patient import Patient
from app.models.message import Message

logger = logging.getLogger(__name__)


class PatientEagerLoadingMixin:
    """
    Mixin for optimized eager loading strategies.
    """

    def _apply_eager_loading(self, query, eager_load: List[str] = None):
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

        # Nested eager loading for messages with sender
        # selectinload for messages (1:many), then joinedload for sender (1:1)
        if "messages" in eager_load:
            query = query.options(
                selectinload(Patient.messages).joinedload(Message.sender)
            )

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
