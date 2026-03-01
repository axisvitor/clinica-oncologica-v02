"""Unit tests for session ownership and session-id scoping in auth router."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Response

from app.api.v2.routers import auth as auth_router
from app.core.exceptions import UnauthorizedError, ValidationError


def _unwrap(func):
    """Unwrap SlowAPI/FastAPI decorators to test endpoint core logic directly."""
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


def _build_request(session_id: str) -> MagicMock:
    request = MagicMock()
    request.cookies = {"session_id": session_id} if session_id is not None else {}
    request.headers = {}
    request.state = SimpleNamespace()
    return request


def _extract_filter_keys(filter_call) -> set[str]:
    keys: set[str] = set()
    for condition in filter_call.args:
        left = getattr(condition, "left", None)
        key = getattr(left, "key", None)
        if key:
            keys.add(key)
    return keys


@pytest.mark.asyncio
async def test_verify_session_requires_requested_session_match():
    """verify-session must query by requested session id + user id, not latest session."""
    verify_session_fn = _unwrap(auth_router.verify_session)
    request = _build_request(str(uuid4()))
    response = Response()
    current_user = {"id": str(uuid4())}

    session_query = MagicMock()
    session_query.filter.return_value = session_query
    session_query.first.return_value = None

    db = MagicMock()
    db.query.return_value = session_query

    with pytest.raises(UnauthorizedError):
        await verify_session_fn(
            request=request,
            response=response,
            current_user=current_user,
            db=db,
        )

    filter_keys = _extract_filter_keys(session_query.filter.call_args)
    assert {"id", "user_id"} <= filter_keys


@pytest.mark.asyncio
async def test_verify_session_rejects_invalid_session_id_format():
    """verify-session should fail fast when request session id is malformed."""
    verify_session_fn = _unwrap(auth_router.verify_session)
    request = _build_request("not-a-valid-session-id")
    response = Response()
    current_user = {"id": str(uuid4())}
    db = MagicMock()

    with pytest.raises(ValidationError):
        await verify_session_fn(
            request=request,
            response=response,
            current_user=current_user,
            db=db,
        )

    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_logout_scopes_session_revocation_to_current_user():
    """logout must only revoke sessions owned by the authenticated user."""
    logout_fn = _unwrap(auth_router.logout)
    request = _build_request(str(uuid4()))
    response = Response()
    current_user = {"id": str(uuid4())}

    redis_cache = AsyncMock()
    redis_cache.invalidate_session = AsyncMock(return_value=True)

    db_session_query = MagicMock()
    db_session_query.filter.return_value = db_session_query
    db_session_query.first.return_value = None

    db = MagicMock()
    db.query.return_value = db_session_query

    result = await logout_fn(
        request=request,
        response=response,
        current_user=current_user,
        redis_cache=redis_cache,
        db=db,
    )

    assert result["success"] is True
    filter_keys = _extract_filter_keys(db_session_query.filter.call_args)
    assert {"id", "user_id"} <= filter_keys
    db.commit.assert_not_called()
