# API Migration Guide - Frontend v2.1.0

**Version:** 2.1.0
**Date:** January 2025
**Status:** Active Migration

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [CSRF Endpoint Migration](#csrf-endpoint-migration)
3. [New API Modules](#new-api-modules)
4. [Breaking Changes](#breaking-changes)
5. [Migration Checklist](#migration-checklist)
6. [Rollback Plan](#rollback-plan)

---

## 🎯 Overview

This guide covers the migration from deprecated endpoints to new standardized API endpoints in version 2.1.0.

### Key Changes

✅ **COMPLETED:**
- CSRF endpoint migrated to `/api/v2/auth/csrf-token`
- Appointments API module added
- Treatments API module added

⚠️ **IN PROGRESS:**
- Medications API module (pending)

---

## 🔐 CSRF Endpoint Migration

### Status: ✅ COMPLETED

### What Changed

The CSRF token endpoint was moved from the root API to the auth namespace for better organization.

**OLD (Deprecated):**
```
GET /api/v2/csrf-token
```

**NEW (Current):**
```
GET /api/v2/auth/csrf-token
```

### Migration Timeline

- **Phase 1:** ✅ New endpoint implemented (Backend v2.0.0)
- **Phase 2:** ✅ Frontend updated to use new endpoint (Frontend v2.1.0)
- **Phase 3:** ⏳ Deprecation notice added (Q1 2025)
- **Phase 4:** ⏳ Old endpoint removed (Q2 2025)

### Backend Compatibility

The backend currently supports **BOTH** endpoints:

```python
# OLD (Deprecated but still works)
@router.get("/csrf-token", deprecated=True)
async def get_csrf_token_deprecated():
    # Redirects to new endpoint
    ...

# NEW (Recommended)
@router.get("/auth/csrf-token")
async def get_csrf_token():
    # Current implementation
    ...
```

### Frontend Changes

**File:** `/frontend-hormonia/src/lib/api-client/core.ts`

**BEFORE:**
```typescript
async fetchCsrfToken(): Promise<void> {
  const response = await fetch(`${this.baseURL}/api/v2/csrf-token`, {
    credentials: 'include'
  })
  // ...
}
```

**AFTER:**
```typescript
async fetchCsrfToken(): Promise<void> {
  const response = await fetch(`${this.baseURL}/api/v2/auth/csrf-token`, {
    credentials: 'include'
  })
  // ...
}
```

### Action Required

✅ **NONE** - Migration is complete. All references updated.

### Verification

```bash
# Frontend - Verify no old endpoint usage
grep -r "csrf-token" frontend-hormonia/src --exclude-dir=node_modules

# Should only show: /api/v2/auth/csrf-token
```

---

## 📦 New API Modules

### 1. Appointments API ✨

**Status:** ✅ IMPLEMENTED

#### Module Location
`/frontend-hormonia/src/lib/api-client/appointments.ts`

#### Available Methods

```typescript
import { apiClient } from '@/lib/api-client'

// List appointments
const appointments = await apiClient.appointments.list({
  patient_id: 'patient-id',
  status: 'scheduled'
})

// Create appointment
const appointment = await apiClient.appointments.create({
  patient_id: 'patient-id',
  practitioner_id: 'doctor-id',
  appointment_type: 'consultation',
  scheduled_at: '2025-02-01T10:00:00Z',
  duration_minutes: 60
})

// Check conflicts
const conflicts = await apiClient.appointments.checkConflicts(
  'doctor-id',
  '2025-02-01T10:00:00Z',
  60
)

// Update status
await apiClient.appointments.cancel('id', 'Reason')
await apiClient.appointments.complete('id', 'Notes')
```

#### Migration from Patient API

**BEFORE (Old approach):**
```typescript
// Appointments accessed via patients
const patient = await apiClient.patients.get('patient-id')
const appointments = patient.appointments // Limited data
```

**AFTER (New approach):**
```typescript
// Direct appointments access
const appointments = await apiClient.appointments.getByPatient('patient-id')
// Full appointment data with relationships
```

#### TypeScript Types

```typescript
import type {
  Appointment,
  AppointmentCreate,
  AppointmentUpdate,
  AppointmentStatus,
  AppointmentType
} from '@/lib/api-client/types'
```

#### RBAC Requirements

- `view_appointments` - List and view appointments
- `create_appointment` - Create new appointments
- `edit_appointment` - Update and change status
- `delete_appointment` - Delete appointments

---

### 2. Treatments API ✨

**Status:** ✅ IMPLEMENTED

#### Module Location
`/frontend-hormonia/src/lib/api-client/treatments.ts`

#### Available Methods

```typescript
import { apiClient } from '@/lib/api-client'

// List treatments
const treatments = await apiClient.treatments.list({
  patient_id: 'patient-id',
  status: 'active'
})

// Create treatment
const treatment = await apiClient.treatments.create({
  patient_id: 'patient-id',
  treatment_type: 'quimioterapia',
  start_date: '2025-01-01',
  planned_sessions: '12'
})

// Status management
await apiClient.treatments.activate('treatment-id')
await apiClient.treatments.complete('treatment-id')
await apiClient.treatments.suspend('treatment-id', 'Reason')

// Statistics
const stats = await apiClient.treatments.getStatistics()
```

#### Migration from Patient API

**BEFORE (Old approach):**
```typescript
// Treatments accessed via patients
const patient = await apiClient.patients.get('patient-id')
const treatments = patient.treatments // Limited data
```

**AFTER (New approach):**
```typescript
// Direct treatments access
const treatments = await apiClient.treatments.getByPatient('patient-id')
const activeTreatments = await apiClient.treatments.getActiveByPatient('patient-id')
```

#### TypeScript Types

```typescript
import type {
  Treatment,
  TreatmentCreate,
  TreatmentUpdate,
  TreatmentStatus,
  TreatmentType
} from '@/lib/api-client/types'
```

#### RBAC Requirements

- `view_treatments` - List and view treatments
- `create_treatment` - Create new treatments
- `edit_treatment` - Update and manage lifecycle
- `delete_treatment` - Delete treatments
- `view_analytics` - View treatment statistics

---

### 3. Medications API ⏳

**Status:** ⚠️ PENDING IMPLEMENTATION

#### Planned Timeline

- **Q1 2025:** Implementation
- **Q1 2025:** Testing and validation
- **Q2 2025:** Production deployment

#### Expected Interface

```typescript
// Planned API (subject to change)
interface MedicationsApi {
  list(filters?: MedicationFilters): Promise<PaginatedResponse<Medication>>
  get(id: string): Promise<Medication>
  create(data: MedicationCreate): Promise<Medication>
  update(id: string, data: MedicationUpdate): Promise<Medication>
  delete(id: string): Promise<void>

  // Status management
  activate(id: string): Promise<Medication>
  deactivate(id: string): Promise<Medication>

  // Patient medications
  getByPatient(patientId: string): Promise<Medication[]>
  getActiveByPatient(patientId: string): Promise<Medication[]>
}
```

#### Current Workaround

Use patient API to access medications:

```typescript
const patient = await apiClient.patients.get('patient-id')
const medications = patient.medications // Limited data
```

---

## 💥 Breaking Changes

### None Currently

Version 2.1.0 maintains backward compatibility. All changes are additive.

### Deprecation Notices

#### 1. CSRF Endpoint (Deprecated Q1 2025, Removed Q2 2025)

```typescript
// ⚠️ DEPRECATED - Will be removed in v2.2.0
GET /api/v2/csrf-token

// ✅ USE THIS INSTEAD
GET /api/v2/auth/csrf-token
```

#### 2. Nested Patient Data (Soft Deprecated)

```typescript
// ⚠️ DISCOURAGED - Still works but less efficient
const patient = await apiClient.patients.get('id')
const appointments = patient.appointments
const treatments = patient.treatments

// ✅ RECOMMENDED - More efficient and flexible
const appointments = await apiClient.appointments.getByPatient('id')
const treatments = await apiClient.treatments.getByPatient('id')
```

---

## ✅ Migration Checklist

### For Developers

#### CSRF Migration ✅ COMPLETE

- [x] Update `core.ts` to use new endpoint
- [x] Test CSRF token fetching
- [x] Verify POST/PUT/DELETE requests include token
- [x] Update documentation

#### Appointments API ✅ COMPLETE

- [x] Create `appointments.ts` module
- [x] Add TypeScript types
- [x] Implement CRUD methods
- [x] Add status management (cancel, complete)
- [x] Implement conflict detection
- [x] Add unit tests
- [x] Update documentation

#### Treatments API ✅ COMPLETE

- [x] Create `treatments.ts` module
- [x] Add TypeScript types
- [x] Implement CRUD methods
- [x] Add lifecycle management (activate, complete, suspend)
- [x] Implement statistics
- [x] Add unit tests
- [x] Update documentation

#### Medications API ⏳ PENDING

- [ ] Create `medications.ts` module
- [ ] Add TypeScript types
- [ ] Implement CRUD methods
- [ ] Add lifecycle management
- [ ] Add unit tests
- [ ] Update documentation

### For Code Review

- [x] All endpoints return standardized responses
- [x] Error handling follows ApiError pattern
- [x] TypeScript types are complete
- [x] RBAC requirements documented
- [x] User-friendly error messages in Portuguese
- [x] Pagination support implemented
- [x] Retry logic configured correctly

### For QA Testing

- [x] CSRF protection working
- [x] Appointments CRUD operations functional
- [x] Treatments CRUD operations functional
- [x] Conflict detection working
- [x] Status lifecycle working
- [x] Error messages user-friendly
- [x] Pagination working correctly
- [ ] Medications API (pending implementation)

---

## 🔄 Rollback Plan

### If Issues Occur

#### 1. CSRF Endpoint Issues

**Symptoms:** CSRF validation failures

**Rollback:**
```typescript
// In core.ts, revert to old endpoint temporarily
async fetchCsrfToken(): Promise<void> {
  const response = await fetch(`${this.baseURL}/api/v2/csrf-token`, {
    credentials: 'include'
  })
  // ...
}
```

**Impact:** None (old endpoint still available)

#### 2. Appointments API Issues

**Symptoms:** Appointment operations failing

**Rollback:**
```typescript
// Comment out appointments import in index.ts
// import { appointmentsApi } from './appointments'

// Fall back to patient API for basic appointment data
const patient = await apiClient.patients.get('patient-id')
const appointments = patient.appointments
```

**Impact:** Limited appointment functionality

#### 3. Treatments API Issues

**Symptoms:** Treatment operations failing

**Rollback:**
```typescript
// Comment out treatments import in index.ts
// import { treatmentsApi } from './treatments'

// Fall back to patient API for basic treatment data
const patient = await apiClient.patients.get('patient-id')
const treatments = patient.treatments
```

**Impact:** Limited treatment functionality

---

## 📊 Migration Status

### Overall Progress

```
✅ CSRF Endpoint Migration:    100% Complete
✅ Appointments API:            100% Complete
✅ Treatments API:              100% Complete
⏳ Medications API:             0% (Planned Q1 2025)
```

### Coverage Improvement

```
Before v2.1.0:  80% endpoint coverage
After v2.1.0:   90% endpoint coverage (+10pp)
Target v2.2.0:  95% endpoint coverage
```

---

## 🎯 Next Steps

### Immediate (Q1 2025)

1. ⏳ Implement Medications API module
2. ⏳ Complete E2E tests for new modules
3. ⏳ Add monitoring for new endpoints

### Short-term (Q2 2025)

4. ⏳ Remove deprecated CSRF endpoint
5. ⏳ Complete migration guides for all teams
6. ⏳ Performance optimization

### Long-term (Q3-Q4 2025)

7. ⏳ GraphQL layer (optional)
8. ⏳ Real-time subscriptions
9. ⏳ Advanced caching strategies

---

## 📚 Additional Resources

- [API Client Guide](./API_CLIENT_GUIDE.md)
- [Backend API Documentation](../../backend-hormonia/docs/api/)
- [TypeScript Types Reference](../src/lib/api-client/types.ts)
- [RBAC Documentation](../../backend-hormonia/docs/security/)

---

## 📞 Support

For migration assistance:

1. Check this documentation
2. Review implementation examples in API Client Guide
3. Test in development environment first
4. Contact frontend development team

---

**Version:** 2.1.0
**Last Updated:** January 2025
**Maintained by:** Frontend Development Team
