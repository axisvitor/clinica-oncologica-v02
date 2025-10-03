"""Service Dependencies - Clean Domain Separation"""
from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Optional
import redis.asyncio as redis

from app.database import get_db, get_supabase
from app.services import ServiceProvider, get_service_provider

# =============================================================================
# DATABASE & EXTERNAL SERVICE DEPENDENCIES
# =============================================================================

# Database dependency
get_database = get_db

# Supabase client dependency  
get_supabase_client = get_supabase

# Redis dependency
async def get_redis(services: ServiceProvider = Depends(get_service_provider)) -> Optional[redis.Redis]:
    """Get Redis client instance"""
    return services.redis_client

# =============================================================================
# DOMAIN SERVICE DEPENDENCIES (Using Clean Architecture)
# =============================================================================

# Patient Domain Services
def get_patient_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.patient_service

def get_patient_repository(db: Session = Depends(get_db)):
    from app.repositories.patient import PatientRepository
    return PatientRepository(db)

# Flow Domain Services
def get_flow_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.flow_service

def get_flow_state_repository(db: Session = Depends(get_db)):
    from app.repositories.flow import FlowStateRepository
    return FlowStateRepository(db)

def get_flow_analytics_service(db: Session = Depends(get_db)):
    from app.services.flow_analytics import FlowAnalyticsService
    return FlowAnalyticsService(db)

# Quiz Domain Services
def get_quiz_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.quiz_service

def get_quiz_template_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.quiz_service.template_service

def get_quiz_response_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.quiz_service.response_service

def get_quiz_session_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.quiz_service.session_service

def get_quiz_analytics_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.quiz_service.analytics_service

# Message Domain Services
def get_message_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.message_service

def get_auth_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.auth_service

# Analytics Domain Services
def get_analytics_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.analytics_service

# Report Domain Services
def get_report_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.report_service

# Notification Domain Services
def get_notification_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.notification_service

# File Domain Services
def get_file_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.file_service

# Monthly Quiz Domain Services
def get_monthly_quiz_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.monthly_quiz_service

# Metrics Domain Services
def get_metrics_collector_service(services: ServiceProvider = Depends(get_service_provider)):
    return services.metrics_collector_service

def get_metrics_redis_storage(services: ServiceProvider = Depends(get_service_provider)):
    return services.metrics_redis_storage

# =============================================================================
# ENHANCED SERVICE DEPENDENCIES (For advanced features)
# =============================================================================

async def get_cache_service():
    """Get cache service instance"""
    from app.services.cache import CacheService
    return CacheService()

async def get_websocket_manager():
    """Get WebSocket manager instance"""
    from app.services.websocket_manager import WebSocketManager
    return WebSocketManager.get_instance()

# =============================================================================
# FLOW MANAGEMENT SERVICES (Specific to flow domain)
# =============================================================================

def get_flow_management_service(
    flow_repo=Depends(get_flow_state_repository),
    flow_engine=Depends(get_flow_service)
):
    """Get flow management service instance"""
    from app.services.flow_management import FlowManagementService
    return FlowManagementService(flow_repo, flow_engine)
