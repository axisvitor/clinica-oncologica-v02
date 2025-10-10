# Eager Loading Quick Reference Guide

## 🎯 Quick Decision: When to Use Eager Loading?

| Scenario | Use eager_load=True | Use eager_load=False |
|----------|---------------------|----------------------|
| Reading data for display | ✅ YES | ❌ NO |
| Accessing relationships | ✅ YES | ❌ NO |
| List/paginated queries | ✅ YES | ❌ NO |
| Single record lookup | ✅ YES | ❌ NO |
| Creating/updating records | ❌ NO | ✅ YES |
| Deleting records | ❌ NO | ✅ YES |
| Bulk operations | ❌ NO | ✅ YES |
| Background jobs/cleanup | ❌ NO | ✅ YES |

---

## 📚 Repository Method Reference

### Treatment Repository
```python
from app.repositories.treatment import TreatmentRepository

treatment_repo = TreatmentRepository(db)

# All methods support eager_load parameter (default=True)
treatment = treatment_repo.get_by_id(id)  # Loads patient, doctor, medications
treatments = treatment_repo.get_by_patient(patient_id)  # All relationships loaded
active = treatment_repo.get_active()  # All relationships loaded
```

**Relationships Loaded**: patient, doctor, medications

---

### Appointment Repository
```python
from app.repositories.appointment import AppointmentRepository

appointment_repo = AppointmentRepository(db)

# All methods support eager_load parameter (default=True)
appointment = appointment_repo.get_by_id(id)  # Loads patient, practitioner
upcoming = appointment_repo.get_upcoming(practitioner_id=doctor_id)
by_date = appointment_repo.get_by_date_range(start_date, end_date)
```

**Relationships Loaded**: patient, practitioner

---

### Medication Repository
```python
from app.repositories.medication import MedicationRepository

medication_repo = MedicationRepository(db)

# All methods support eager_load parameter (default=True)
medication = medication_repo.get_by_id(id)  # Loads patient, prescribed_by, treatment
active = medication_repo.get_active(patient_id)
expiring = medication_repo.get_expiring_soon(days=30)
```

**Relationships Loaded**: patient, prescribed_by, treatment

---

### Notification Repository
```python
from app.repositories.notification import NotificationRepository

notification_repo = NotificationRepository(db)

# All methods support eager_load parameter (default=True)
notifications = notification_repo.get_by_user(user_id)  # Loads user, related_patient
unread = notification_repo.get_unread(user_id)
by_priority = notification_repo.get_by_priority(NotificationPriority.HIGH)
```

**Relationships Loaded**: user, related_patient

---

### Session Repository
```python
from app.repositories.session import SessionRepository

session_repo = SessionRepository(db)

# All methods support eager_load parameter (default=True)
session = session_repo.get_by_token(token)  # Loads user
active = session_repo.get_active_sessions(user_id)
by_device = session_repo.get_by_device(device_id)
```

**Relationships Loaded**: user

---

### Consent Repository
```python
from app.repositories.consent import ConsentRepository

consent_repo = ConsentRepository(db)

# All methods support eager_load parameter (default=True)
consent = consent_repo.get_by_id(id)  # Loads patient, consented_by, witness
active = consent_repo.get_active(patient_id)
pending = consent_repo.get_pending(patient_id)
expiring = consent_repo.get_expiring_soon(days=30)
```

**Relationships Loaded**: patient, consented_by, witness

---

## 🔧 Common Usage Patterns

### Pattern 1: Read Operations (USE eager_load=True)
```python
# ✅ GOOD: Let eager loading eliminate N+1 queries
treatments = treatment_repo.get_by_patient(patient_id)
for treatment in treatments:
    print(treatment.patient.name)  # Already loaded, no extra query
    print(treatment.doctor.email)  # Already loaded, no extra query
```

### Pattern 2: Write Operations (USE eager_load=False)
```python
# ✅ GOOD: Skip eager loading for mutations
consent = consent_repo.grant_consent(consent_id, user_id)  # Uses eager_load=False
session = session_repo.revoke_session(session_id)  # Uses eager_load=False
```

### Pattern 3: API Endpoints (USE eager_load=True)
```python
@router.get("/appointments")
async def get_appointments(
    practitioner_id: UUID,
    appointment_repo: AppointmentRepository = Depends()
):
    # ✅ GOOD: Eager loading automatically loads all relationships
    appointments = appointment_repo.get_by_practitioner(practitioner_id)
    return [
        {
            "id": apt.id,
            "patient_name": apt.patient.name,  # No N+1 query
            "practitioner_name": apt.practitioner.full_name,  # No N+1 query
            "scheduled_start": apt.scheduled_start
        }
        for apt in appointments
    ]
```

