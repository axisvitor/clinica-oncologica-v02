# Logging Standards

This document defines the logging standards for Backend Hormonia to ensure consistent, secure, and useful logging practices.

## Overview

**Problem Solved:** LOW-011 - Console.logs (print statements) in Production

Proper logging is essential for:
- **Debugging:** Troubleshoot issues in production
- **Monitoring:** Track application health
- **Security:** Audit trails for compliance
- **Performance:** Identify bottlenecks

---

## Logging Levels

### 1. DEBUG
**Use for:** Detailed diagnostic information
**Examples:**
- SQL queries executed
- Function entry/exit points
- Variable values during execution

```python
logger.debug(f"Processing patient {patient_id} with metadata: {metadata}")
```

### 2. INFO
**Use for:** General informational messages
**Examples:**
- Application startup
- Successful operations
- Business workflow milestones

```python
logger.info(f"Patient {patient_id} created successfully")
```

### 3. WARNING
**Use for:** Potentially harmful situations
**Examples:**
- Deprecated feature usage
- Recoverable errors
- Performance degradation

```python
logger.warning(f"Quiz response processing took {duration}ms (threshold: 500ms)")
```

### 4. ERROR
**Use for:** Error events that might still allow the application to continue
**Examples:**
- Failed API calls
- Database connection issues
- Validation failures

```python
logger.error(f"Failed to send WhatsApp message to {phone}", exc_info=True)
```

### 5. CRITICAL
**Use for:** Severe error events that might cause the application to abort
**Examples:**
- System crashes
- Data corruption
- Security breaches

```python
logger.critical(f"Database connection pool exhausted!", exc_info=True)
```

---

## Standard Logging Patterns

### Pattern 1: Function Entry/Exit

```python
import logging

logger = logging.getLogger(__name__)

def create_patient(patient_data: dict) -> Patient:
    """Create a new patient."""
    logger.debug(f"create_patient called with data: {patient_data}")

    try:
        patient = Patient(**patient_data)
        db.session.add(patient)
        db.session.commit()

        logger.info(f"Patient created: {patient.id}")
        return patient

    except Exception as e:
        logger.error(f"Failed to create patient: {e}", exc_info=True)
        raise
```

### Pattern 2: Performance Logging

```python
import time
import logging

logger = logging.getLogger(__name__)

def process_quiz_response(response_data: dict):
    """Process quiz response with timing."""
    start_time = time.time()

    try:
        # Process response
        result = process(response_data)

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"Quiz response processed in {duration_ms:.2f}ms")

        if duration_ms > 500:
            logger.warning(
                f"Slow quiz processing detected: {duration_ms:.2f}ms",
                extra={"duration_ms": duration_ms, "threshold": 500}
            )

        return result

    except Exception as e:
        logger.error(f"Quiz processing failed after {(time.time() - start_time) * 1000:.2f}ms", exc_info=True)
        raise
```

### Pattern 3: Structured Logging

```python
logger.info(
    "Patient onboarding completed",
    extra={
        "patient_id": patient.id,
        "cpf": patient.cpf,
        "onboarding_duration_ms": duration,
        "source": "web_form"
    }
)
```

---

## What NOT to Log

### ❌ Sensitive Data

**Never log:**
- Passwords or password hashes
- Credit card numbers
- CPF/RG (except last 4 digits)
- Phone numbers (except last 4 digits)
- Session tokens
- API keys
- Personal health information (PHI)

**❌ Bad:**
```python
logger.info(f"User login: {username} with password {password}")
logger.debug(f"Processing CPF: {cpf}")
```

**✅ Good:**
```python
logger.info(f"User login: {username} successful")
logger.debug(f"Processing CPF: ***-***-{cpf[-3:]}")
```

### ❌ Excessive Logging

**Don't log in tight loops:**
```python
# ❌ Bad - logs 10,000 times
for i in range(10000):
    logger.debug(f"Processing item {i}")
    process(item)

# ✅ Good - logs once
logger.debug(f"Processing {len(items)} items")
for item in items:
    process(item)
logger.debug("Processing complete")
```

---

## Logging Configuration

### Configuration File

**File:** `app/config/logging_config.py`

```python
import logging.config
import sys

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "default",
            "stream": sys.stdout
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "json",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": "json",
            "filename": "logs/error.log",
            "maxBytes": 10485760,
            "backupCount": 5
        }
    },
    "loggers": {
        "": {  # Root logger
            "level": "INFO",
            "handlers": ["console", "file", "error_file"]
        },
        "sqlalchemy.engine": {
            "level": "WARNING",  # Only log warnings/errors from SQLAlchemy
            "handlers": ["file"],
            "propagate": False
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        }
    }
}

def setup_logging():
    """Initialize logging configuration."""
    logging.config.dictConfig(LOGGING_CONFIG)
```

### Environment-Specific Levels

```bash
# .env.development
LOG_LEVEL=DEBUG
LOG_SQL=true

# .env.production
LOG_LEVEL=INFO
LOG_SQL=false
```

