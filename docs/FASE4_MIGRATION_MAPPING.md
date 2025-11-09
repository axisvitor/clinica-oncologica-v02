# FASE 4: Migration Mapping

**Date**: 2025-11-09
**Branch**: `claude/analyze-phase4-cache-services-011CUxbFbUBkhPr9UutWziSN`

---

## 📋 Migration Strategy

Based on analysis of stub files and actual imports, here's the migration plan:

### 1. app/utils/unified_cache.py → app.infrastructure.cache

**Status**: DEPRECATED STUB (112 lines, all re-exports)
**Target**: `from app.infrastructure.cache import ...`
**Files affected**: ~15 files

**Migration**:
```python
# OLD:
from app.utils.unified_cache import UnifiedCacheManager, cache, cached
from app.utils.unified_cache import get_unified_cache_manager

# NEW:
from app.infrastructure.cache import UnifiedCacheManager, cache, cached
from app.infrastructure.cache import get_unified_cache_manager
```

**Files to update**:
- docs/PROJETO_MODERNIZATION_COMPLETE.md
- docs/CLEANUP_SCRIPT_INSTRUCTIONS.md
- backend-hormonia/app/utils/unified_cache.py (remove after migration)
- backend-hormonia/app/services/unified_cache.py (check if also stub)
- backend-hormonia/app/services/patient.py
- backend-hormonia/app/services/auth.py
- backend-hormonia/app/middleware/cache_middleware.py
- backend-hormonia/app/api/v2/performance.py
- backend-hormonia/app/api/v2/patients_flow.py
- backend-hormonia/app/api/v2/patients.py.archived
- backend-hormonia/app/api/v1_archived_2025-11-07/performance.py
- backend-hormonia/app/api/v1_archived_2025-11-07/patients.py
- backend-hormonia/app/api/v1_archived_2025-11-07/enhanced_analytics.py
- backend-hormonia/app/api/v1_archived_2025-11-07/admin/users.py
- backend-hormonia/SERVICES_MAP.md

---

### 2. app/services/message_sender.py → app.domain.messaging.delivery

**Status**: DEPRECATED STUB (21 lines, single re-export)
**Target**: `from app.domain.messaging.delivery import MessageSender`
**Files affected**: ~21 files

**Migration**:
```python
# OLD:
from app.services.message_sender import MessageSender

# NEW:
from app.domain.messaging.delivery import MessageSender
```

**Files to update**:
- docs/CLEANUP_SCRIPT_INSTRUCTIONS.md
- backend-hormonia/app/tasks/messaging.py
- backend-hormonia/app/tasks/flow_automation.py
- backend-hormonia/app/tasks/flows.py
- backend-hormonia/app/tasks/common.py
- backend-hormonia/app/services/monthly_quiz_message_integration.py
- backend-hormonia/app/services/follow_up_system.py
- backend-hormonia/app/services/error_recovery.py
- backend-hormonia/app/services/dlq_service.py
- backend-hormonia/app/domain/quizzes/integration/flow_integration.py
- backend-hormonia/app/domain/messaging/scheduling/message_scheduler.py
- backend-hormonia/app/domain/flows/core/flow_service.py
- backend-hormonia/app/domain/flows/core/message_handler.py
- backend-hormonia/app/domain/errors/flows/recovery_strategy.py
- backend-hormonia/app/domain/agents/quiz/question_presenter.py
- backend-hormonia/app/domain/agents/quiz/conductor.py
- backend-hormonia/app/domain/agents/quiz/notification_manager.py
- backend-hormonia/app/api/v2/messages/core.py
- backend-hormonia/app/api/v2/messages.py
- backend-hormonia/app/api/v1_archived_2025-11-07/messages.py
- backend-hormonia/app/agents/patient/flow_coordinator.py

---

### 3. app/services/message_factory.py → app.domain.messaging.core

**Status**: DEPRECATED STUB (21 lines, single re-export)
**Target**: `from app.domain.messaging.core import MessageFactory`
**Files affected**: ~11 files

**Migration**:
```python
# OLD:
from app.services.message_factory import MessageFactory

# NEW:
from app.domain.messaging.core import MessageFactory
```

**Files to update**:
- docs/CLEANUP_SCRIPT_INSTRUCTIONS.md
- backend-hormonia/docs/migrations/PHASE_3_SERVICES_CONSOLIDATION.md
- backend-hormonia/docs/migrations/FINAL_VALIDATION_CHECKLIST.md
- backend-hormonia/app/tasks/quiz_flow.py
- backend-hormonia/app/services/monthly_quiz_message_integration.py
- backend-hormonia/app/services/base.py
- backend-hormonia/app/services/ab_testing_integration.py
- backend-hormonia/app/services/ab_testing.py
- backend-hormonia/app/domain/quizzes/quiz_session_manager.py
- backend-hormonia/app/domain/quizzes/integration/flow_integration.py
- backend-hormonia/app/api/v1_archived_2025-11-07/ab_testing.py

---

### 4. app/core/redis_unified.py → KEEP (NOT DEPRECATED)

**Status**: ⚠️ **ACTIVE IMPLEMENTATION** (287 lines)
**Action**: **NO MIGRATION NEEDED** - This is the target file, not a stub!

**Reasoning**:
- This file is the **unified Redis client interface** (facade pattern)
- Imports from `app.core.redis_manager` (actual implementation)
- Provides recommended entry points: `get_redis_client()`, `get_async_redis()`, etc.
- Contains deprecation warnings for OLD clients (LegacyRedisClientFactory, SimplifiedRedisClient)
- 54 files import from this (expected - it's the unified interface)

**Conclusion**: Do NOT remove this file. It's the consolidation target.

---

## 📊 Summary

| File | Status | Action | Files Affected |
|------|--------|--------|----------------|
| app/utils/unified_cache.py | Stub | Remove after migration | ~15 |
| app/services/message_sender.py | Stub | Remove after migration | ~21 |
| app/services/message_factory.py | Stub | Remove after migration | ~11 |
| app/core/redis_unified.py | **Active** | **KEEP** | 54 (expected) |

**Total files to update**: ~47 files
**Total stub files to remove**: 3 files
**Total lines to remove**: ~154 lines (stubs only)

---

## 🔧 Execution Plan

1. ✅ **Create migration mapping** (this document)
2. ⏭️ **Update unified_cache imports** (~15 files)
3. ⏭️ **Update message_sender imports** (~21 files)
4. ⏭️ **Update message_factory imports** (~11 files)
5. ⏭️ **Update cleanup script** (remove self-import, fix targets)
6. ⏭️ **Run tests** to verify no breakage
7. ⏭️ **Remove stub files** (archive to legacy/)
8. ⏭️ **Create completion report**
9. ⏭️ **Commit and push**

---

**Next Step**: Start with unified_cache migration (smallest impact, ~15 files)
