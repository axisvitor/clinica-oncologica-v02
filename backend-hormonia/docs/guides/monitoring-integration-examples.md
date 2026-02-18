# Monitoring Integration Examples

## Exemplos práticos de integração do sistema de monitoramento

## 1. Authentication Monitoring

### Failed Login Tracking

```python
from fastapi import HTTPException
from app.monitoring import (
    failed_auth_total,
    log_security_event,
    get_structured_logger
)

logger = get_structured_logger(__name__)

async def login(credentials: LoginCredentials):
    try:
        user = await authenticate(credentials)
    except InvalidCredentialsError:
        # Track failed authentication
        failed_auth_total.labels(
            method="password",
            reason="invalid_credentials"
        ).inc()

        # Log security event
        log_security_event(
            logger=logger,
            event_type="failed_auth",
            severity="medium",
            details={
                "username": credentials.username,
                "method": "password"
            },
            ip_address=request.client.host
        )

        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"access_token": generate_token(user)}
```

### Unauthorized Access Tracking

```python
from app.monitoring import unauthorized_access_total
from app.core.authorization import check_role

async def admin_endpoint(current_user: User):
    if not check_role(current_user, "admin"):
        # Track unauthorized access attempt
        unauthorized_access_total.labels(
            endpoint="/api/v2/admin",
            role=current_user.role,
            required_role="admin"
        ).inc()

        log_security_event(
            logger=logger,
            event_type="unauthorized_access",
            severity="high",
            details={
                "endpoint": "/api/v2/admin",
                "user_role": current_user.role,
                "required_role": "admin"
            },
            user_id=current_user.id,
            ip_address=request.client.host
        )

        raise HTTPException(status_code=403, detail="Insufficient permissions")
```

## 2. Performance Monitoring

### HTTP Request Tracking

```python
from app.monitoring import track_request_duration

@router.get("/patients")
async def get_patients(request: Request):
    with track_request_duration(
        method=request.method,
        endpoint=request.url.path,
        status_code=200
    ):
        # Your endpoint logic
        patients = await patient_service.get_all()
        return patients
```

### Database Query Monitoring

```python
from app.monitoring import track_db_query, log_performance_event

async def get_patient_with_monitoring(patient_id: int):
    with track_db_query(operation="SELECT", table="patients"):
        start_time = time.time()
        patient = await session.query(Patient).filter(
            Patient.id == patient_id
        ).first()
        duration_ms = (time.time() - start_time) * 1000

        # Log if query is slow
        if duration_ms > 100:
            log_performance_event(
                logger=logger,
                event_type="slow_query",
                duration_ms=duration_ms,
                details={
                    "operation": "SELECT",
                    "table": "patients",
                    "patient_id": patient_id
                },
                threshold_exceeded=True
            )

    return patient
```

### Cache Performance Tracking

```python
from app.monitoring import track_cache_access

class CachedPatientService:
    def __init__(self):
        self.hits = 0
        self.misses = 0

    async def get_patient(self, patient_id: int):
        # Try cache first
        cached = await redis.get(f"patient:{patient_id}")

        if cached:
            self.hits += 1
            result = json.loads(cached)
        else:
            self.misses += 1
            result = await db.query(Patient).filter(
                Patient.id == patient_id
            ).first()
            await redis.set(
                f"patient:{patient_id}",
                json.dumps(result),
                ex=3600
            )

        # Track cache performance
        track_cache_access(
            cache_type="redis",
            hits=self.hits,
            misses=self.misses
        )

        return result
```

### N+1 Query Detection

```python
from app.monitoring import n1_query_detected_total

@router.get("/patients-with-medications")
async def get_patients_with_medications():
    # BAD: N+1 query pattern
    patients = await session.query(Patient).all()

    for patient in patients:
        # This triggers a separate query for each patient!
        medications = await session.query(Medication).filter(
            Medication.patient_id == patient.id
        ).all()

        # Detect and track N+1
        n1_query_detected_total.labels(
            endpoint="/api/v2/patients-with-medications",
            model="Medication"
        ).inc()

    # GOOD: Use eager loading instead
    patients = await session.query(Patient).options(
        joinedload(Patient.medications)
    ).all()
```

## 3. Saga Monitoring

### Saga Execution Tracking

```python
from app.monitoring import track_saga_execution, saga_compensation_total

async def create_patient_saga(patient_data: dict):
    try:
        with track_saga_execution("patient_onboarding", "success"):
            # Execute saga steps
            patient = await create_patient_step(patient_data)
            await send_welcome_message_step(patient.id)
            await create_initial_quiz_step(patient.id)

            return patient

    except Exception as e:
        # Track compensation
        saga_compensation_total.labels(
            saga_type="patient_onboarding",
            reason=type(e).__name__
        ).inc()

        # Execute compensations
        await rollback_patient_creation(patient.id)

        log_business_event(
            logger=logger,
            event_type="saga_compensated",
            entity_type="saga",
            entity_id=None,
            details={
                "saga_type": "patient_onboarding",
                "reason": str(e),
                "compensations_executed": 3
            }
        )

        raise
```

