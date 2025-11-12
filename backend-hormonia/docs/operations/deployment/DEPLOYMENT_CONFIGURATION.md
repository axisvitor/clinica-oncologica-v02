# Deployment Configuration Guide

This document describes the configuration settings for deploying the Hormonia backend system with critical bug fixes.

## Overview

The configuration system has been enhanced to support:
- Advanced logging with rate limiting
- Centralized error tracking
- Critical bug fix monitoring
- Deployment validation

## New Configuration Settings

### Logging Configuration

#### `LOG_LEVEL` (default: "INFO")
- **Description**: Sets the logging level for the application
- **Values**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Production**: Use INFO or WARNING to reduce log volume
- **Development**: Use DEBUG for detailed troubleshooting

#### `MAX_LOGS_PER_SECOND` (default: 100)
- **Description**: Maximum logs per second to prevent rate limiting
- **Purpose**: Prevents hitting platform log limits (Railway: 500/sec)
- **Adjustment**: Reduce if hitting platform limits, increase for high-traffic apps

#### `ENABLE_REQUEST_LOGGING` (default: true)
- **Description**: Enable request logging middleware
- **Behavior**: Uses DEBUG level for routine operations to reduce noise
- **Production**: Consider setting to false to reduce log volume

#### `LOG_STACK_TRACES` (default: true)
- **Description**: Enable stack trace logging for errors
- **Production**: Can be false to reduce log size
- **Development**: Should be true for debugging

#### `LOG_DEDUPLICATION_WINDOW` (default: 300)
- **Description**: Time window in seconds for log deduplication
- **Purpose**: Prevents spam from repeated identical log messages
- **Value**: 300 seconds (5 minutes) is recommended

### Error Tracking Configuration

#### `ENABLE_ERROR_TRACKING` (default: true)
- **Description**: Enable centralized error tracking and database logging
- **Purpose**: Tracks critical errors like DI failures, role enum issues, schema problems
- **Production**: Should be true for monitoring

#### `MAX_ERROR_LOGS` (default: 1000)
- **Description**: Maximum number of error logs to store in database
- **Purpose**: Prevents unbounded database growth
- **Cleanup**: Old errors are automatically cleaned up when limit is reached

#### `ERROR_DEDUPLICATION_WINDOW` (default: 3600)
- **Description**: Time window in seconds for error deduplication
- **Purpose**: Groups similar errors together with count tracking
- **Value**: 3600 seconds (1 hour) is recommended

#### `ERROR_TRACKING_RATE_LIMIT` (default: 10)
- **Description**: Maximum error logs per minute for same error type
- **Purpose**: Prevents error log flooding from repeated failures
- **Adjustment**: Increase for high-traffic applications

#### `CRITICAL_ERROR_NOTIFICATION` (default: true)
- **Description**: Enable notifications for critical errors
- **Types**: Dependency injection, role enum, schema compatibility issues
- **Integration**: Works with monitoring systems and alerting

## Environment Variable Examples

### Development Environment
```bash
# Logging - Verbose for debugging
LOG_LEVEL=DEBUG
MAX_LOGS_PER_SECOND=50
ENABLE_REQUEST_LOGGING=true
LOG_STACK_TRACES=true
LOG_DEDUPLICATION_WINDOW=300

# Error Tracking - Full tracking
ENABLE_ERROR_TRACKING=true
MAX_ERROR_LOGS=500
ERROR_DEDUPLICATION_WINDOW=1800
ERROR_TRACKING_RATE_LIMIT=20
CRITICAL_ERROR_NOTIFICATION=true
```

### Production Environment
```bash
# Logging - Optimized for performance
LOG_LEVEL=INFO
MAX_LOGS_PER_SECOND=100
ENABLE_REQUEST_LOGGING=false
LOG_STACK_TRACES=false
LOG_DEDUPLICATION_WINDOW=300

# Error Tracking - Production monitoring
ENABLE_ERROR_TRACKING=true
MAX_ERROR_LOGS=1000
ERROR_DEDUPLICATION_WINDOW=3600
ERROR_TRACKING_RATE_LIMIT=10
CRITICAL_ERROR_NOTIFICATION=true
```

### High-Traffic Production
```bash
# Logging - Minimal for high traffic
LOG_LEVEL=WARNING
MAX_LOGS_PER_SECOND=200
ENABLE_REQUEST_LOGGING=false
LOG_STACK_TRACES=false
LOG_DEDUPLICATION_WINDOW=600

# Error Tracking - Aggressive deduplication
ENABLE_ERROR_TRACKING=true
MAX_ERROR_LOGS=2000
ERROR_DEDUPLICATION_WINDOW=7200
ERROR_TRACKING_RATE_LIMIT=5
CRITICAL_ERROR_NOTIFICATION=true
```

## Deployment Validation

### Pre-Deployment Validation

Run the deployment validation script before deploying:

```bash
# Full validation (requires running API)
python scripts/deployment_validation.py --base-url http://your-api-url

# Static validation only (for CI/CD)
python scripts/deployment_validation.py --skip-smoke-tests

# Quick health check
python scripts/validate_deployment_health.py --base-url http://your-api-url

# Critical fixes validation
python scripts/validate_critical_fixes.py --base-url http://your-api-url
```

### Bash Script (Linux/macOS)
```bash
# Run comprehensive validation
./scripts/deploy_validate.sh

# Skip API tests (for CI environments)
SKIP_API_TESTS=true ./scripts/deploy_validate.sh
```

### Windows Batch Script
```cmd
REM Run comprehensive validation
scripts\deploy_validate.bat

REM Skip API tests
set SKIP_API_TESTS=true
scripts\deploy_validate.bat
```

### Validation Checks

The deployment validation performs:

1. **Static Code Validation**
   - Dependency injection patterns
   - Role enum usage consistency
   - Database model compatibility
   - Date parameter handling

2. **Service Health Checks**
   - API endpoint availability
   - Database connectivity
   - Redis connection (if configured)

3. **Critical Endpoint Smoke Tests**
   - Analytics endpoints with date parameters
   - Monthly quiz endpoints with role checks
   - Alerts endpoints with schema compatibility

4. **Error Handling Validation**
   - Invalid date format handling
   - Authentication error responses
   - Schema compatibility errors

## Monitoring Integration

### Error Tracking Database

The system creates an `error_logs` table to track critical errors:

```sql
CREATE TABLE error_logs (
    id UUID PRIMARY KEY,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    context JSONB,
    count INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE
);
```

### Monitoring Endpoints

New monitoring endpoints are available:

- `GET /api/v2/monitoring/errors` - Error tracking metrics
- `GET /api/v2/monitoring/health` - System health status
- `GET /api/v2/monitoring/logs` - Log statistics

### Alerting Integration

Configure alerts for critical error patterns:

```python
# Example: Alert on dependency injection errors
if error_type == "DI_GENERATOR_ERROR" and count > 5:
    send_alert("Critical: Dependency injection failing repeatedly")

# Example: Alert on role enum errors
if error_type == "ROLE_ENUM_ERROR":
    send_alert("Critical: Role enum compatibility issue detected")
```

## Migration Guide

### From Previous Configuration

1. **Update .env file** with new logging settings
2. **Run database migration** for error tracking table
3. **Update deployment scripts** to use validation
4. **Configure monitoring** for new error types

### Database Migration

```bash
# Apply error tracking migration
alembic upgrade head

# Verify migration
python -c "from app.models.error_tracking import ErrorLog; print('Error tracking table ready')"
```

### Configuration Validation

```bash
# Validate configuration
python -c "from app.core.config import settings; print('Configuration valid')"

# Test error tracking
python -c "from app.core.error_handler import CriticalErrorHandler; print('Error handler ready')"
```

## Troubleshooting

### Common Issues

#### High Log Volume
- Reduce `MAX_LOGS_PER_SECOND`
- Set `ENABLE_REQUEST_LOGGING=false`
- Increase `LOG_DEDUPLICATION_WINDOW`

#### Missing Error Logs
- Check `ENABLE_ERROR_TRACKING=true`
- Verify database migration applied
- Check error handler initialization

#### Validation Failures
- Run individual validation scripts
- Check configuration file syntax
- Verify database connectivity

### Log Analysis

```bash
# Check error patterns
grep "ERROR" logs/app.log | head -20

# Monitor error tracking
python scripts/monitor_errors.py

# Validate deployment health
python scripts/validate_deployment_health.py
```

## Security Considerations

### Log Security
- Never log sensitive data (passwords, tokens)
- Sanitize error messages before logging
- Use structured logging for better parsing

### Error Tracking Security
- Limit error log retention time
- Sanitize stack traces in production
- Implement proper access controls for error endpoints

### Configuration Security
- Use environment variables for secrets
- Validate configuration at startup
- Implement secure defaults

## Performance Impact

### Logging Performance
- Rate limiting prevents log flooding
- Deduplication reduces storage requirements
- Structured logging improves parsing efficiency

### Error Tracking Performance
- Database writes are batched for efficiency
- Deduplication reduces database growth
- Cleanup processes prevent unbounded growth

### Monitoring Overhead
- Minimal impact with proper configuration
- Async processing for non-critical operations
- Configurable sampling for high-traffic scenarios

## Best Practices

### Development
- Use DEBUG logging for troubleshooting
- Enable all error tracking features
- Run validation scripts before commits

### Staging
- Use production-like logging configuration
- Test error tracking and alerting
- Validate deployment scripts

### Production
- Use INFO or WARNING log levels
- Enable error tracking and monitoring
- Implement proper alerting thresholds
- Regular validation and health checks