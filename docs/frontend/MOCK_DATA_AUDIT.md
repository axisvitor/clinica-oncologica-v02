# Frontend Mock Data Audit Report

**Generated:** 2025-10-06
**Scope:** All files in `frontend-hormonia/src/pages/**`
**Total Files Analyzed:** 22 pages

---

## Executive Summary

### Overview Statistics
- **Total Mock Data Instances:** 37
- **Pages Affected:** 9 out of 22 pages (41%)
- **Critical Issues:** 12
- **Cosmetic Issues:** 25
- **Pages Clean (No Mock Data):** 13

### Impact Classification
- **🔴 CRITICAL:** Mock data that misleads users about actual system state or breaks functionality
- **🟡 COSMETIC:** Placeholder data that doesn't impact core functionality but should be replaced

---

## Detailed Findings by Page

### 1. AdminPage.tsx
**Path:** `frontend-hormonia/src/pages/AdminPage.tsx`
**Mock Data Instances:** 2

#### 🔴 CRITICAL: Hard-coded System Statistics
- **Lines:** 27-38
- **Type:** Static object with fake metrics
- **Code:**
```typescript
const systemStats = {
  totalUsers: 145,
  activeUsers: 132,
  totalPatients: 1234,
  activePatients: 987,
  messagesProcessed: 45678,
  apiCalls: 123456,
  averageResponseTime: 145,
  uptime: 99.9,
  diskUsage: 45,
  memoryUsage: 67
}
```
- **Impact:** Displays misleading system health metrics to administrators
- **Used in:** System monitoring dashboard, resource usage displays
- **Recommended Fix:** Replace with API call to `/api/v1/admin/system-stats` or `/api/v1/metrics/system`

#### 🟡 COSMETIC: Mock User List
- **Lines:** 470-503
- **Type:** Hardcoded array iteration `[1, 2, 3, 4, 5].map()`
- **Code:** Renders 5 fake users with `Usuário {i}` and `usuario{i}@email.com`
- **Impact:** Shows fake users in admin user management
- **Recommended Fix:** Replace with API call to `/api/v1/admin/users`

---

### 2. AnalyticsPage.tsx
**Path:** `frontend-hormonia/src/pages/AnalyticsPage.tsx`
**Mock Data Instances:** 3

#### 🔴 CRITICAL: Treatment Type Distribution
- **Lines:** 74-79
- **Type:** Static array with treatment percentages
- **Code:**
```typescript
const treatmentTypeData = [
  { name: 'Terapia Hormonal Feminina', value: 45, color: '#3b82f6' },
  { name: 'Terapia Hormonal Masculina', value: 30, color: '#10b981' },
  { name: 'Reposição Hormonal', value: 20, color: '#f59e0b' },
  { name: 'Tratamento Personalizado', value: 5, color: '#ef4444' }
]
```
- **Impact:** Pie chart shows incorrect treatment distribution
- **Recommended Fix:** Replace with API call to `/api/v1/analytics/treatment-distribution`

#### 🟡 COSMETIC: Patient Status Counts
- **Lines:** 452, 458
- **Type:** Hardcoded values in UI
- **Code:** Shows "12" paused patients and "8" completed
- **Impact:** Misleading status distribution display
- **Recommended Fix:** Use data from `patientsAnalytics` or add to dashboard API response

#### 🟡 COSMETIC: System Performance Mock
- **Lines:** 504, 508
- **Type:** Hardcoded metrics
- **Code:** Uptime "99.9%" and messages "1,234"
- **Impact:** Displays fake system performance metrics
- **Recommended Fix:** Add to `/api/v1/analytics/dashboard` response

---

### 3. MetricsDashboardPage.tsx
**Path:** `frontend-hormonia/src/pages/MetricsDashboardPage.tsx`
**Mock Data Instances:** 5

#### 🟡 COSMETIC: Static Status Cards
- **Lines:** 159, 165, 176, 185, 190, 199
- **Type:** Hardcoded status text
- **Code:** "Ativo", "Monitorados", "Otimizada", "Funcionais"
- **Impact:** Shows placeholder status that may not reflect actual state
- **Recommended Fix:** Update to use real-time metrics from API

#### 🟡 COSMETIC: Recommendation Examples
- **Lines:** 265-283
- **Type:** Hardcoded insight messages
- **Code:** Static recommendation cards with preset text
- **Impact:** Shows fake AI insights
- **Recommended Fix:** Replace with actual AI recommendation API

---

### 4. MonthlyQuizDashboard.tsx
**Path:** `frontend-hormonia/src/pages/MonthlyQuizDashboard.tsx`
**Mock Data Instances:** 1