### Pattern 4: Background Jobs (USE eager_load=False)
```python
# ✅ GOOD: Skip eager loading for cleanup operations
expired_sessions = session_repo.get_expired_sessions(eager_load=False)
for session in expired_sessions:
    session_repo.delete(session.id)
```

---

## 📊 Performance Impact Examples

### Before Eager Loading (N+1 Queries)
```python
# ❌ BAD: Without eager loading
treatments = db.query(Treatment).filter(Treatment.patient_id == patient_id).all()  # 1 query

for treatment in treatments:  # 10 treatments
    patient_name = treatment.patient.name  # +10 queries
    doctor_name = treatment.doctor.full_name  # +10 queries
    med_count = len(treatment.medications)  # +10 queries

# Total: 31 queries (1 + 10*3)
```

### After Eager Loading (3 Queries)
```python
# ✅ GOOD: With eager loading
treatments = treatment_repo.get_by_patient(patient_id)  # 1 query + 2 eager load queries

for treatment in treatments:  # 10 treatments
    patient_name = treatment.patient.name  # No extra query
    doctor_name = treatment.doctor.full_name  # No extra query
    med_count = len(treatment.medications)  # No extra query

# Total: 3 queries (80% reduction!)
```

---

## 🚀 Best Practices

### 1. Always Use Default (eager_load=True) for Read Operations
```python
# ✅ GOOD
appointments = appointment_repo.get_upcoming(practitioner_id=doctor_id)

# ❌ BAD (only if you really need to skip eager loading)
appointments = appointment_repo.get_upcoming(practitioner_id=doctor_id, eager_load=False)
```

### 2. Disable for Mutations and Bulk Operations
```python
# ✅ GOOD: Methods already have eager_load=False
notification_repo.mark_as_read(notification_id)
session_repo.revoke_all_user_sessions(user_id)
```

### 3. Use Appropriate Loading Strategy

**joinedload** for many-to-one/one-to-one:
```python
query = query.options(
    joinedload(Treatment.patient),  # Many-to-one
    joinedload(Treatment.doctor)     # Many-to-one
)
```

**selectinload** for one-to-many/many-to-many:
```python
query = query.options(
    selectinload(Treatment.medications),  # One-to-many
    selectinload(Patient.treatments)      # One-to-many
)
```

### 4. Monitor Query Performance
```python
# Enable SQL query logging in development
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Check query counts
treatments = treatment_repo.get_by_patient(patient_id)
# Should see exactly 3 queries in logs
```

---

## 🔍 Troubleshooting

### Issue: "DetachedInstanceError"
**Cause**: Accessing relationship after session closed
**Solution**: Use eager loading!

```python
# ❌ BAD: Session closed, relationships not loaded
treatment = treatment_repo.get_by_id(id, eager_load=False)
db.close()
print(treatment.patient.name)  # ERROR: DetachedInstanceError

# ✅ GOOD: Relationships loaded before session closes
treatment = treatment_repo.get_by_id(id, eager_load=True)
db.close()
print(treatment.patient.name)  # Works! Already loaded
```

### Issue: Too Many Queries in Logs
**Cause**: Forgot to use eager loading
**Solution**: Use default eager_load=True

```python
# ❌ BAD: N+1 queries
treatments = treatment_repo.get_by_patient(patient_id, eager_load=False)

# ✅ GOOD: 3 queries total
treatments = treatment_repo.get_by_patient(patient_id)  # Default eager_load=True
```

### Issue: Slow API Response
**Cause**: Not using eager loading
**Solution**: Always use eager loading for read operations

```python
# ❌ BAD: Slow due to N+1 queries
@router.get("/treatments")
async def get_treatments(patient_id: UUID, db: Session = Depends(get_db)):
    return db.query(Treatment).filter(Treatment.patient_id == patient_id).all()

# ✅ GOOD: Fast with eager loading
@router.get("/treatments")
async def get_treatments(patient_id: UUID, treatment_repo: TreatmentRepository = Depends()):
    return treatment_repo.get_by_patient(patient_id)  # Eager loading enabled
```

---

## 📖 Additional Resources

- **Full Implementation**: See `SPRINT_1_EAGER_LOADING_IMPLEMENTATION.md`
- **SQLAlchemy Docs**: [Eager Loading](https://docs.sqlalchemy.org/en/14/orm/loading_relationships.html)
- **Repository Pattern**: `app/repositories/base.py`

---

**Last Updated**: 2025-10-09
**Sprint**: Sprint 1 (P1-2)
