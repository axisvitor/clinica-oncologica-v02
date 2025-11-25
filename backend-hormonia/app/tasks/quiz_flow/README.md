# Quiz Flow Tasks Package

This package contains all Celery tasks related to quiz flow processing, organized into logical modules.

## Package Structure

```
quiz_flow/
├── __init__.py              # Package exports (backward compatibility)
├── question_tasks.py        # Quiz question delivery tasks
├── response_tasks.py        # Quiz response processing tasks
├── monitoring_tasks.py      # Quiz monitoring and trigger tasks
├── cleanup_tasks.py         # Expired session cleanup tasks
├── helpers.py              # Shared helper functions
└── README.md               # This file
```

## Modules

### `question_tasks.py` (173 lines)
**Tasks for quiz question delivery and progress updates.**

- `send_quiz_question_task` - Send quiz questions to patients
- `send_quiz_progress_update_task` - Send progress updates during quiz completion

### `response_tasks.py` (173 lines)
**Tasks for quiz response processing and report generation.**

- `process_quiz_response_task` - Process patient quiz responses
- `generate_quiz_report_task` - Generate medical reports from quiz responses

### `monitoring_tasks.py` (274 lines)
**Tasks for quiz monitoring, triggers, and link management.**

- `check_quiz_triggers_task` - Check for patients needing quiz triggers
- `send_quiz_link_reminder_task` - Send reminders for pending quiz links
- `monitor_quiz_links_task` - Monitor quiz links for expirations

### `cleanup_tasks.py` (263 lines)
**Tasks for cleaning up expired quiz sessions.**

- `cleanup_expired_quiz_sessions_task` - Clean up expired quiz sessions (HIGH-004)
- `_notify_doctor_of_expired_session` - Notify doctors about expired sessions
- `_resume_patient_flow_after_expiration` - Resume patient flow after expiration

### `helpers.py` (138 lines)
**Shared helper functions used across quiz flow tasks.**

- `_trigger_whatsapp_fallback` - Trigger WhatsApp fallback when session expires
- `_notify_providers_of_quiz_completion` - Notify providers of quiz completion

## Backward Compatibility

All tasks are re-exported from `__init__.py` to maintain backward compatibility:

```python
# Old import (still works)
from app.tasks.quiz_flow import send_quiz_question_task

# New import (also works)
from app.tasks.quiz_flow.question_tasks import send_quiz_question_task
```

## Task Configurations

All Celery task decorators are preserved exactly as they were:

- **Retry logic**: Exponential backoff maintained
- **Task names**: All `name="..."` decorators preserved
- **Max retries**: Original retry counts kept
- **Delay intervals**: Original delay configurations maintained

## Line Count Summary

- Original `quiz_flow.py`: 963 lines
- New package total: 1,069 lines (includes documentation)
- Average module size: ~200 lines (well within maintainability guidelines)

## Migration Notes

No code changes required for existing imports. The package structure provides:

1. ✅ Better organization by functional area
2. ✅ Smaller, more maintainable files
3. ✅ Easier testing and development
4. ✅ Full backward compatibility
5. ✅ Preserved Celery configurations

## Testing

Test files can import helper functions and tasks exactly as before:

```python
from app.tasks.quiz_flow import (
    cleanup_expired_quiz_sessions_task,
    _notify_doctor_of_expired_session,
    _resume_patient_flow_after_expiration
)
```

## Related Tickets

- **HIGH-004**: Implements timeout and cleanup for abandoned quiz sessions
