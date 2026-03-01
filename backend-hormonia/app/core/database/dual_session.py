"""Dual-mode session mixin for services shared between API (async) and Celery (sync).

Services inherit DualSessionMixin and call helper methods like self._execute(stmt)
instead of directly using db.query() or await db.execute(). The mixin branches
internally based on the session type passed at construction time.
"""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

T = TypeVar("T")


class DualSessionMixin:
    """Mixin providing sync/async DB operation helpers."""

    db: Session | AsyncSession

    @property
    def is_async(self) -> bool:
        """Check if the current session is async."""
        return isinstance(self.db, AsyncSession)

    def _execute(self, stmt, **kwargs) -> Any:
        """Execute statement. Returns Result or awaitable coroutine."""
        if self.is_async:
            return self.db.execute(stmt, **kwargs)
        return self.db.execute(stmt, **kwargs)

    def _scalars(self, stmt, **kwargs) -> Any:
        """Execute and return scalars. Returns ScalarResult or coroutine."""
        if self.is_async:
            return self.db.scalars(stmt, **kwargs)
        return self.db.scalars(stmt, **kwargs)

    def _get(self, entity: type[T], ident: Any) -> Any:
        """Get by primary key. Returns entity/None or coroutine."""
        if self.is_async:
            return self.db.get(entity, ident)
        return self.db.get(entity, ident)

    def _commit(self) -> Any:
        """Commit transaction. Returns None or coroutine."""
        if self.is_async:
            return self.db.commit()
        self.db.commit()
        return None

    def _flush(self) -> Any:
        """Flush changes. Returns None or coroutine."""
        if self.is_async:
            return self.db.flush()
        self.db.flush()
        return None

    def _refresh(self, instance: Any, **kwargs) -> Any:
        """Refresh instance. Returns None or coroutine."""
        if self.is_async:
            return self.db.refresh(instance, **kwargs)
        self.db.refresh(instance, **kwargs)
        return None

    def _add(self, instance: Any) -> None:
        """Add instance to the session."""
        self.db.add(instance)

    def _delete(self, instance: Any) -> Any:
        """Delete instance. Returns None or coroutine."""
        if self.is_async:
            return self.db.delete(instance)
        self.db.delete(instance)
        return None
