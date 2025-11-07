# V1 API Code Duplication - Specific Examples

This document shows exact line numbers and code snippets of duplicated patterns that can be immediately consolidated.

---

## 1. EXCEPTION HANDLING DUPLICATION (450+ lines, 20+ instances)

### Pattern Found: Try-Except Identical Blocks

**flows.py (Lines 75-98):**
```python
try:
    return await flow_management.get_patient_flow_state(patient_id)
    
except FlowStateNotFoundError:
    raise flow_not_found_exception(str(patient_id))
except FlowOperationError as e:
    raise flow_operation_exception("get_state", str(e))
except Exception as e:
    logger.exception(f"Unexpected error getting flow state for patient {patient_id}")
    raise internal_server_exception("Failed to get flow state")
```

**Same Pattern Appears At:**
- flows.py:100-131 (advance_patient_flow)
- flows.py:133-172 (pause_patient_flow)
- flows.py:174-205 (resume_patient_flow)
- flows.py:207-237 (get_patient_flow_history)
- flows.py:468-496 (get_flow_templates)
- flows.py:498-523 (create_flow_template)
- quiz.py:45-90 (create_quiz_template) - Similar but with IntegrityError
- quiz.py:136-185 (update_quiz_template) - Similar pattern
- ai.py:298-305 (ai_chat)
- ai.py:441-448 (analyze_patient)
- ai.py:528-535 (generate_response)

**Solution:** Create decorator
```python
@handle_api_exceptions("endpoint_name")
async def endpoint(...):
    return await service.method()  # Exceptions handled automatically
```

**Savings:** 510 lines → 100 lines (80% reduction)

---

## 2. PAGINATION DUPLICATION (180+ lines, 5+ instances)

### Pattern 1: admin/users.py (Lines 186-216)

```python
# Build base query with optimizations
query = db.query(User)
query = build_user_filters(filters, query)

# Use optimized pagination
paginated_query, total, pagination_info = QueryOptimizer.optimize_pagination_query(
    query, page, size, max_size=100
)

# Execute query with ordering
users = paginated_query.order_by(User.created_at.desc()).all()

# Extract pagination info
total_pages = pagination_info['total_pages']
has_next = pagination_info['has_next']
has_previous = pagination_info['has_previous']

return UserListResponse(
    items=[UserResponse.model_validate(user) for user in users],
    total=total,
    page=page,
    size=size,
    total_pages=total_pages,
    has_next=has_next,
    has_previous=has_previous
)
```

### Pattern 2: quiz.py (Lines 100-110)

```python
templates, total = service.get_templates(
    skip=pagination.skip,
    limit=pagination.limit,
    active_only=active_only
)
return QuizTemplateListResponse(
    items=templates,
    total=total,
    page=pagination.skip // pagination.limit + 1 if pagination.limit > 0 else 1,
    size=pagination.limit
)
```

### Pattern 3: quiz.py (Lines 542-546, 559-565, 671-676)

Repeated 3+ times with identical structure.

**Duplication Issues:**
- Manual page calculation (error-prone)
- Different response formats
- Inconsistent pagination semantics

**Solution:** Use utility function
```python
def paginate(items: List, total: int, page: int, size: int) -> dict:
    """Build consistent paginated response."""
    total_pages = (total + size - 1) // size
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1
    }
```

**Savings:** 180 lines

---

## 3. VALIDATION DUPLICATION (190+ lines, 10+ instances)

### Pattern 1: admin/users.py (Lines 283-289)

```python
try:
    role_enum = UserRole(user_data.role.lower())
except ValueError:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid role: {user_data.role}"
    )
```

**Same Pattern At:**
- admin/users.py:453-462 (in update_user_role)
- admin/users.py:798-804 (in update_user_role again)

**Issue:** 3 separate implementations of identical validation

### Pattern 2: quiz.py (Lines 54-71)

