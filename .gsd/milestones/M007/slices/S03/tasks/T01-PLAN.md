---
estimated_steps: 8
estimated_files: 3
---

# T01: Backend — Pydantic schemas and GET/PUT day-config endpoints

**Slice:** S03 — Editor de templates dia-a-dia para o médico
**Milestone:** M007

## Description

Add the thin day-config API layer that projects between the internal `steps` JSONB and a physician-friendly flat list. This is the core data contract — the frontend and tests both depend on it.

## Steps

1. **Add Pydantic schemas** to `backend-hormonia/app/schemas/v2/templates.py` (append at end, after the existing flow template schemas section):

   ```python
   # ==================== Day Config Editor Schemas ====================

   class DayConfigItem(BaseModel):
       """Physician-facing day configuration."""
       day_number: int = Field(..., ge=1, description="Day number in the flow")
       content: str = Field(..., min_length=1, description="Message content for this day")
       message_type: str = Field("question", description="Semantic type: question, motivation, or reminder")
       expects_response: bool = Field(False, description="Whether the system waits for patient response")

       @field_validator("message_type")
       @classmethod
       def validate_message_type(cls, v):
           allowed = {"question", "motivation", "reminder"}
           if v not in allowed:
               raise ValueError(f"message_type must be one of {allowed}, got '{v}'")
           return v

   class DayConfigListResponse(BaseModel):
       """Response for GET day configs."""
       template_id: str
       template_name: str
       is_draft: bool
       days: List[DayConfigItem]
       total_days: int

   class DayConfigListUpdate(BaseModel):
       """Request body for PUT day configs."""
       days: List[DayConfigItem] = Field(..., min_length=0, description="Complete list of day configurations")
   ```

2. **Add GET endpoint** in `backend-hormonia/app/api/v2/routers/flow_templates.py`. Add the import for new schemas at the top alongside existing imports from `app.schemas.v2.templates`:

   ```python
   from app.schemas.v2.templates import (
       ...,  # keep existing imports
       DayConfigItem,
       DayConfigListResponse,
       DayConfigListUpdate,
   )
   ```

   Add `GET /flows/{template_id}/days` endpoint after the existing `get_flow_template` route:

   ```python
   @router.get("/flows/{template_id}/days", response_model=DayConfigListResponse)
   @limiter.limit(RATE_LIMIT_READ)
   async def get_flow_template_days(
       request: Request,
       template_id: UUID,
       db: AsyncSession = Depends(get_async_db),
       current_user: Dict = Depends(get_current_user_from_session),
   ):
   ```

   Implementation: load `FlowTemplateVersion` by id (404 if missing), read `template.steps` (must be a list), project each step to `DayConfigItem`:
   - `day_number` = `step["day"]`
   - `content` = `step["messages"][0]["content"]` (first message), falling back to `step.get("content", "")` or `step.get("base_content", "")` or `step.get("message", "")` (same fallback chain as `_parse_db_template_version`)
   - `message_type` = `step.get("message_type", "question")`
   - `expects_response` = `step["messages"][0].get("expects_response", False)` if messages exist, else `False`

   Sort by `day_number`, return `DayConfigListResponse`.

3. **Add PUT endpoint** in the same file, `PUT /flows/{template_id}/days`:

   ```python
   @router.put("/flows/{template_id}/days", response_model=DayConfigListResponse)
   @limiter.limit(RATE_LIMIT_WRITE)
   async def update_flow_template_days(
       request: Request,
       template_id: UUID,
       payload: DayConfigListUpdate,
       db: AsyncSession = Depends(get_async_db),
       current_user: Dict = Depends(get_current_user_from_session),
   ):
   ```

   Implementation:
   - Load template (404 if missing)
   - `_check_write_permission(current_user)`
   - If `not template.is_draft`: raise HTTPException 409 "Cannot edit days of a published template. Create a new draft version first."
   - Check for duplicate `day_number` values → 400
   - Hydrate each `DayConfigItem` into the internal step format:
     ```python
     {
         "day": item.day_number,
         "send_mode": "wait_each" if item.expects_response else "single",
         "messages": [
             {"order": 1, "content": item.content, "expects_response": item.expects_response}
         ],
         "intent": f"day_{item.day_number}_message",
         "message_type": item.message_type,
     }
     ```
   - Set `template.steps = hydrated_steps` (always a list, never a dict)
   - Set `template.updated_at = now_sao_paulo()`
   - Commit
   - **Dual cache invalidation:**
     - `await _invalidate_template_cache("flow", template_id)` — clears template API cache
     - Also delete the runtime dispatch cache key: get `kind_key` from `template.kind` (eager load or query `FlowKind`), then `redis_client.delete(f"flow_template:{kind_key}:steps")` — clears the 1h TTL cache used by `StateMixin._get_day_config()`
   - Audit log: `AuditAction.UPDATE`, resource_type `"flow_template_days"`, details with template_id and day_count
   - Return updated `DayConfigListResponse` (re-project from saved steps)

