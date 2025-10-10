# WhatsApp Integration Guide - Patient Registration

## Overview

This guide documents the WhatsApp integration for automatic welcome messages sent to patients upon registration in the Hormonia oncology clinic system.

## Features

### Automatic Welcome Messages
- **Trigger**: Automatically sent when a new patient is registered
- **Content**: Personalized welcome message with clinic information
- **Priority**: High priority to ensure quick delivery
- **Reliability**: Non-blocking with automatic retry on failure

### Error Handling
- **Graceful Degradation**: Patient registration succeeds even if WhatsApp fails
- **Failure Logging**: All failures logged to database for analysis
- **Automatic Retry**: Exponential backoff retry mechanism (3 attempts by default)
- **Monitoring**: Comprehensive logging for debugging and monitoring

## Configuration

### Environment Variables

Add to `.env`:

```bash
# WhatsApp Integration Configuration
ENABLE_WHATSAPP_ON_REGISTRATION=true
WHATSAPP_WELCOME_MESSAGE_ENABLED=true
WHATSAPP_MAX_RETRIES=3
WHATSAPP_RETRY_DELAY_SECONDS=60

# Clinic Information (used in messages)
CLINIC_NAME="Clínica Oncológica Hormonia"
CLINIC_SUPPORT_PHONE="+5511999999999"

# Evolution API Configuration (required)
ENABLE_EVOLUTION=true
EVOLUTION_API_URL="https://your-evolution-api-url.com"
EVOLUTION_INSTANCE_NAME="clinica_oncologica"
EVOLUTION_API_KEY="your-evolution-api-key"
```

### Feature Flags

| Flag | Default | Description |
|------|---------|-------------|
| `ENABLE_WHATSAPP_ON_REGISTRATION` | `true` | Master switch for WhatsApp integration |
| `WHATSAPP_WELCOME_MESSAGE_ENABLED` | `true` | Enable/disable welcome messages |
| `WHATSAPP_MAX_RETRIES` | `3` | Maximum retry attempts for failed messages |
| `WHATSAPP_RETRY_DELAY_SECONDS` | `60` | Initial delay before first retry (uses exponential backoff) |

## Database Schema

### whatsapp_delivery_failures Table

```sql
CREATE TABLE whatsapp_delivery_failures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    message_content TEXT,
    error_message TEXT NOT NULL,
    error_code VARCHAR(50),
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMPTZ,
    last_retry_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    resolved_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Status Values**:
- `pending`: Waiting for retry
- `retrying`: Retry in progress
- `failed`: Max retries exceeded
- `resolved`: Successfully sent after retry

## Implementation Details

### Message Flow

1. **Patient Registration**
   ```
   POST /api/v1/patients
   └─> PatientService.create_patient()
       ├─> Create patient record
       ├─> Send WhatsApp welcome message (async)
       │   ├─> Success: Log and continue
       │   └─> Failure: Log to whatsapp_delivery_failures
       └─> Start treatment flow
   ```

2. **Retry Mechanism**
   ```
   Exponential Backoff Schedule:
   - Attempt 1: 60 seconds after failure
   - Attempt 2: 120 seconds after attempt 1
   - Attempt 3: 240 seconds after attempt 2
   - After 3 failures: Mark as 'failed', requires manual intervention
   ```

### Welcome Message Template

Location: `app/templates/whatsapp/welcome_message.py`

**Template Variables**:
- `patient_name`: Patient's name
- `clinic_name`: From `CLINIC_NAME` setting
- `support_phone`: From `CLINIC_SUPPORT_PHONE` setting (optional)

**Example Output**:
```
Olá Maria Silva! 👋

Seja bem-vindo(a) à Clínica Oncológica Hormonia!

Estamos muito felizes em tê-lo(a) conosco nesta jornada...

📱 O que esperar deste canal:
• Mensagens de acompanhamento diárias
• Lembretes de medicação e consultas
...
```

## API Usage

### Patient Registration Endpoint

```bash
POST /api/v1/patients
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Maria Silva",
  "phone": "+5511999999999",
  "email": "maria@example.com",
  "treatment_type": "hormone_therapy",
  "birth_date": "1980-01-15",
  "cpf": "12345678901"
}
```

**Response** (201 Created):
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Maria Silva",
  "phone": "+5511999999999",
  "email": "maria@example.com",
  "treatment_type": "hormone_therapy",
  "flow_state": "onboarding",
  "created_at": "2025-10-09T23:00:00Z"
}
```