```python
if not template_data.name or not template_data.name.strip():
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Template name cannot be empty"
    )

if not template_data.version or not template_data.version.strip():
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Template version cannot be empty"
    )

if not template_data.questions or len(template_data.questions) == 0:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Template must contain at least one question"
    )
```

**Same Pattern At:**
- quiz.py:145-159 (update_quiz_template)
- quiz.py:253-257 (create_template_version)

**Issue:** Template validation repeated 3 times in similar form

### Pattern 3: quiz.py (Lines 579-601)

```python
if not response_data.patient_id:
    raise HTTPException(...)
if not response_data.quiz_template_id:
    raise HTTPException(...)
if not response_data.question_id or not response_data.question_id.strip():
    raise HTTPException(...)
if not response_data.response_value or not str(response_data.response_value).strip():
    raise HTTPException(...)
```

**Savings:** 190 lines with centralized validators

---

## 4. PATIENT ACCESS VALIDATION DUPLICATION (75 lines, 15+ instances)

### Pattern: Direct Validation Calls

**flows.py Instances:**
- Line 116: `patient = await validate_patient_access(patient_id, current_user, patient_service)`
- Line 149: Same call
- Line 188: Same call
- Line 223: Same call
- Line 652: Same call
- Line 680: Same call
- Line 713: Same call

**quiz.py Instances:**
- Line 394: `await validate_patient_access(patient_id, current_user, patient_service)`
- Line 642: Same call
- Line 691: Same call
- Line 724: Same call

**ai.py Instances:**
- Line 252: `patient = await validate_patient_access(...)`
- Line 346: Same call
- Line 489: Same call
- Line 577: Same call
- Line 700: Same call
- Line 833: Same call
- Line 946: Same call

**Issue:** Manual calls instead of dependency injection

**Solution:** Already exists as dependency - ensure all use it consistently

---

## 5. CACHE MANAGEMENT DUPLICATION (150 lines, Lines 94-168)

### v1/ai.py Duplication

**get_redis_client() - Lines 94-121:**
```python
async def get_redis_client():
    """Get Redis client for caching with connection pooling and error handling."""
    try:
        from app.config import settings
        import redis.asyncio as redis
        
        # Enhanced connection with pooling and better timeout handling
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
            max_connections=20,
            retry_on_timeout=True,
        )
        
        # Verify connection
        await client.ping()
        logger.info("Redis client connected successfully for AI caching")
        return client
    except Exception as e:
        logger.warning(f"Redis unavailable for AI caching, falling back to no cache: {e}")
        return None
```

**Issue:** Exact same pattern already exists in:
- `/backend-hormonia/app/core/redis_unified.py` (centralized)
- `/backend-hormonia/app/api/v2/ai.py` (v2 version)

**get_cached_data() - Lines 123-148:**
```python
async def get_cached_data(redis_client, cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached data from Redis with error handling."""
    if redis_client is None:
        return None
    
    try:
        data = await redis_client.get(cache_key)
        if data:
            parsed_data = json.loads(data)
            logger.debug(f"Cache HIT for key: {cache_key}")
            return parsed_data
        else:
            logger.debug(f"Cache MISS for key: {cache_key}")
            return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error for cache key {cache_key}: {e}")
        # Invalidate corrupted cache entry
        try:
            await redis_client.delete(cache_key)
        except:
            pass
        return None
    except Exception as e:
        logger.warning(f"Cache read error for {cache_key}: {e}")
        return None
```

**Issue:** Identical logic already in `redis_unified.py`

**set_cached_data() - Lines 150-168:**
```python
async def set_cached_data(
    redis_client, cache_key: str, data: Dict[str, Any], ttl_seconds: int
) -> bool:
    """Set cached data in Redis with JSON serialization."""
    if redis_client is None:
        return False
    
    try:
        serialized_data = json.dumps(data, default=str, ensure_ascii=False)
        await redis_client.setex(cache_key, ttl_seconds, serialized_data)
        logger.debug(f"Cache SET for key: {cache_key} (TTL: {ttl_seconds}s)")
        return True
    except TypeError as e:
        logger.error(f"JSON serialization error for {cache_key}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Cache write error for {cache_key}: {e}")
        return False
```

