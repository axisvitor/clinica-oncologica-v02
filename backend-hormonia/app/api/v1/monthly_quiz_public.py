"""
Public Monthly Quiz API endpoints for external access.

These endpoints are specifically designed for external access without authentication.
They include enhanced security measures, rate limiting, and comprehensive logging.
"""
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse

from app.dependencies import get_monthly_quiz_service, get_request_context, RequestContext
from app.services.monthly_quiz_service import MonthlyQuizService
from app.monitoring.business_metrics import BusinessMetricsCollector
from app.schemas.monthly_quiz import (
    MonthlyQuizAccessRequest, MonthlyQuizAccessResponse,
    MonthlyQuizSubmitResponse
)
from app.utils.api_decorators import handle_service_exceptions
from app.middleware.rate_limiting import PublicEndpointRateLimiter
from app.utils.security import validate_public_request, sanitize_input

router = APIRouter()
logger = logging.getLogger(__name__)

# Optional authentication for enhanced logging (but not required)
security = HTTPBearer(auto_error=False)

# Rate limiter for public endpoints
rate_limiter = PublicEndpointRateLimiter(
    requests_per_minute=10,  # 10 requests per minute per IP
    requests_per_hour=50,    # 50 requests per hour per IP
    burst_limit=5            # Allow 5 rapid requests
)


