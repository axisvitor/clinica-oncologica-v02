"""
Compatibility helpers for health patch paths.

This module keeps test/runtime behavior stable while the implementation is
organized across submodules.
"""

from __future__ import annotations

import inspect
import sys
from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies.auth_dependencies import (
    _get_service_provider,
    get_admin_user,
    get_current_user,
    security,
)
from app.models.user import User


def resolve_health_attr(name: str, default: Any) -> Any:
    """
    Resolve an attribute from the canonical health package when available.
    """
    package_name = __package__ or "app.api.v2.routers.health"
    health_module = sys.modules.get(package_name)
    if health_module is None and package_name != "app.api.v2.routers.health":
        health_module = sys.modules.get("app.api.v2.routers.health")
    if health_module is None:
        return default
    return getattr(health_module, name, default)


async def call_health_attr(name: str, default: Any, *args: Any, **kwargs: Any) -> Any:
    """
    Call a compatibility-resolved callable and await it when needed.
    """
    target = resolve_health_attr(name, default)

    if callable(target):
        result = target(*args, **kwargs)
    else:
        result = target

    if inspect.isawaitable(result):
        return await result
    return result


async def get_current_user_compat(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services=Depends(_get_service_provider),
) -> User:
    """
    Auth dependency that honors patch target `app.api.v2.routers.health.get_current_user`.
    """
    target = resolve_health_attr("get_current_user", get_current_user)

    if target is get_current_user:
        return await get_current_user(
            request=request,
            credentials=credentials,
            services=services,
        )

    try:
        result = target(
            request=request,
            credentials=credentials,
            services=services,
        )
    except TypeError:
        try:
            result = target(request=request)
        except TypeError:
            result = target()

    if inspect.isawaitable(result):
        result = await result
    return result


async def get_admin_user_compat(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services=Depends(_get_service_provider),
) -> User:
    """
    Admin dependency that honors patch target `app.api.v2.routers.health.get_admin_user`.
    """
    target = resolve_health_attr("get_admin_user", get_admin_user)

    if target is not get_admin_user:
        try:
            result = target(
                request=request,
                credentials=credentials,
                services=services,
            )
        except TypeError:
            try:
                result = target(request=request)
            except TypeError:
                result = target()

        if inspect.isawaitable(result):
            result = await result
        return result

    current_user = await get_current_user_compat(
        request=request,
        credentials=credentials,
        services=services,
    )
    return await get_admin_user(current_user=current_user)