**Background**: Welcome message sent asynchronously (non-blocking).

## Monitoring & Troubleshooting

### Check Delivery Failures

```sql
-- View recent WhatsApp delivery failures
SELECT
    patient_id,
    phone_number,
    message_type,
    error_message,
    retry_count,
    status,
    next_retry_at,
    created_at
FROM whatsapp_delivery_failures
WHERE status IN ('pending', 'retrying')
ORDER BY created_at DESC
LIMIT 20;
```

### View Retry Schedule

```sql
-- Messages scheduled for retry
SELECT
    patient_id,
    phone_number,
    retry_count,
    next_retry_at,
    EXTRACT(EPOCH FROM (next_retry_at - NOW())) / 60 AS minutes_until_retry
FROM whatsapp_delivery_failures
WHERE status = 'pending'
  AND next_retry_at > NOW()
ORDER BY next_retry_at;
```

### Failure Analysis

```sql
-- Most common error types
SELECT
    message_type,
    error_code,
    COUNT(*) as failure_count,
    AVG(retry_count) as avg_retries
FROM whatsapp_delivery_failures
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY message_type, error_code
ORDER BY failure_count DESC;
```

## Testing

### Unit Tests

```bash
# Run WhatsApp integration tests
pytest tests/integration/whatsapp/test_patient_registration_whatsapp.py -v

# Run with coverage
pytest tests/integration/whatsapp/ --cov=app.services.patient --cov-report=html
```

### Manual Testing

```bash
# 1. Enable test mode (uses mock WhatsApp service)
export ENABLE_EVOLUTION=false

# 2. Create test patient
curl -X POST http://localhost:8000/api/v1/patients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Patient",
    "phone": "+5511999999999",
    "email": "test@example.com",
    "treatment_type": "hormone_therapy"
  }'

# 3. Check logs for WhatsApp message status
tail -f logs/app.log | grep -i whatsapp
```

## Migration

### Apply Database Migration

```bash
# Run migration
cd backend-hormonia
alembic upgrade head

# Verify table created
psql $DATABASE_URL -c "\d whatsapp_delivery_failures"
```

### Rollback (if needed)

```bash
# Rollback migration
alembic downgrade -1
```

## Best Practices

### DO's ✅

- **Monitor failure logs regularly**: Check `whatsapp_delivery_failures` table weekly
- **Test with real phone numbers**: Verify messages in staging before production
- **Use feature flags**: Disable in development/testing environments
- **Log comprehensively**: All WhatsApp operations should be logged
- **Handle failures gracefully**: Never fail patient registration due to WhatsApp

### DON'Ts ❌

- **Don't block patient creation**: WhatsApp failures must not prevent registration
- **Don't retry indefinitely**: Respect max retry limit (default: 3)
- **Don't expose sensitive data**: Sanitize logs and error messages
- **Don't skip testing**: Always test welcome messages before deployment
- **Don't ignore failure patterns**: Investigate recurring errors

## Support

### Common Issues

**Issue**: Welcome messages not being sent
```
Solution:
1. Check ENABLE_WHATSAPP_ON_REGISTRATION=true
2. Verify Evolution API credentials
3. Check Evolution API connectivity
4. Review application logs
```

**Issue**: High failure rate
```
Solution:
1. Check Evolution API status/quota
2. Verify phone number format (+55XXXXXXXXXXX)
3. Review rate limiting settings
4. Check network connectivity
```

**Issue**: Retries not working
```
Solution:
1. Check WHATSAPP_MAX_RETRIES > 0
2. Verify background job processor is running
3. Check database connectivity
4. Review retry schedule in whatsapp_delivery_failures
```

## Changelog

### Version 1.0.0 (2025-10-09)
- Initial WhatsApp integration implementation
- Welcome message on patient registration
- Automatic retry with exponential backoff
- Failure logging and tracking
- Comprehensive test coverage

## Future Enhancements

- [ ] Background job for processing retry queue
- [ ] Admin dashboard for monitoring failures
- [ ] Custom message templates per treatment type
- [ ] Multi-language support
- [ ] Rich media messages (images, documents)
- [ ] Message delivery analytics
- [ ] Integration with Celery for async processing
