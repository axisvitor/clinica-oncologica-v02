# Backend Initialization Scripts

Comprehensive scripts for system initialization, validation, and health checking.

## Scripts Overview

### 1. System Initialization (`init_system.py`)

Complete system initialization with comprehensive checks.

```bash
# Full initialization (validates and initializes all components)
python scripts/init_system.py

# Check-only mode (validation without changes)
python scripts/init_system.py --check-only

# Verbose mode (detailed logging)
python scripts/init_system.py --verbose
```

**Features:**
- Environment variable validation
- Configuration validation
- Database connectivity check and migrations
- Redis connectivity check
- Service dependency verification
- Application factory initialization

### 2. Database Initialization (`init_database.py`)

Database-specific initialization and migration management.

```bash
# Run migrations
python scripts/init_database.py

# Fresh database (WARNING: drops all data)
python scripts/init_database.py --fresh

# Seed initial data
python scripts/init_database.py --seed

# Skip migrations
python scripts/init_database.py --skip-migrations
```

**Features:**
- Database connection validation
- Fresh database creation
- Alembic migration execution
- Initial data seeding
- Schema integrity validation

### 3. Redis Initialization (`init_redis.py`)

Redis-specific initialization and configuration.

```bash
# Initialize Redis
python scripts/init_redis.py

# Configure Redis settings
python scripts/init_redis.py --configure

# Flush all data (WARNING: deletes all data)
python scripts/init_redis.py --flush
```

**Features:**
- Redis connection validation
- Redis configuration
- Cache structure initialization
- Data validation
- Performance testing

### 4. Health Check (`health_check.py`)

Comprehensive system health monitoring.

```bash
# Run health check
python scripts/health_check.py

# With custom timeout
python scripts/health_check.py --timeout 60

# JSON output
python scripts/health_check.py --json
```

**Features:**
- Database health and performance
- Redis health and metrics
- API endpoint validation
- System resource monitoring
- Response time tracking

### 5. Environment Validation (`validate_env.py`)

Environment configuration validation and security audit.

```bash
# Validate environment
python scripts/validate_env.py

# Strict mode (warnings as errors)
python scripts/validate_env.py --strict

# JSON output
python scripts/validate_env.py --json
```

**Features:**
- Required variable checking
- Format validation
- Security key validation
- CORS configuration check
- File permission audit
- Security vulnerability detection

## Usage Workflows

### Development Setup

```bash
# 1. Validate environment
python scripts/validate_env.py

# 2. Initialize database
python scripts/init_database.py --seed

# 3. Initialize Redis
python scripts/init_redis.py

# 4. Full system check
python scripts/init_system.py --check-only

# 5. Start application
uvicorn main:app --reload
```

### Production Deployment

```bash
# 1. Strict environment validation
python scripts/validate_env.py --strict

# 2. Database migrations
python scripts/init_database.py

# 3. System initialization
python scripts/init_system.py

# 4. Health check
python scripts/health_check.py

# 5. Start application
uvicorn main:app --host 0.0.0.0 --port 8000
```

### CI/CD Pipeline

```bash
# Pre-deployment checks
python scripts/validate_env.py --strict --json
python scripts/init_system.py --check-only

# Deployment
python scripts/init_database.py
python scripts/init_redis.py

# Post-deployment verification
python scripts/health_check.py --json
```

## Exit Codes

All scripts follow standard exit code conventions:

- `0` - Success
- `1` - Failure

This allows easy integration with CI/CD pipelines:

```bash
python scripts/init_system.py && echo "Success" || echo "Failed"
```

## Logging

All scripts log to:
- Standard output (console)
- `logs/` directory (file-based logging)

Log levels:
- `INFO` - Normal operation
- `WARNING` - Non-critical issues
- `ERROR` - Critical failures
- `DEBUG` - Detailed diagnostics (with `--verbose`)

## Dependencies

Required packages (already in requirements.txt):
- `asyncio` - Async operations
- `sqlalchemy` - Database operations
- `redis` - Redis operations
- `alembic` - Database migrations
- `httpx` - HTTP requests
- `psutil` - System monitoring

## Security Considerations

1. **Never commit .env files** - Contains sensitive credentials
2. **Set proper file permissions** - `chmod 600 .env`
3. **Use strong secrets** - Generate with `secrets.token_urlsafe(32)`
4. **Validate in CI/CD** - Run `validate_env.py --strict`
5. **Monitor health regularly** - Schedule `health_check.py`

## Troubleshooting

### Database Connection Fails

```bash
# Check DATABASE_URL format
echo $DATABASE_URL

# Test connection manually
psql $DATABASE_URL -c "SELECT 1"

# Validate configuration
python scripts/validate_env.py
```

### Redis Connection Fails

```bash
# Check REDIS_URL format
echo $REDIS_URL

# Test connection manually
redis-cli -u $REDIS_URL ping

# Initialize Redis
python scripts/init_redis.py
```

### Migration Errors

```bash
# Check current migration status
alembic current

# View migration history
alembic history

# Rollback one revision
alembic downgrade -1

# Re-run migrations
python scripts/init_database.py
```

## Maintenance

### Regular Tasks

**Daily:**
```bash
# Health check
python scripts/health_check.py --json >> logs/health.log
```

**Weekly:**
```bash
# Environment audit
python scripts/validate_env.py --strict --json >> logs/security_audit.log
```

**Before Deployments:**
```bash
# Full system check
python scripts/init_system.py --check-only
python scripts/health_check.py
```

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Run with `--verbose` flag for detailed output
3. Use `--json` flag for structured output
4. Review validation messages and suggestions