## 4. Webhook Monitoring

### Webhook Processing with Metrics

```python
from app.monitoring import (
    webhook_processed_total,
    webhook_signature_failures_total
)

async def process_webhook(request: Request):
    # Validate signature
    signature = request.headers.get("X-Webhook-Signature")
    if not validate_signature(request.body, signature):
        webhook_signature_failures_total.labels(
            source="evolution"
        ).inc()

        log_security_event(
            logger=logger,
            event_type="webhook_signature_failure",
            severity="high",
            details={
                "source": "evolution",
                "endpoint": str(request.url)
            },
            ip_address=request.client.host
        )

        raise HTTPException(status_code=401, detail="Invalid signature")

    # Process webhook
    try:
        result = await handle_webhook_event(request.body)

        webhook_processed_total.labels(
            source="evolution",
            event_type=request.body.get("event_type"),
            status="success"
        ).inc()

        return {"status": "success"}

    except Exception as e:
        webhook_processed_total.labels(
            source="evolution",
            event_type=request.body.get("event_type"),
            status="failed"
        ).inc()

        raise
```

## 5. Rate Limiting Monitoring

### Rate Limit Tracking

```python
from app.monitoring import rate_limit_hits_total
from app.utils.rate_limiter import rate_limit

@router.post("/quiz/response")
@rate_limit(max_requests=10, window=60, tier="authenticated")
async def submit_quiz_response(
    response: QuizResponse,
    current_user: User
):
    # Rate limiter automatically tracks hits
    rate_limit_hits_total.labels(
        endpoint="/api/v2/quiz/response",
        tier="authenticated"
    ).inc()

    return await process_quiz_response(response)
```

## 6. Business Metrics

### Patient Creation Tracking

```python
from app.monitoring import patient_created_total, log_business_event

async def create_patient(patient_data: PatientCreate, source: str = "web"):
    patient = Patient(**patient_data.dict())
    session.add(patient)
    await session.commit()

    # Track business metric
    patient_created_total.labels(source=source).inc()

    # Log business event
    log_business_event(
        logger=logger,
        event_type="patient_created",
        entity_type="patient",
        entity_id=patient.id,
        details={
            "source": source,
            "has_phone": bool(patient.phone),
            "onboarding_complete": False
        }
    )

    return patient
```

### Quiz Session Tracking

```python
from app.monitoring import quiz_session_total, quiz_response_total

async def start_quiz_session(patient_id: int):
    session = QuizSession(patient_id=patient_id)
    db.add(session)
    await db.commit()

    quiz_session_total.labels(status="started").inc()

    return session

async def submit_quiz_response(response_data: dict):
    response = QuizResponse(**response_data)
    db.add(response)
    await db.commit()

    quiz_response_total.labels(
        question_type=response.question_type
    ).inc()

    return response
```

## 7. Custom Metrics

### Creating Custom Metrics

```python
from prometheus_client import Counter, Histogram

# Custom business metric
onboarding_completion_time = Histogram(
    'onboarding_completion_time_seconds',
    'Time to complete patient onboarding',
    ['onboarding_type'],
    buckets=[60, 300, 600, 1800, 3600]
)

async def complete_onboarding(patient_id: int, start_time: datetime):
    duration = (now_sao_paulo() - start_time).total_seconds()

    onboarding_completion_time.labels(
        onboarding_type="standard"
    ).observe(duration)

    log_business_event(
        logger=logger,
        event_type="onboarding_completed",
        entity_type="patient",
        entity_id=patient_id,
        details={
            "duration_seconds": duration,
            "onboarding_type": "standard"
        }
    )
```

## 8. Error Tracking

### Comprehensive Error Monitoring

```python
from app.monitoring import log_performance_event

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log error with context
    log_performance_event(
        logger=logger,
        event_type="unhandled_exception",
        duration_ms=0,
        details={
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "endpoint": str(request.url),
            "method": request.method
        },
        threshold_exceeded=True
    )

    # Return generic error to client
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
```

## Testing Monitoring

### Integration Tests

```python
import pytest
from prometheus_client import REGISTRY

def test_failed_auth_metric():
    # Get baseline
    before = REGISTRY.get_sample_value(
        'auth_failed_total',
        labels={'method': 'password', 'reason': 'invalid_credentials'}
    ) or 0

    # Trigger failed auth
    response = client.post("/api/v2/login", json={
        "username": "test",
        "password": "wrong"
    })

    # Check metric increased
    after = REGISTRY.get_sample_value(
        'auth_failed_total',
        labels={'method': 'password', 'reason': 'invalid_credentials'}
    )

    assert after == before + 1
```

## References

- [Prometheus Client Python](https://github.com/prometheus/client_python)
- [Structured Logging Best Practices](https://www.structlog.org/en/stable/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)
