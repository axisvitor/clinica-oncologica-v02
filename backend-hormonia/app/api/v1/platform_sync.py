"""
API endpoints for platform synchronization and integration.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Any
from uuid import UUID
import redis.asyncio as redis

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.dependencies import get_redis, get_current_user
from app.services.platform_synchronization import PlatformSynchronizationService
from app.services.websocket_events import WebSocketEventService
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.repositories.flow_template import FlowTemplateRepository
from app.models.user import User

router = APIRouter(prefix="/platform", tags=["platform_sync"])


@router.post("/sync/patient/{patient_id}", response_model=None)
async def sync_patient_record(
    patient_id: UUID,
    interactions: List[dict[str, Any]],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Sync flow interactions to patient record."""
    try:
        # Initialize services
        patient_repo = PatientRepository(db)
        flow_repo = FlowTemplateRepository(db)
        websocket_service = WebSocketEventService(redis)
        
        sync_service = PlatformSynchronizationService(
            db=db,
            redis=redis,
            patient_repository=patient_repo,
            flow_repository=flow_repo,
            websocket_service=websocket_service
        )
        
        # Perform sync
        success = await sync_service.sync_patient_record_updates(patient_id, interactions)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to sync patient record")
        
        return {
            'success': True,
            'message': f'Successfully synced {len(interactions)} interactions for patient {patient_id}',
            'patient_id': str(patient_id),
            'interactions_count': len(interactions),
            'synced_at': datetime.utcnow().isoformat(),
            'synced_by': current_user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing patient record: {str(e)}")


@router.post("/audit/create", response_model=None)
async def create_audit_entry(
    entity_type: str,
    entity_id: UUID,
    action: str,
    changes: dict[str, Any],
    user_id: Optional[UUID] = None,
    source_system: str = "api",
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Create audit trail entry."""
    try:
        # Initialize services
        patient_repo = PatientRepository(db)
        flow_repo = FlowTemplateRepository(db)
        websocket_service = WebSocketEventService(redis)

        sync_service = PlatformSynchronizationService(
            db=db,
            redis=redis,
            patient_repository=patient_repo,
            flow_repository=flow_repo,
            websocket_service=websocket_service
        )
        
        # Create audit entry
        success = await sync_service.create_audit_trail_entry(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes,
            user_id=user_id or current_user.id,
            source_system=source_system
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create audit entry")
        
        return {
            'success': True,
            'message': 'Audit entry created successfully',
            'entity_type': entity_type,
            'entity_id': str(entity_id),
            'action': action,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': current_user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating audit entry: {str(e)}")


@router.get("/consistency/validate", response_model=None)
async def validate_data_consistency(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Validate cross-platform data consistency."""
    try:
        # Initialize services
        patient_repo = PatientRepository(db)
        flow_repo = FlowTemplateRepository(db)
        websocket_service = WebSocketEventService(redis)

        sync_service = PlatformSynchronizationService(
            db=db,
            redis=redis,
            patient_repository=patient_repo,
            flow_repository=flow_repo,
            websocket_service=websocket_service
        )
        
        # Validate consistency
        consistency_report = await sync_service.validate_cross_platform_consistency()
        
        return {
            'success': True,
            'consistency_report': consistency_report,
            'validated_by': current_user.email
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating consistency: {str(e)}")


@router.post("/auth/sync/{user_id}", response_model=None)
async def sync_user_permissions(
    user_id: UUID,
    flow_permissions: dict[str, Any],
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Sync flow system permissions with user authentication."""
    try:
        # Initialize services
        patient_repo = PatientRepository(db)
        flow_repo = FlowTemplateRepository(db)
        websocket_service = WebSocketEventService(redis)

        sync_service = PlatformSynchronizationService(
            db=db,
            redis=redis,
            patient_repository=patient_repo,
            flow_repository=flow_repo,
            websocket_service=websocket_service
        )
        
        # Sync permissions
        success = await sync_service.sync_authentication_integration(user_id, flow_permissions)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to sync user permissions")
        
        return {
            'success': True,
            'message': f'Successfully synced permissions for user {user_id}',
            'user_id': str(user_id),
            'permissions': flow_permissions,
            'synced_at': datetime.utcnow().isoformat(),
            'synced_by': current_user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing user permissions: {str(e)}")


@router.post("/sync/run", response_model=None)
async def run_periodic_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Manually trigger periodic synchronization."""
    try:
        # Initialize services
        patient_repo = PatientRepository(db)
        flow_repo = FlowTemplateRepository(db)
        websocket_service = WebSocketEventService(redis)

        sync_service = PlatformSynchronizationService(
            db=db,
            redis=redis,
            patient_repository=patient_repo,
            flow_repository=flow_repo,
            websocket_service=websocket_service
        )
        
        # Run sync in background
        background_tasks.add_task(sync_service.run_periodic_synchronization)
        
        return {
            'success': True,
            'message': 'Periodic synchronization started',
            'triggered_by': current_user.email,
            'triggered_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error triggering sync: {str(e)}")


@router.get("/sync/status", response_model=None)
async def get_sync_status(
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get synchronization status and metrics."""
    try:
        # Get sync queue depths
        patient_sync_queue_depth = await redis.llen("patient_sync_queue")
        audit_sync_queue_depth = await redis.llen("audit_sync_queue")
        
        # Get last sync timestamp
        last_sync = await redis.get("last_sync_timestamp")
        last_sync_time = None
        sync_lag_minutes = None
        
        if last_sync:
            last_sync_time = datetime.fromisoformat(last_sync.decode())
            sync_lag_minutes = (datetime.utcnow() - last_sync_time).total_seconds() / 60
        
        # Get recent sync results
        sync_result_keys = await redis.keys("sync_results:*")
        recent_results = []
        
        for key in sorted(sync_result_keys, reverse=True)[:5]:  # Last 5 results
            result_data = await redis.get(key)
            if result_data:
                recent_results.append(json.loads(result_data))
        
        return {
            'sync_status': {
                'patient_sync_queue_depth': patient_sync_queue_depth,
                'audit_sync_queue_depth': audit_sync_queue_depth,
                'last_sync_time': last_sync_time.isoformat() if last_sync_time else None,
                'sync_lag_minutes': sync_lag_minutes,
                'status': 'healthy' if (sync_lag_minutes or 0) < 30 else 'lagging'
            },
            'recent_sync_results': recent_results,
            'checked_at': datetime.utcnow().isoformat(),
            'checked_by': current_user.email
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sync status: {str(e)}")


@router.get("/audit/trail/{entity_type}/{entity_id}", response_model=None)
async def get_audit_trail(
    entity_type: str,
    entity_id: UUID,
    days: int = Query(7, ge=1, le=365, description="Number of days to retrieve"),
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get audit trail for an entity."""
    try:
        audit_entries = []
        
        # Get audit entries for the specified date range
        for i in range(days):
            date = datetime.utcnow() - timedelta(days=i)
            audit_key = f"audit:{entity_type}:{entity_id}:{date.strftime('%Y%m%d')}"
            
            entries = await redis.lrange(audit_key, 0, -1)
            for entry_data in entries:
                try:
                    entry = json.loads(entry_data)
                    audit_entries.append(entry)
                except json.JSONDecodeError:
                    continue
        
        # Sort by timestamp (newest first)
        audit_entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {
            'entity_type': entity_type,
            'entity_id': str(entity_id),
            'audit_entries': audit_entries,
            'total_entries': len(audit_entries),
            'date_range_days': days,
            'retrieved_at': datetime.utcnow().isoformat(),
            'retrieved_by': current_user.email
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving audit trail: {str(e)}")


@router.get("/consistency/reports", response_model=None)
async def get_consistency_reports(
    days: int = Query(7, ge=1, le=30, description="Number of days to retrieve"),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get recent consistency validation reports."""
    try:
        # Get consistency report keys
        report_keys = await redis.keys("consistency_report:*")
        
        # Filter by date range
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_reports = []
        
        for key in report_keys:
            try:
                # Extract date from key
                date_str = key.decode().split(':')[1]
                report_date = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                
                if report_date >= cutoff_date:
                    report_data = await redis.get(key)
                    if report_data:
                        report = json.loads(report_data)
                        recent_reports.append(report)
                        
            except Exception as e:
                logger.error(f"Error processing report key {key}: {e}")
                continue
        
        # Sort by timestamp (newest first)
        recent_reports.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {
            'consistency_reports': recent_reports,
            'total_reports': len(recent_reports),
            'date_range_days': days,
            'retrieved_at': datetime.utcnow().isoformat(),
            'retrieved_by': current_user.email
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving consistency reports: {str(e)}")


@router.delete("/sync/cleanup", response_model=None)
async def cleanup_sync_data(
    older_than_days: int = Query(30, ge=1, le=365, description="Clean data older than X days"),
    db: Session = Depends(get_db),
    redis: Optional[redis.Redis] = Depends(get_redis),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Clean up old synchronization data."""
    try:
        # Initialize services
        patient_repo = PatientRepository(db)
        flow_repo = FlowTemplateRepository(db)
        websocket_service = WebSocketEventService(redis)
        
        sync_service = PlatformSynchronizationService(
            db=db,
            redis=redis,
            patient_repository=patient_repo,
            flow_repository=flow_repo,
            websocket_service=websocket_service
        )
        
        # Run cleanup
        cleanup_result = await sync_service._cleanup_old_sync_data()
        
        return {
            'success': cleanup_result['success'],
            'cleaned_count': cleanup_result.get('cleaned_count', 0),
            'older_than_days': older_than_days,
            'cleaned_at': datetime.utcnow().isoformat(),
            'cleaned_by': current_user.email,
            'error': cleanup_result.get('error')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning up sync data: {str(e)}")