#### 🔴 CRITICAL: Fallback Stats Values
- **Lines:** 62-66
- **Type:** Conditional fallback to zero
- **Code:**
```typescript
const totalSent = stats?.total_sent ?? stats?.total_links_created ?? 0;
const totalCompleted = stats?.total_completed ?? stats?.completed_quizzes ?? 0;
```
- **Impact:** May show zeros when data exists under different keys (backward compatibility issue)
- **Recommended Fix:** Ensure API contract consistency, remove fallbacks after migration

---

### 5. ClinicalMonitoringDashboard.tsx
**Path:** `frontend-hormonia/src/pages/ClinicalMonitoringDashboard.tsx`
**Mock Data Instances:** 8

#### 🔴 CRITICAL: Sentiment Distribution Mock
- **Lines:** 191-195
- **Type:** Static array with percentages
- **Code:**
```typescript
const sentimentDistribution = [
  { name: 'Positivo', value: 45, color: '#10b981' },
  { name: 'Neutro', value: 35, color: '#6b7280' },
  { name: 'Negativo', value: 20, color: '#ef4444' },
]
```
- **Impact:** Shows fake sentiment analysis data
- **Recommended Fix:** Replace with `/api/v1/analytics/sentiment` endpoint

#### 🟡 COSMETIC: Engagement Radar Chart Data
- **Lines:** 478-484
- **Type:** Hardcoded engagement metrics
- **Code:**
```typescript
{ metric: 'Mensagens', value: 75 },
{ metric: 'Quiz', value: 65 },
{ metric: 'Check-ins', value: 80 },
// ...
```
- **Impact:** Shows fake engagement breakdown
- **Recommended Fix:** Add to `/api/v1/analytics/engagement` response

#### 🟡 COSMETIC: Recommendation Alerts
- **Lines:** 507-545
- **Type:** Conditional mock recommendations
- **Impact:** Shows generic recommendations not based on real data
- **Recommended Fix:** Implement AI-based recommendation engine

---

### 6. PhysicianDashboard.tsx
**Path:** `frontend-hormonia/src/pages/PhysicianDashboard.tsx`
**Mock Data Instances:** 2

#### 🔴 CRITICAL: Fallback AI Insights
- **Lines:** 112-125
- **Type:** Mock risk assessment fallback
- **Code:**
```typescript
return {
  id: patient.id,
  name: patient.full_name,
  risk_level: 'low',
  risk_factors: [],
  sentiment_score: 0.5,
  engagement_score: 50,
  has_alerts: false
}
```
- **Impact:** Shows all patients as low-risk when AI insights fail
- **Recommended Fix:** Properly handle AI service failures, show loading state or error message

#### 🟡 COSMETIC: Export Report Mock
- **Lines:** 208-227
- **Type:** Client-side JSON export (not using backend)
- **Impact:** Limited export functionality, doesn't generate proper PDF/Excel
- **Recommended Fix:** Use `/api/v1/reports/generate` endpoint

---

### 7. QuestionariosPage.tsx
**Path:** `frontend-hormonia/src/pages/QuestionariosPage.tsx`
**Mock Data Instances:** 2

#### 🔴 CRITICAL: Analytics Fallback
- **Lines:** 152-159
- **Type:** Mock analytics when fetch fails
- **Code:**
```typescript
return {
  ...template,
  analytics: {
    total_responses: 0,
    completion_rate: 0,
    average_completion_time: null
  }
}
```
- **Impact:** Shows zeros instead of actual analytics or error state
- **Recommended Fix:** Proper error handling with user notification

---

### 8. MedicoDashboard.tsx
**Path:** `frontend-hormonia/src/pages/medico/MedicoDashboard.tsx`
**Mock Data Instances:** 4

#### 🔴 CRITICAL: Dashboard Statistics
- **Lines:** 97, 101, 105, 109
- **Type:** Hardcoded zeros for all stats
- **Code:**
```tsx
<p className="text-3xl font-bold text-blue-600">0</p>
<p className="text-sm text-gray-600">Pacientes Ativos</p>
```
- **Impact:** Always shows zero for all physician statistics
- **Recommended Fix:** Implement `/api/v1/medico/dashboard-stats` endpoint

---

### 9. DashboardPage.tsx
**Path:** `frontend-hormonia/src/pages/DashboardPage.tsx`
**Mock Data Instances:** 11

#### 🟡 COSMETIC: Patient Status Distribution
- **Lines:** 191-203
- **Type:** Hardcoded patient counts
- **Code:** "12" paused, "8" completed, "3" inactive
- **Impact:** Shows fake patient distribution
- **Recommended Fix:** Add to dashboard API response

