"""Dual-session DB adapter for saga orchestrator.

Provides async-safe DB operations that work transparently with both
AsyncSession (API path) and sync Session (Celery tasks via run_async).

This is an internal module - not re-exported from the package __init__.py.
"""

import inspect
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class SagaDBAdapterMixin:
    """Mixin providing dual-session DB operations.

    Subclasses must set ``self.db`` to either an ``AsyncSession``
    (API path) or a sync ``Session`` (Celery path). The adapter
    methods detect the session type at call time and route accordingly.
    """

    db: Any  # AsyncSession | Session - set by subclass __init__

    @staticmethod
    def _sync_select_execute(db, statement):
        entity = statement.column_descriptions[0].get("entity")
        query = db.query(entity)

        for criterion in getattr(statement, "_where_criteria", ()):
            query = query.filter(criterion)

        for order_by in getattr(statement, "_order_by_clauses", ()):
            query = query.order_by(order_by)

        limit_clause = getattr(statement, "_limit_clause", None)
        if limit_clause is not None:
            limit_value = getattr(limit_clause, "value", limit_clause)
            try:
                query = query.limit(int(limit_value))
            except (TypeError, ValueError):
                pass

        rows = query.all() if hasattr(query, "all") else None
        if not isinstance(rows, list):
            first_row = query.first() if hasattr(query, "first") else None
            rows = [first_row] if first_row is not None else []

        class _ScalarResult:
            def __init__(self, items):
                self._items = items

            def first(self):
                return self._items[0] if self._items else None

            def all(self):
                return self._items

        class _QueryResult:
            def __init__(self, items):
                self._items = items

            def scalars(self):
                return _ScalarResult(self._items)

            def first(self):
                return self._items[0] if self._items else None

        return _QueryResult(rows)

    async def _db_execute(self, statement):
        if not isinstance(self.db, AsyncSession) and hasattr(self.db, "query"):
            return self._sync_select_execute(self.db, statement)
        result = self.db.execute(statement)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _db_flush(self) -> None:
        result = self.db.flush()
        if inspect.isawaitable(result):
            await result

    async def _db_commit(self) -> None:
        result = self.db.commit()
        if inspect.isawaitable(result):
            await result

    async def _db_rollback(self) -> None:
        result = self.db.rollback()
        if inspect.isawaitable(result):
            await result


__all__ = ["SagaDBAdapterMixin"]