**Solution:**
```python
# Replace entire lines 94-168 with:
from app.core.redis_unified import get_redis_client, get_cached_data, set_cached_data
```

**Savings:** 150 lines → 1 line

---

## 6. AUDIT LOGGING DUPLICATION (80 lines)

### admin/users.py - Lines 57-95

```python
async def log_user_action(
    audit_service: AuditService,
    action: str,
    user_id: UUID,
    admin_user: User,
    context: RequestContext,
    target_user: Optional[User] = None,
    additional_data: Optional[dict] = None
) -> None:
    """Log user management actions for audit trail."""
    try:
        event_data = {
            "action": action,
            "admin_user_id": str(admin_user.id),
            "admin_user_email": admin_user.email,
            "target_user_id": str(user_id),
            **(additional_data or {})
        }
        
        if target_user:
            event_data.update({
                "target_user_email": target_user.email,
                "target_user_role": target_user.role.value,
                "target_user_active": target_user.is_active
            })
        
        audit_service.log_event(
            event_type=f"admin_user_{action}",
            event_category="security",
            severity="info",
            user_id=admin_user.id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            event_data=event_data,
            result="success"
        )
    except Exception as e:
        logger.error(f"Failed to log user action {action}: {e}")
```

**Repeated Manual Calls At:**
- Line 200-206 (list_users)
- Line 304-308 (create_user)
- Line 364-366 (get_user)
- Line 477-485 (update_user)
- Line 562-566 (delete_user)
- Line 640-642 (activate_user)
- Line 724-726 (deactivate_user)
- Line 816-820 (update_user_role)
- Line 879-883 (update_user_permissions)
- Line 967-971 (reset_user_password)

**Issue:** 10+ manual calls that could be handled by decorator

**Solution:**
```python
@audit_action("create_user")
async def create_user(...):
    # Decorator automatically logs the action
    ...
```

**Savings:** 80 lines

---

## 7. PATIENT CONTEXT BUILDING DUPLICATION (80 lines)

### ai.py - Lines 249-265

```python
# Build patient context if patient_id provided
patient_context = None
if request.patient_id:
    # Validate patient access
    patient = await validate_patient_access(
        request.patient_id, current_user, get_patient_service(db)
    )
    
    # Build context
    context_builder = get_ai_service()
    patient_context = await context_builder.build_patient_context(
        str(request.patient_id),
        {
            "name": patient.name,
            "treatment_type": patient.treatment_type or "general",
            "current_day": patient.current_day,
        },
    )
```

**Identical Pattern At:**
- Lines 369-377 (analyze_patient)
- Lines 495-503 (generate_response)
- Lines 581-589 (analyze_sentiment)

**Issue:** Same 17-line block repeated 4 times

**Solution:**
```python
async def build_patient_context_safely(
    patient_id: UUID,
    current_user: User,
    db: Session
) -> Optional[PatientContext]:
    """Build patient context with validation."""
    try:
        patient = await validate_patient_access(
            patient_id, current_user, get_patient_service(db)
        )
        ai_service = get_ai_service()
        return await ai_service.build_patient_context(
            str(patient_id),
            {
                "name": patient.name,
                "treatment_type": patient.treatment_type or "general",
                "current_day": patient.current_day,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to build context: {e}")
        return None
```

**Savings:** 80 lines

---

## 8. AUTHORIZATION DUPLICATION (60 lines)

### ai.py - Lines 57-92