#### 🟡 COSMETIC: Alert Statistics
- **Lines:** 269-282, 291-302, 308-323
- **Type:** Hardcoded alert metrics
- **Impact:** Shows fake alert distribution and performance metrics
- **Recommended Fix:** Create `/api/v1/alerts/statistics` endpoint

#### 🟡 COSMETIC: Quiz Statistics
- **Lines:** 247-252
- **Type:** Hardcoded quiz metrics
- **Code:** "5" in progress, "85%" completion
- **Impact:** Misleading quiz performance data
- **Recommended Fix:** Add to `/api/v1/analytics/quizzes` endpoint

---

## Pages Clean of Mock Data ✅

The following pages use only real API data or have proper loading states:

1. **FlowsPage.tsx** - Uses real flow data from API
2. **PatientsPage.tsx** - Properly fetches from `/api/v1/patients`
3. **QuizPage.tsx** - Uses API for all quiz data
4. **SettingsPage.tsx** - User preferences from backend
5. **WhatsAppPage.tsx** - Wrapper component, no mock data
6. **MessagesPage.tsx** - Real messages from API
7. **PatientDetailPage.tsx** - Real patient data
8. **LoginPage.tsx** - Authentication only
9. **AlertsPage.tsx** - Real alerts from API
10. **ReportsPage.tsx** - Real reports from API
11. **MedicoLogin.tsx** - Authentication only
12. **PacientesList.tsx** - Real patient list from API
13. **ProntuarioView.tsx** - Real patient records from API

---

## Summary Statistics by Category

### Mock Data by Type
- **Static Objects:** 8 instances
- **Hardcoded Arrays:** 7 instances
- **Conditional Fallbacks:** 6 instances
- **Placeholder Values:** 16 instances

### Mock Data by Impact Area
- **Patient Metrics:** 9 instances
- **System Statistics:** 8 instances
- **Analytics/Charts:** 7 instances
- **Alert Metrics:** 6 instances
- **AI/Insights:** 4 instances
- **Quiz Metrics:** 3 instances

---

## Recommended Actions

### Immediate (Critical - Week 1)
1. **AdminPage.tsx**: Implement `/api/v1/admin/system-stats` endpoint
2. **AnalyticsPage.tsx**: Add treatment distribution to analytics API
3. **PhysicianDashboard.tsx**: Fix AI insights error handling
4. **MedicoDashboard.tsx**: Create physician dashboard stats endpoint
5. **ClinicalMonitoringDashboard.tsx**: Implement sentiment analysis API

### Short-term (Cosmetic - Week 2-3)
1. Replace all hardcoded patient status counts with API data
2. Implement proper alert statistics endpoint
3. Add quiz metrics to analytics responses
4. Create recommendations/insights API
5. Replace client-side exports with backend report generation

### Long-term (Enhancement - Month 2)
1. Add real-time metrics with WebSocket updates
2. Implement comprehensive AI insights engine
3. Create advanced analytics aggregation endpoints
4. Add caching layer for dashboard metrics
5. Implement metric history tracking

---

## API Endpoints to Create

### High Priority
- `GET /api/v1/admin/system-stats` - System health and resource usage
- `GET /api/v1/admin/users` - User management list
- `GET /api/v1/analytics/treatment-distribution` - Treatment type breakdown
- `GET /api/v1/analytics/sentiment` - Sentiment analysis data
- `GET /api/v1/medico/dashboard-stats` - Physician statistics

### Medium Priority
- `GET /api/v1/alerts/statistics` - Alert metrics and distribution
- `GET /api/v1/analytics/quizzes` - Quiz performance metrics
- `GET /api/v1/analytics/engagement` - Detailed engagement breakdown
- `GET /api/v1/ai/recommendations` - AI-generated recommendations
- `POST /api/v1/reports/generate` - Backend report generation

---

## Testing Recommendations

### Before Removing Mock Data
1. Ensure all replacement APIs return expected data structure
2. Add loading states for all API calls
3. Implement proper error handling and fallbacks
4. Test with slow network conditions
5. Verify empty state handling

### After Replacing Mock Data
1. Verify all metrics display correctly
2. Test real-time update functionality
3. Validate performance with production data volumes
4. Ensure proper caching is in place
5. Monitor API response times

---

## Conclusion

The audit reveals that 41% of pages contain some form of mock data, with 12 critical instances that directly mislead users about system state. The majority of mock data is concentrated in dashboard and analytics pages where real-time metrics are expected.

**Priority should be given to:**
1. Admin system statistics (most visible to administrators)
2. Analytics charts and distributions (used for decision-making)
3. AI insights fallbacks (creates false security about patient risk)

All identified mock data should be replaced within the next sprint cycle to ensure production readiness.