---

## Replacing print() Statements

### Before (❌)

```python
def create_patient(data):
    print(f"Creating patient: {data}")  # ❌ Bad

    patient = Patient(**data)
    print(f"Patient created: {patient.id}")  # ❌ Bad

    return patient
```

### After (✅)

```python
import logging

logger = logging.getLogger(__name__)

def create_patient(data):
    logger.debug(f"Creating patient with data: {data}")  # ✅ Good

    patient = Patient(**data)
    logger.info(f"Patient created successfully: {patient.id}")  # ✅ Good

    return patient
```

---

## Pre-commit Hook Enforcement

### Installation

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Test
pre-commit run --all-files
```

### Configuration

**File:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      - id: block-print-statements
        name: Block print() in production code
        entry: 'print\('
        language: pygrep
        types: [python]
        exclude: ^(scripts/|tests/)
        stages: [commit]
```

### Usage

```bash
# This commit will be blocked:
git add app/services/patient.py  # Contains print()
git commit -m "Add feature"
# ❌ ERROR: print() statement found!

# Fix by replacing with logger
# ✅ Commit succeeds
```

---

## Structured Logging with Context

### Adding Context

```python
import logging
import contextvars

# Context variable for request ID
request_id_var = contextvars.ContextVar('request_id', default=None)

class RequestIDFilter(logging.Filter):
    """Add request ID to log records."""

    def filter(self, record):
        record.request_id = request_id_var.get()
        return True

# Add filter to handler
handler.addFilter(RequestIDFilter())

# Set request ID in middleware
request_id_var.set(str(uuid.uuid4()))

# Now all logs include request ID
logger.info("Patient created")
# Output: [2025-01-16 10:30:15] INFO [req-abc123] Patient created
```

---

## Log Aggregation and Monitoring

### Tools Integration

#### 1. ELK Stack (Elasticsearch, Logstash, Kibana)

```python
# Send logs to Logstash
import logging
from logstash_async.handler import AsynchronousLogstashHandler

handler = AsynchronousLogstashHandler(
    host='logstash.hormonia.com.br',
    port=5000,
    database_path='logstash.db'
)
logger.addHandler(handler)
```

#### 2. Sentry (Error Tracking)

```python
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_sdk.init(
    dsn="https://...@sentry.io/...",
    integrations=[
        LoggingIntegration(
            level=logging.INFO,        # Capture info and above
            event_level=logging.ERROR  # Send errors to Sentry
        )
    ]
)
```

#### 3. CloudWatch (AWS)

```python
import watchtower

handler = watchtower.CloudWatchLogHandler(
    log_group='backend-hormonia',
    stream_name='production'
)
logger.addHandler(handler)
```

---

## Performance Considerations

### Lazy Logging

```python
# ❌ Bad - f-string always evaluated
logger.debug(f"Processing {expensive_function()} items")

# ✅ Good - only evaluated if DEBUG enabled
logger.debug("Processing %s items", expensive_function())
```

### Conditional Logging

```python
if logger.isEnabledFor(logging.DEBUG):
    expensive_debug_info = generate_debug_info()
    logger.debug(f"Debug info: {expensive_debug_info}")
```

---

## Log Rotation

### File-based Rotation

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    filename='logs/app.log',
    maxBytes=10485760,  # 10MB
    backupCount=5       # Keep 5 backup files
)
```

### Time-based Rotation

```python
from logging.handlers import TimedRotatingFileHandler

handler = TimedRotatingFileHandler(
    filename='logs/app.log',
    when='midnight',    # Rotate at midnight
    interval=1,         # Every day
    backupCount=30      # Keep 30 days
)
```

---

## Testing Logging

### Unit Tests

```python
import logging
import pytest

def test_patient_creation_logs(caplog):
    """Test that patient creation is logged."""

    with caplog.at_level(logging.INFO):
        patient = create_patient({"name": "Test Patient"})

    assert "Patient created successfully" in caplog.text
    assert patient.id in caplog.text
```

---

## Compliance and Auditing

### HIPAA Audit Logging

For HIPAA compliance, log:
- Patient data access (who, when, what)
- Data modifications (before/after values)
- Authentication events
- Authorization failures

```python
logger.info(
    "Patient record accessed",
    extra={
        "event_type": "PHI_ACCESS",
        "user_id": current_user.id,
        "patient_id": patient.id,
        "action": "read",
        "timestamp": datetime.utcnow().isoformat()
    }
)
```

---

## Migration Checklist

### Removing print() Statements

- [ ] Run automated script: `python scripts/remove_print_statements.py`
- [ ] Review changes: `git diff`
- [ ] Replace with appropriate logging levels
- [ ] Test application
- [ ] Install pre-commit hook
- [ ] Update CI/CD to check for print()

---

## References

- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [12-Factor App: Logs](https://12factor.net/logs)
- [Logging Best Practices](https://docs.python-guide.org/writing/logging/)

---

**Last Updated:** 2025-01-16
**Version:** 1.0.0
**Owner:** Backend Team