```python
async def verify_physician_or_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify user is a physician or admin.
    AI features are restricted to medical professionals only for patient safety
    and data privacy compliance.
    """
    role_value = (
        current_user.role.value
        if isinstance(current_user.role, UserRole)
        else str(current_user.role or "").lower()
    )
    
    if role_value not in {UserRole.DOCTOR.value, UserRole.ADMIN.value}:
        logger.warning(
            "Unauthorized AI access attempt by user %s with role %s",
            current_user.id,
            current_user.role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI features are only accessible to doctors and administrators",
        )
    return current_user
```

**Same Function At:**
- v2/ai.py:94-113 (nearly identical)

**Issue:** Function defined in both v1 and v2 independently

**Solution:** Move to `app/dependencies/auth_overrides.py` and import in both

**Savings:** 60 lines (shared between v1 and v2)

---

## 9. ANALYTICS PLACEHOLDER (DEAD CODE - 77 lines)

### quiz.py - Lines 760-836

```python
@router.get("/analytics/summary", response_model=dict)
@handle_service_exceptions
async def get_quiz_summary_analytics(
    date_from: Optional[str] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format)"),
    service: QuizAnalyticsService = Depends(get_quiz_analytics_service),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get quiz analytics summary.
    
    ⚠️ PLACEHOLDER IMPLEMENTATION
    This endpoint currently returns mock data for development purposes.
    
    TODO: Implement real analytics aggregation:
    - Total quizzes created (from quiz_templates table)
    - Total quiz responses (from quiz_responses table)
    - Total quiz sessions (from quiz_sessions table)
    - Average completion rate (calculated from sessions)
    - Response time metrics (from session durations)
    - User engagement scores (from response patterns)
    - Template popularity metrics (usage counts)
    - Temporal analysis (trends over date range)
    ...
    """
    logger = logging.getLogger(__name__)
    logger.warning(...)
    
    try:
        # TODO: Replace with actual service implementation
        return {
            "message": "Summary analytics endpoint - implementation needed in service layer",
            "date_from": date_from,
            "date_to": date_to,
            "total_templates": 0,  # TODO: Query COUNT(*)...
            "total_responses": 0,  # TODO: Query COUNT(*)...
            "total_sessions": 0,   # TODO: Query COUNT(*)...
            "completion_rate": 0.0  # TODO: Calculate...
        }
    except Exception as e:
        logger.error(...)
        raise HTTPException(...)
```

**Issue:** Entire endpoint is placeholder with hardcoded zeros

**Solution:** Delete entirely, direct users to v2/analytics

**Savings:** 77 lines (pure deletion)

---

## CONSOLIDATION IMPACT SUMMARY

| Category | Lines | Files Affected | Solution |
|----------|-------|-----------------|----------|
| Exception Handling | 510 | 4 | `@handle_api_exceptions` decorator |
| Pagination | 180 | 3 | `paginate()` utility function |
| Validation | 190 | 2 | `validate_*()` utility functions |
| Cache Management | 150 | 1 | Use `redis_unified.py` |
| Audit Logging | 80 | 1 | `@audit_action` decorator |
| Patient Context | 80 | 1 | `build_patient_context_safely()` utility |
| Authorization | 60 | 2 | Shared dependency |
| Analytics Placeholder | 77 | 1 | Delete (dead code) |
| **TOTAL** | **1,327** | **~4** | **Phase 1-2 Implementation** |

---

## Implementation Roadmap

### Immediate (Week 1)
- [x] Remove analytics placeholder (77 lines)
- [x] Create decorators.py for exception handling
- [x] Create validators.py for validation

### Short-term (Week 2-3)
- [ ] Apply decorators to all endpoints
- [ ] Consolidate pagination utilities
- [ ] Apply validators to all endpoints

### Medium-term (Week 4-6)
- [ ] Consolidate cache management (use redis_unified)
- [ ] Extract patient context building
- [ ] Consolidate audit logging

### Long-term (Month 3-6+)
- [ ] Deprecation warnings
- [ ] Client migration support
- [ ] Endpoint sunset

