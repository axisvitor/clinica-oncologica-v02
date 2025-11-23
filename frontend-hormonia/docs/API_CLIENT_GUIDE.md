# Frontend API Client - Complete Usage Guide

**Version:** 2.1.0
**Last Updated:** January 2025
**Framework:** React 19 + TypeScript + Vite

---

## 📋 Table of Contents

1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Authentication](#authentication)
4. [Available Modules](#available-modules)
5. [Error Handling](#error-handling)
6. [TypeScript Types](#typescript-types)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

---

## 🎯 Introduction

The API Client is a comprehensive, type-safe HTTP client library that provides easy access to all backend endpoints. It handles:

- ✅ **Authentication** (Firebase + Session cookies)
- ✅ **CSRF Protection** (automatic token management)
- ✅ **Error Handling** (user-friendly messages)
- ✅ **Retry Logic** (automatic retry for transient failures)
- ✅ **Type Safety** (complete TypeScript interfaces)
- ✅ **Pagination** (built-in support)

---

## 🚀 Quick Start

### Installation

The API client is already included in the project. Simply import it:

```typescript
import { apiClient } from '@/lib/api-client'
```

### Basic Usage

```typescript
// List patients
const patients = await apiClient.patients.list({ status: 'active' })

// Get specific patient
const patient = await apiClient.patients.get('patient-id')

// Create new patient
const newPatient = await apiClient.patients.create({
  name: 'João Silva',
  phone: '+5511999999999',
  doctor_id: 'doctor-id'
})

// Update patient
await apiClient.patients.update('patient-id', { status: 'completed' })
```

---

## 🔐 Authentication

### Login Flow

```typescript
import { signInWithEmailAndPassword } from 'firebase/auth'
import { apiClient } from '@/lib/api-client'

// 1. Login with Firebase
const userCredential = await signInWithEmailAndPassword(
  auth,
  email,
  password
)

// 2. Get Firebase ID token
const idToken = await userCredential.user.getIdToken()

// 3. Create backend session
const sessionResponse = await apiClient.auth.createSession(idToken)

// 4. Session cookie is now set automatically
// All subsequent requests include the cookie
```

### Check Authentication

```typescript
// Check if user is authenticated
const { authenticated, user } = await apiClient.auth.checkAuth()

if (authenticated) {
  console.log('Logged in as:', user.full_name)
}
```

### Logout

```typescript
// Logout current session
await apiClient.auth.logout()

// Or invalidate all sessions
await apiClient.auth.invalidateAllSessions()
```

---

## 📦 Available Modules

### 1. Auth API

```typescript
// Session management
await apiClient.auth.createSession(firebaseToken)
await apiClient.auth.getSession()
await apiClient.auth.logout()
await apiClient.auth.invalidateAllSessions()

// User info
const user = await apiClient.auth.getCurrentUser()
const { authenticated, user } = await apiClient.auth.checkAuth()
```

### 2. Patients API

```typescript
// CRUD operations
const patients = await apiClient.patients.list({
  status: 'active',
  page: 1,
  size: 20
})

const patient = await apiClient.patients.get('patient-id')

const newPatient = await apiClient.patients.create({
  name: 'João Silva',
  phone: '+5511999999999',
  doctor_id: 'doctor-id'
})

await apiClient.patients.update('patient-id', { status: 'completed' })
await apiClient.patients.delete('patient-id')

// Search
const results = await apiClient.patients.search('João')

// Additional data
const timeline = await apiClient.patients.getTimeline('patient-id')
const stats = await apiClient.patients.getStatistics('patient-id')
const history = await apiClient.patients.getMedicalHistory('patient-id')
const docs = await apiClient.patients.getDocuments('patient-id')
const appointments = await apiClient.patients.getAppointments('patient-id')
```

### 3. Appointments API ✨ NEW

```typescript
// List appointments
const appointments = await apiClient.appointments.list({
  patient_id: 'patient-id',
  status: 'scheduled',
  page: 1,
  size: 20
})

// Create appointment
const appointment = await apiClient.appointments.create({
  patient_id: 'patient-id',
  practitioner_id: 'doctor-id',
  appointment_type: 'consultation',
  scheduled_at: '2025-02-01T10:00:00Z',
  duration_minutes: 60
})

// Check for conflicts
const conflicts = await apiClient.appointments.checkConflicts(
  'doctor-id',
  '2025-02-01T10:00:00Z',
  60
)

// Update status
await apiClient.appointments.cancel('appointment-id', 'Patient request')
await apiClient.appointments.complete('appointment-id', 'All good')

// Query by filters
const patientAppts = await apiClient.appointments.getByPatient('patient-id')
const doctorAppts = await apiClient.appointments.getByPractitioner('doctor-id')
const rangeAppts = await apiClient.appointments.getByDateRange(
  '2025-02-01',
  '2025-02-28'
)
```

**RBAC Requirements:**
- `list()`, `get()`, `getByPatient()`: `view_appointments`
- `create()`: `create_appointment`
- `update()`, `cancel()`, `complete()`: `edit_appointment`
- `delete()`: `delete_appointment`

### 4. Treatments API ✨ NEW

```typescript
// List treatments
const treatments = await apiClient.treatments.list({
  patient_id: 'patient-id',
  status: 'active',
  treatment_type: 'quimioterapia',
  page: 1,
  size: 20
})

// Create treatment
const treatment = await apiClient.treatments.create({
  patient_id: 'patient-id',
  doctor_id: 'doctor-id',
  treatment_type: 'quimioterapia',
  start_date: '2025-01-01',
  planned_sessions: '12',
  protocol: 'Protocol XYZ'
})

// Update treatment
await apiClient.treatments.update('treatment-id', {
  completed_sessions: '3',
  notes: 'Patient responding well'
})

// Status management
await apiClient.treatments.activate('treatment-id')
await apiClient.treatments.complete('treatment-id')
await apiClient.treatments.suspend('treatment-id', 'Side effects')

// Statistics
const stats = await apiClient.treatments.getStatistics({
  treatment_type: 'quimioterapia'
})

// Query by patient
const patientTreatments = await apiClient.treatments.getByPatient('patient-id')
const activeTreatments = await apiClient.treatments.getActiveByPatient('patient-id')
```

**RBAC Requirements:**
- `list()`, `get()`, `getByPatient()`: `view_treatments`
- `create()`: `create_treatment`
- `update()`, `activate()`, `suspend()`, `complete()`: `edit_treatment`
- `delete()`: `delete_treatment`
- `getStatistics()`: `view_analytics`

### 5. Monthly Quiz API

```typescript
// Templates
const templates = await apiClient.monthlyQuiz.getTemplates()
const template = await apiClient.monthlyQuiz.getTemplate('template-id')

// Sessions
const session = await apiClient.monthlyQuiz.startSession(
  'patient-id',
  'template-id'
)

await apiClient.monthlyQuiz.submitAnswer(
  'session-id',
  'question-id',
  { answer: 'Sim' }
)

const sessionData = await apiClient.monthlyQuiz.getSession('session-id')

// Responses
const responses = await apiClient.monthlyQuiz.getPatientResponses('patient-id')
const analysis = await apiClient.monthlyQuiz.getSessionAnalysis('session-id')
```

### 6. Analytics API

```typescript
// Overview
const overview = await apiClient.analytics.getOverview({
  startDate: '2025-01-01',
  endDate: '2025-01-31'
})

// Patient analytics
const patientAnalytics = await apiClient.analytics.getPatientAnalytics('patient-id')

// Metrics
const treatmentAnalytics = await apiClient.analytics.getTreatmentAnalytics()
const adherence = await apiClient.analytics.getAdherenceMetrics()
const risk = await apiClient.analytics.getRiskAssessment('patient-id')

// Export
const csvBlob = await apiClient.analytics.exportAnalytics('csv')
const pdfBlob = await apiClient.analytics.exportAnalytics('pdf')
```

### 7. Dashboard API

```typescript
// General stats
const stats = await apiClient.dashboard.getStats()
const activity = await apiClient.dashboard.getRecentActivity()
const alerts = await apiClient.dashboard.getAlerts()

// Physician-specific
const physicianStats = await apiClient.dashboard.getPhysicianStats('doctor-id')
const physicianPatients = await apiClient.dashboard.getPhysicianPatients('doctor-id')
```

### 8. Admin API

```typescript
// User management
const users = await apiClient.admin.users.list({ role: 'doctor' })
const user = await apiClient.admin.users.get('user-id')

await apiClient.admin.users.create({
  email: 'doctor@example.com',
  full_name: 'Dr. João Silva',
  role: 'doctor'
})

await apiClient.admin.users.update('user-id', { is_active: false })
await apiClient.admin.users.delete('user-id')

// System management
const health = await apiClient.admin.system.getHealth()
const metrics = await apiClient.admin.system.getMetrics()
await apiClient.admin.system.clearCache()

// Audit logs
const logs = await apiClient.admin.audit.list({
  startDate: '2025-01-01',
  endDate: '2025-01-31'
})

const auditCsv = await apiClient.admin.audit.export('csv')
```

### 9. Messages API

```typescript
// List messages
const messages = await apiClient.messages.list({
  status: 'sent',
  page: 1,
  size: 20
})

// Send message
const message = await apiClient.messages.send({
  patient_id: 'patient-id',
  content: 'Olá! Como você está?',
  type: 'text'
})

// Bulk send
const bulkResult = await apiClient.messages.sendBulk({
  patient_ids: ['id1', 'id2', 'id3'],
  content: 'Lembrete de consulta'
})

// Conversation
const conversation = await apiClient.messages.getConversation('patient-id')

// Mark as read
await apiClient.messages.markAsRead('message-id')

// Retry failed message
await apiClient.messages.retry('message-id')
```

### 10. Flows API

```typescript
// List flows
const flows = await apiClient.flows.list()
const flow = await apiClient.flows.get('flow-id')

// Create/update (admin only)
const newFlow = await apiClient.flows.create({
  name: 'Onboarding Flow',
  description: 'Patient onboarding automation',
  is_active: true
})

await apiClient.flows.update('flow-id', { is_active: false })

// Execute flow
const execution = await apiClient.flows.execute('flow-id', 'patient-id')

// Analytics
const analytics = await apiClient.flows.getAnalytics('flow-id')
const executions = await apiClient.flows.getExecutions('flow-id')

// Activate/deactivate
await apiClient.flows.activate('flow-id')
await apiClient.flows.deactivate('flow-id')
```

---

## 🚨 Error Handling

### ApiError Class

All API errors are instances of `ApiError`:

```typescript
class ApiError extends Error {
  status: number              // HTTP status code
  data: unknown              // Error details from backend
  userFriendlyMessage: string // Translated user message
  retryable: boolean         // Can this error be retried?
  timestamp: string          // ISO timestamp
}
```

### Handling Errors

```typescript
try {
  const patient = await apiClient.patients.get('invalid-id')
} catch (error) {
  if (error instanceof ApiError) {
    // Show user-friendly message
    toast.error(error.userFriendlyMessage)

    // Handle specific status codes
    switch (error.status) {
      case 401:
        // Unauthorized - redirect to login
        navigate('/login')
        break
      case 403:
        // Forbidden - show access denied message
        toast.error('Você não tem permissão para esta ação')
        break
      case 404:
        // Not found
        toast.error('Recurso não encontrado')
        break
      case 429:
        // Rate limited - show retry message
        toast.warning('Muitas tentativas. Aguarde alguns minutos.')
        break
      case 500:
        // Server error
        toast.error('Erro no servidor. Tente novamente mais tarde.')
        break
    }

    // Check if retryable
    if (error.retryable) {
      console.log('This error can be retried automatically')
    }
  }
}
```

### User-Friendly Error Messages

The client automatically provides localized Portuguese error messages:

```typescript
// Network error (status 0)
"Não foi possível conectar ao servidor. Verifique sua conexão."

// Unauthorized (401)
"Sua sessão expirou. Por favor, faça login novamente."

// Forbidden (403)
"Você não tem permissão para realizar esta ação."

// Not Found (404)
"O recurso solicitado não foi encontrado."

// Rate Limited (429)
"Muitas tentativas. Aguarde alguns minutos e tente novamente."

// Server Error (500)
"Erro interno do servidor. Nossa equipe foi notificada."
```

---

## 📘 TypeScript Types

All API methods are fully typed. Import types as needed:

```typescript
import type {
  Patient,
  PatientCreate,
  PatientUpdate,
  Appointment,
  AppointmentCreate,
  Treatment,
  TreatmentCreate,
  QuizSession,
  User
} from '@/lib/api-client/types'

// Use types in your components
const handleCreatePatient = async (data: PatientCreate) => {
  const patient: Patient = await apiClient.patients.create(data)
  return patient
}
```

### Common Types

```typescript
// Pagination
interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

// Filters
interface PatientFilters {
  search?: string
  status?: string
  doctor_id?: string
  treatment_type?: string
}

interface AppointmentFilters {
  search?: string
  patient_id?: string
  practitioner_id?: string
  status?: AppointmentStatus
  appointment_type?: AppointmentType
  date_from?: string
  date_to?: string
}

interface TreatmentFilters {
  search?: string
  patient_id?: string
  doctor_id?: string
  status?: TreatmentStatus
  treatment_type?: TreatmentType
}
```

---

## ✅ Best Practices

### 1. Use React Hooks

Create custom hooks for API calls:

```typescript
// hooks/usePatients.ts
export function usePatients(filters?: PatientFilters) {
  const [data, setData] = useState<Patient[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    const fetchPatients = async () => {
      try {
        setLoading(true)
        const response = await apiClient.patients.list(filters)
        setData(response.items)
      } catch (err) {
        setError(err as ApiError)
      } finally {
        setLoading(false)
      }
    }

    fetchPatients()
  }, [JSON.stringify(filters)])

  return { data, loading, error }
}

// Usage in component
const { data: patients, loading, error } = usePatients({ status: 'active' })
```

### 2. Handle Loading States

```typescript
const [loading, setLoading] = useState(false)

const handleSubmit = async () => {
  setLoading(true)
  try {
    await apiClient.patients.create(formData)
    toast.success('Paciente criado com sucesso!')
  } catch (error) {
    if (error instanceof ApiError) {
      toast.error(error.userFriendlyMessage)
    }
  } finally {
    setLoading(false)
  }
}
```

### 3. Optimize with React Query

```typescript
import { useQuery, useMutation } from '@tanstack/react-query'

// Query
const { data: patients } = useQuery({
  queryKey: ['patients', filters],
  queryFn: () => apiClient.patients.list(filters)
})

// Mutation
const createPatient = useMutation({
  mutationFn: (data: PatientCreate) => apiClient.patients.create(data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['patients'] })
    toast.success('Paciente criado!')
  }
})
```

### 4. Implement Optimistic Updates

```typescript
const updatePatientStatus = useMutation({
  mutationFn: ({ id, status }: { id: string; status: string }) =>
    apiClient.patients.update(id, { status }),
  onMutate: async ({ id, status }) => {
    // Cancel outgoing refetches
    await queryClient.cancelQueries({ queryKey: ['patients'] })

    // Snapshot previous value
    const previous = queryClient.getQueryData(['patients'])

    // Optimistically update
    queryClient.setQueryData(['patients'], (old: any) => ({
      ...old,
      items: old.items.map((p: Patient) =>
        p.id === id ? { ...p, status } : p
      )
    }))

    return { previous }
  },
  onError: (err, variables, context) => {
    // Rollback on error
    queryClient.setQueryData(['patients'], context?.previous)
  }
})
```

### 5. Type Your API Responses

```typescript
// Define expected response structure
interface PatientWithStats extends Patient {
  stats: {
    total_appointments: number
    completed_treatments: number
  }
}

// Use in API call
const patient = await apiClient.patients.get('id') as PatientWithStats
```

---

## 📚 Examples

### Example 1: Patient Management Dashboard

```typescript
function PatientDashboard() {
  const [filters, setFilters] = useState<PatientFilters>({ status: 'active' })
  const { data: patients, loading, error } = usePatients(filters)

  if (loading) return <Spinner />
  if (error) return <ErrorMessage error={error} />

  return (
    <div>
      <FilterBar filters={filters} onChange={setFilters} />
      <PatientList patients={patients} />
    </div>
  )
}
```

### Example 2: Appointment Scheduler

```typescript
function AppointmentScheduler() {
  const createAppointment = async (data: AppointmentCreate) => {
    try {
      // Check for conflicts first
      const conflicts = await apiClient.appointments.checkConflicts(
        data.practitioner_id!,
        data.scheduled_at,
        data.duration_minutes || 60
      )

      if (conflicts.has_conflicts) {
        toast.warning('Conflito detectado com outro agendamento')
        return
      }

      // Create appointment
      const appointment = await apiClient.appointments.create(data)
      toast.success('Agendamento criado com sucesso!')
      return appointment
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.userFriendlyMessage)
      }
    }
  }

  return <AppointmentForm onSubmit={createAppointment} />
}
```

### Example 3: Treatment Tracker

```typescript
function TreatmentTracker({ patientId }: { patientId: string }) {
  const [treatments, setTreatments] = useState<Treatment[]>([])

  useEffect(() => {
    const loadTreatments = async () => {
      const data = await apiClient.treatments.getByPatient(patientId)
      setTreatments(data)
    }
    loadTreatments()
  }, [patientId])

  const handleComplete = async (treatmentId: string) => {
    try {
      await apiClient.treatments.complete(treatmentId)
      toast.success('Tratamento concluído!')
      // Reload treatments
      const updated = await apiClient.treatments.getByPatient(patientId)
      setTreatments(updated)
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.userFriendlyMessage)
      }
    }
  }

  return (
    <TreatmentList
      treatments={treatments}
      onComplete={handleComplete}
    />
  )
}
```

---

## 🔧 Troubleshooting

### Issue: "Network Error" (Status 0)

**Cause:** Cannot connect to backend server

**Solutions:**
1. Check if backend is running
2. Verify API URL in environment variables
3. Check CORS configuration
4. Test network connectivity

### Issue: "CSRF Token Missing"

**Cause:** CSRF protection blocking request

**Solutions:**
1. Ensure CSRF token is fetched on app init
2. Check cookies are enabled
3. Verify `withCredentials: true` in requests

### Issue: "Session Expired" (401)

**Cause:** Authentication session invalid

**Solutions:**
1. Redirect user to login page
2. Implement automatic token refresh
3. Handle session expiry gracefully

### Issue: "Rate Limited" (429)

**Cause:** Too many requests

**Solutions:**
1. Implement request debouncing
2. Add loading states to prevent duplicate requests
3. Show retry countdown to user

---

## 📞 Support

For issues or questions:

1. Check this documentation
2. Review TypeScript types in `/src/lib/api-client/types.ts`
3. Check backend API documentation
4. Contact development team

---

**Version:** 2.1.0
**Last Updated:** January 2025
**Maintained by:** Frontend Development Team
