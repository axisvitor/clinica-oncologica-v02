# Patient Authorization Middleware Design

## Overview
The Patient Authorization Middleware enforces strict patient-only access to WhatsApp communication by validating phone numbers against registered patients before processing any webhook.

## Architecture Components

### 1. PatientAuthorizationMiddleware
- **Purpose**: Validate phone numbers against patient database
- **Scope**: All WhatsApp webhook endpoints
- **Security Level**: BLOCK all non-registered numbers

### 2. PhoneNumberSecurityService
- **Purpose**: Secure phone number validation and normalization
- **Features**:
  - Consistent E.164 normalization
  - Rate limiting per phone number
  - Security logging and monitoring

### 3. WhatsAppSecurityAuditService
- **Purpose**: Track and log all WhatsApp security events
- **Features**:
  - Unauthorized access attempts logging
  - Patient authorization audit trail
  - Security metrics and alerting

### 4. Database Schema Extensions
- **whatsapp_security_events** table
- **patient_phone_authorizations** table
- Enhanced webhook_events with security metadata

## Security Flow

1. **Webhook Received** → Extract phone number
2. **Phone Normalization** → Secure E.164 format
3. **Patient Authorization** → Database lookup with caching
4. **Security Logging** → Log authorization result
5. **Access Decision** → ALLOW (patient) or BLOCK (non-patient)
6. **Monitoring** → Real-time security alerts

## Implementation Phases

### Phase 1: Core Security (Priority 1)
- Patient authorization middleware
- Phone number security service
- Basic security logging

### Phase 2: Enhanced Monitoring (Priority 2)
- Security audit service
- Real-time alerting
- Dashboard integration

### Phase 3: Advanced Features (Priority 3)
- Patient onboarding flow security
- Advanced rate limiting
- ML-based anomaly detection