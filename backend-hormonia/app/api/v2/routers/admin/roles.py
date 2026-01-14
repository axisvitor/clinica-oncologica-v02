"""
Admin Roles & Permissions API v2.

Provides lightweight role/permission endpoints for admin dashboards.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.user import User

from .dependencies import get_admin_user

router = APIRouter()


@router.get(
    "/roles",
    summary="List roles",
    description="Return supported roles for admin tooling.",
)
async def list_roles(
    admin_user: User = Depends(get_admin_user),
):
    """Return available roles."""
    return {
        "data": [
            {
                "name": "admin",
                "description": "Administrator role",
                "permissions": [],
            },
            {
                "name": "doctor",
                "description": "Doctor role",
                "permissions": [],
            },
        ]
    }


@router.post(
    "/roles",
    summary="Create role (not implemented)",
    description="Role creation is not implemented yet.",
)
async def create_role(
    admin_user: User = Depends(get_admin_user),
):
    """Return 501 for role creation."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Role creation is not implemented",
    )


@router.get(
    "/permissions",
    summary="List permissions",
    description="Return supported permission identifiers.",
)
async def list_permissions(
    admin_user: User = Depends(get_admin_user),
):
    """Return permissions list."""
    return {"data": ["read", "write", "delete", "admin"]}