@router.post("/access", response_model=MonthlyQuizAccessResponse)
@handle_service_exceptions
async def access_monthly_quiz_public(
    access_data: MonthlyQuizAccessRequest,
    request: Request,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service)
) -> MonthlyQuizAccessResponse:
    """
    Public endpoint to access a monthly quiz using a token.

    **Public endpoint** - No authentication required
    **Rate limited** - 10 requests per minute per IP
    **CORS enabled** - Supports external domain access

    This endpoint allows patients to access their quiz using the
    tokenized link sent to them via WhatsApp, email, or SMS.

    **Parameters**:
    - token: The access token from the quiz link

    **Returns**:
    - Quiz session details and questions

    **Security Features**:
    - Token validation and expiration checking
    - Rate limiting per IP address
    - Comprehensive audit logging
    - Input sanitization
    - CORS support for external domains
    """
    # Apply rate limiting
    await rate_limiter.check_rate_limit(request)
    
    # Validate and sanitize input
    await validate_public_request(request)
    access_data.token = sanitize_input(access_data.token)
    
    try:
        # Extract comprehensive request context
        ip_address = await _extract_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        referer = request.headers.get("referer", "unknown")
        origin = request.headers.get("origin", "unknown")
        
        # Enhanced logging for public access
        logger.info(
            "Public monthly quiz access attempt",
            extra={
                'event_type': 'monthly_quiz_public_access',
                'token_prefix': access_data.token[:10] if access_data.token else 'none',
                'ip_address': ip_address,
                'user_agent': user_agent,
                'referer': referer,
                'origin': origin,
                'timestamp': datetime.utcnow().isoformat(),
                'endpoint': '/api/v1/monthly-quiz-public/access'
            }
        )

        response = await service.access_quiz_via_token(
            access_data.token,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Log successful access with additional context
        logger.info(
            "Public monthly quiz accessed successfully",
            extra={
                'event_type': 'monthly_quiz_public_access_success',
                'session_id': str(response.quiz_session_id),
                'patient_name': response.patient_name,
                'ip_address': ip_address,
                'origin': origin,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Record failed access metrics
        metrics_collector = BusinessMetricsCollector()
        await metrics_collector.record_quiz_access_failure(
            patient_id="unknown",  # We might not have patient ID if token is invalid
            reason=str(e),
            ip_address=ip_address,
            token_prefix=access_data.token[:10] if access_data.token else "none"
        )

        logger.error(
            f"Error in public quiz access: {str(e)}",
            extra={
                'event_type': 'monthly_quiz_public_access_error',
                'ip_address': ip_address,
                'error_type': type(e).__name__,
                'timestamp': datetime.utcnow().isoformat()
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to access quiz. Please check your link and try again."
        )


@router.post("/submit", response_model=dict)
@handle_service_exceptions
async def submit_monthly_quiz_response_public(
    submit_data: MonthlyQuizSubmitResponse,
    request: Request,
    service: MonthlyQuizService = Depends(get_monthly_quiz_service)
) -> dict:
    """
    Public endpoint to submit a quiz response via token.

    **Public endpoint** - No authentication required
    **Rate limited** - 10 requests per minute per IP
    **CORS enabled** - Supports external domain access

    Allows patients to submit quiz responses using their access token.

    **Parameters**:
    - token: The access token
    - question_id: ID of the question being answered
    - response_value: The patient's response
    - response_metadata: Optional additional metadata

    **Returns**:
    - Confirmation of submission

    **Security Features**:
    - Token validation for each submission
    - Response validation against question type
    - Rate limiting per IP address
    - Input sanitization
    - Comprehensive audit logging
    """
    # Apply rate limiting
    await rate_limiter.check_rate_limit(request)
    
    # Validate and sanitize input
    await validate_public_request(request)
    submit_data.token = sanitize_input(submit_data.token)

    # Preserve arrays for multi-select, sanitize each item
    if isinstance(submit_data.response_value, list):
        submit_data.response_value = [sanitize_input(str(item)) for item in submit_data.response_value]
    elif submit_data.response_value is not None:
        submit_data.response_value = sanitize_input(str(submit_data.response_value))
    
    try:
        # Extract comprehensive request context
        ip_address = await _extract_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        referer = request.headers.get("referer", "unknown")
        origin = request.headers.get("origin", "unknown")
        
        # Enhanced logging for submission attempt
        logger.info(
            "Public monthly quiz response submission",
            extra={
                'event_type': 'monthly_quiz_public_submit',
                'question_id': submit_data.question_id,
                'token_prefix': submit_data.token[:10] if submit_data.token else 'none',
                'ip_address': ip_address,
                'user_agent': user_agent,
                'referer': referer,
                'origin': origin,
                'timestamp': datetime.utcnow().isoformat(),
                'endpoint': '/api/v1/monthly-quiz-public/submit'
            }
        )

        result = await service.submit_quiz_response(
            submit_data,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Log successful submission
        logger.info(
            "Public monthly quiz response submitted successfully",
            extra={
                'event_type': 'monthly_quiz_public_submit_success',
                'response_id': result.get('response_id'),
                'question_id': submit_data.question_id,
                'ip_address': ip_address,
                'origin': origin,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Record failed submission metrics
        metrics_collector = BusinessMetricsCollector()
        await metrics_collector.record_quiz_submit_failure(
            patient_id="unknown",  # We might not have patient ID if token is invalid
            quiz_session_id="unknown",
            question_id=submit_data.question_id,
            reason=str(e)
        )

        logger.error(
            f"Error in public quiz submission: {str(e)}",
            extra={
                'event_type': 'monthly_quiz_public_submit_error',
                'question_id': submit_data.question_id,
                'ip_address': ip_address,
                'error_type': type(e).__name__,
                'timestamp': datetime.utcnow().isoformat()
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to submit response. Please check your data and try again."
        )


@router.get("/health", response_model=dict)
async def monthly_quiz_public_health() -> dict:
    """
    Public health check endpoint for monthly quiz functionality.
    
    **Public endpoint** - No authentication required
    
    This endpoint can be used by external services to verify
    that the monthly quiz public endpoints are operational.
    """
    return {
        "status": "healthy",
        "service": "monthly-quiz-public-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "access": "/api/v1/monthly-quiz-public/access",
            "submit": "/api/v1/monthly-quiz-public/submit",
            "health": "/api/v1/monthly-quiz-public/health"
        },
        "features": {
            "public_access": True,
            "rate_limiting": True,
            "cors_enabled": True,
            "security_headers": True,
            "audit_logging": True,
            "input_sanitization": True
        },
        "rate_limits": {
            "requests_per_minute": 10,
            "requests_per_hour": 50,
            "burst_limit": 5
        }
    }


async def _extract_client_ip(request: Request) -> str:
    """
    Extract client IP address with support for proxies and load balancers.
    """
    # Check X-Forwarded-For header (most common)
    if "x-forwarded-for" in request.headers:
        # Get first IP from X-Forwarded-For chain
        forwarded_ips = request.headers["x-forwarded-for"].split(",")
        return forwarded_ips[0].strip()
    
    # Check X-Real-IP header (Nginx)
    if "x-real-ip" in request.headers:
        return request.headers["x-real-ip"]
    
    # Check CF-Connecting-IP header (Cloudflare)
    if "cf-connecting-ip" in request.headers:
        return request.headers["cf-connecting-ip"]
    
    # Check X-Client-IP header
    if "x-client-ip" in request.headers:
        return request.headers["x-client-ip"]
    
    # Fallback to direct client connection
    return request.client.host if request.client else "unknown"
