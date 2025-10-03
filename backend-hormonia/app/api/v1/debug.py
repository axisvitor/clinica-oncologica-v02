"""
Debug endpoints for diagnosing ServiceProvider initialization issues.
"""
import logging
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/session-manager-status", response_model=Dict[str, Any])
async def get_session_manager_status() -> Dict[str, Any]:
    """
    Get detailed status of the session manager and service provider system.

    This endpoint helps diagnose ServiceProvider initialization errors.
    """
    status_info = {
        "timestamp": None,
        "session_manager": {
            "initialized": False,
            "error": None
        },
        "request_factory": {
            "initialized": False,
            "error": None
        },
        "database": {
            "connectivity": "unknown",
            "error": None
        },
        "redis": {
            "connectivity": "unknown",
            "error": None
        },
        "service_provider": {
            "can_create": False,
            "error": None
        }
    }

    import time
    status_info["timestamp"] = time.time()

    # Check session manager
    try:
        from app.core.session_manager import get_session_manager
        session_manager = get_session_manager()
        status_info["session_manager"]["initialized"] = True
        status_info["session_manager"]["instance_id"] = hex(id(session_manager))
    except Exception as e:
        status_info["session_manager"]["error"] = str(e)
        logger.error(f"Session manager check failed: {e}")

    # Check request factory
    try:
        from app.core.session_manager import get_request_factory
        request_factory = get_request_factory()
        status_info["request_factory"]["initialized"] = True
        status_info["request_factory"]["instance_id"] = hex(id(request_factory))
    except Exception as e:
        status_info["request_factory"]["error"] = str(e)
        logger.error(f"Request factory check failed: {e}")

    # Check database connectivity
    try:
        from app.database import test_connection
        db_result = test_connection()
        status_info["database"]["connectivity"] = db_result.get("status", "unknown")
        if db_result.get("status") == "healthy":
            status_info["database"]["pool_info"] = db_result.get("pool_info", {})
        else:
            status_info["database"]["error"] = db_result.get("error", "Unknown error")
    except Exception as e:
        status_info["database"]["error"] = str(e)
        logger.error(f"Database connectivity check failed: {e}")

    # Check Redis connectivity
    try:
        from app.core.redis_manager import get_redis_manager
        redis_manager = get_redis_manager()
        redis_client = await redis_manager.get_async_client()
        await redis_client.ping()
        status_info["redis"]["connectivity"] = "healthy"
        status_info["redis"]["client_type"] = str(type(redis_client))
    except Exception as e:
        status_info["redis"]["error"] = str(e)
        logger.error(f"Redis connectivity check failed: {e}")

    # Test ServiceProvider creation
    try:
        from app.core.session_manager import get_request_factory
        request_factory = get_request_factory()
        get_provider = request_factory.create_service_provider_dependency()

        # Try to create a provider
        for provider in get_provider():
            provider.validate_session()
            status_info["service_provider"]["can_create"] = True
            status_info["service_provider"]["instance_id"] = hex(id(provider))
            break  # Just test one creation

    except Exception as e:
        status_info["service_provider"]["error"] = str(e)
        logger.error(f"ServiceProvider creation test failed: {e}")

    return status_info


@router.get("/service-imports-status", response_model=Dict[str, Any])
async def get_service_imports_status() -> Dict[str, Any]:
    """
    Check if all required services can be imported correctly.
    """
    import_status = {
        "timestamp": None,
        "imports": {}
    }

    import time
    import_status["timestamp"] = time.time()

    # List of critical imports to test
    critical_imports = [
        ("app.services", "ServiceProvider"),
        ("app.core.session_manager", "SessionManager"),
        ("app.core.session_manager", "get_session_manager"),
        ("app.core.session_manager", "get_request_factory"),
        ("app.database", "SessionLocal"),
        ("app.database", "test_connection"),
        ("app.services.auth", "AuthService"),
    ]

    for module_name, class_name in critical_imports:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            import_status["imports"][f"{module_name}.{class_name}"] = {
                "status": "success",
                "error": None
            }
        except Exception as e:
            import_status["imports"][f"{module_name}.{class_name}"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"Import test failed for {module_name}.{class_name}: {e}")

    return import_status


@router.get("/auth-service-test", response_model=Dict[str, Any])
async def test_auth_service_creation() -> Dict[str, Any]:
    """
    Test if AuthService can be created through the dependency system.
    """
    test_result = {
        "timestamp": None,
        "auth_service": {
            "can_create": False,
            "error": None,
            "through_dependency": False,
            "dependency_error": None
        }
    }

    import time
    test_result["timestamp"] = time.time()

    # Test direct creation
    try:
        from app.services.auth import AuthService
        from app.repositories.user import UserRepository
        from app.database import SessionLocal

        db = SessionLocal()
        user_repo = UserRepository(db)
        auth_service = AuthService(db=db, user_repository=user_repo, redis_client=None)

        test_result["auth_service"]["can_create"] = True
        test_result["auth_service"]["instance_id"] = hex(id(auth_service))

        db.close()

    except Exception as e:
        test_result["auth_service"]["error"] = str(e)
        logger.error(f"Direct AuthService creation failed: {e}")

    # Test through dependency injection
    try:
        from app.dependencies import get_auth_service, get_thread_safe_service_provider

        # This is tricky to test without a request context
        # For now, just verify the dependencies exist
        test_result["auth_service"]["through_dependency"] = True
        test_result["auth_service"]["dependency_functions"] = [
            "get_auth_service",
            "get_thread_safe_service_provider"
        ]

    except Exception as e:
        test_result["auth_service"]["dependency_error"] = str(e)
        logger.error(f"Dependency injection test failed: {e}")

    return test_result