"""
Admin endpoints for audit trail management.

Provides endpoints to:
- Get audit statistics
- Manually trigger cleanup
- Run VACUUM
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from app.jobs.audit_cleanup import AuditCleanupJob
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/stats", response_model=Dict[str, Any])
async def get_audit_stats(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current audit tables statistics.

    Requires admin role.

    Returns:
        - table_name: Name of audit table
        - total_records: Total number of records
        - old_records: Records older than 90 days
        - table_size: Current size of table
    """
    # Check admin permission
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    result = await AuditCleanupJob.get_stats()

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {result.get('error', 'Unknown error')}"
        )

    return result


@router.post("/cleanup", response_model=Dict[str, Any])
async def trigger_cleanup(
    run_vacuum: bool = False,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Manually trigger audit cleanup.

    Args:
        run_vacuum: Whether to run VACUUM after cleanup (default: False)

    Requires admin role.

    Returns:
        - success: Whether cleanup succeeded
        - timestamp: When cleanup was executed
        - total_deleted: Total records deleted
        - details: Per-table cleanup results
    """
    # Check admin permission
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    # Run cleanup
    result = await AuditCleanupJob.run()

    # Run VACUUM if requested
    if run_vacuum and result.get("success"):
        try:
            await AuditCleanupJob.run_vacuum()
            result["vacuum_executed"] = True
        except Exception as e:
            result["vacuum_error"] = str(e)
            result["vacuum_executed"] = False

    return result


@router.post("/vacuum", response_model=Dict[str, Any])
async def trigger_vacuum(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Manually trigger VACUUM on audit tables.

    Reclaims disk space after cleanup.

    Requires admin role.
    """
    # Check admin permission
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    try:
        await AuditCleanupJob.run_vacuum()
        return {
            "success": True,
            "message": "VACUUM executed successfully on audit tables"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"VACUUM failed: {str(e)}"
        )