4. **Import `get_async_redis`** at the top of `flow_templates.py` for Redis runtime cache invalidation:
   ```python
   from app.core.redis_manager import get_async_redis_client as get_async_redis
   ```
   Check if `get_async_redis_client` exists in redis_manager — if the name is different (e.g. `get_async_redis`), use whatever the existing templates_shared.py imports. Look at what `_invalidate_template_cache` in `templates_shared.py` uses.

## Must-Haves

- [ ] `DayConfigItem` schema validates `message_type` against `{question, motivation, reminder}`
- [ ] GET endpoint projects steps to physician-friendly day-config list
- [ ] PUT endpoint hydrates day-configs back to step format with `messages` list, `send_mode`, `intent`
- [ ] PUT returns 409 for non-draft templates
- [ ] PUT returns 400 for duplicate day_number values
- [ ] Dual cache invalidation: template API cache AND Redis `flow_template:{kind_key}:steps` key
- [ ] Steps written by PUT always produce a list (never a dict)

## Verification

- `cd backend-hormonia && python -c "from app.schemas.v2.templates import DayConfigItem, DayConfigListResponse, DayConfigListUpdate; print('Schemas OK')"` — imports work
- `cd backend-hormonia && python -c "from app.api.v2.routers.flow_templates import router; routes = [r.path for r in router.routes]; assert '/flows/{template_id}/days' in routes; print('Endpoints OK')"` — endpoints registered
- Verify hydration manually:
  ```python
  from app.schemas.v2.templates import DayConfigItem
  item = DayConfigItem(day_number=1, content="Hello!", message_type="question", expects_response=True)
  step = {"day": item.day_number, "send_mode": "wait_each", "messages": [{"order": 1, "content": item.content, "expects_response": item.expects_response}], "intent": f"day_{item.day_number}_message", "message_type": item.message_type}
  from app.services.flow.config_validation import validate_day_config
  validate_day_config(step, flow_kind="test", day_number=1)
  print("Validation OK")
  ```

## Observability Impact

- Signals added/changed: Audit log entry on PUT with `resource_type="flow_template_days"`, `day_count`, `template_id`; structured logger.info on successful save
- How a future agent inspects this: `GET /api/v2/templates/flows/{id}/days` for current state; audit log entries for change history
- Failure state exposed: 409 with "Cannot edit days of a published template" message; 400 with field-level validation errors; 404 for missing template

## Inputs

- `backend-hormonia/app/schemas/v2/templates.py` — Existing schema file; append new schemas after existing flow template schemas
- `backend-hormonia/app/api/v2/routers/flow_templates.py` — Existing router; add 2 new endpoint functions
- `backend-hormonia/app/api/v2/templates_shared.py` — Import `_check_write_permission`, `_invalidate_template_cache`, `_extract_user_context`, `RATE_LIMIT_READ`, `RATE_LIMIT_WRITE`; these are already imported in flow_templates.py
- `backend-hormonia/app/services/flow/config_validation.py` — Reference for `validate_day_config()` expectations (step must have `messages` list with `content` string, valid `send_mode`)
- `backend-hormonia/app/services/template_loader_pkg/loader.py` lines 264-340 — `_parse_db_template_version()` reads `step["day"]`, `step["messages"]`, `step["send_mode"]`, `step["intent"]`, `step.get("message_type")`. The PUT hydration must produce data in this shape.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` lines 17-67 — `_get_day_config()` caches `flow_template:{kind_key}:steps` in Redis with 1h TTL and finds steps by `step.get("day") == day`. The PUT must invalidate this cache key.
- The Redis async client is imported in `templates_shared.py` — check the import name there: `from app.core.redis_manager import get_async_redis_client as get_async_redis` or similar. Use the same pattern.
- `_CANONICAL_SEND_MODES` = `frozenset({"single", "sequential_auto", "wait_response", "wait_each"})` — the hydration uses "single" (no response expected) or "wait_each" (response expected)

## Expected Output

- `backend-hormonia/app/schemas/v2/templates.py` — 3 new Pydantic models appended: `DayConfigItem`, `DayConfigListResponse`, `DayConfigListUpdate`
- `backend-hormonia/app/api/v2/routers/flow_templates.py` — 2 new endpoint functions: `get_flow_template_days`, `update_flow_template_days`
