# Code Quality Analysis Report

**Project**: Clínica Oncológica - Frontend Hormonia
**Analysis Date**: 2025-10-06
**Scope**: Critical files from React Query audit
**Analyzed Files**: 4 high-priority components

---

## Executive Summary

This report analyzes code quality for the four most critical files identified in the React Query audit. The analysis focuses on maintainability, performance, security, readability, and adherence to best practices.

### Overall Quality Scores

| File | Quality Score | Critical Issues | High Issues | Medium Issues | Lines of Code |
|------|--------------|-----------------|-------------|---------------|---------------|
| ClinicalMonitoringDashboard.tsx | 6.5/10 | 2 | 3 | 4 | 553 |
| QuestionariosPage.tsx | 7/10 | 1 | 2 | 3 | 941 |
| ReportsPage.tsx | 7.5/10 | 1 | 1 | 2 | 290 |
| AlertsPage.tsx | 8/10 | 0 | 1 | 2 | 533 |

**Total Technical Debt Estimate**: 18-24 hours

---

## 1. ClinicalMonitoringDashboard.tsx

**Quality Score**: 6.5/10
**Lines of Code**: 553
**Complexity**: High
**Technical Debt**: 8-10 hours

### Critical Issues

#### 1.1 Manual Data Fetching Instead of React Query
- **Lines**: 139-177
- **Severity**: Critical
- **Category**: Architecture / Best Practices

**Problem**:
```typescript
const fetchClinicalMetrics = async () => {
  try {
    setLoading(true);
    const response = await apiClient.get<ApiResponse<ClinicalMetrics>>('/api/v1/metrics/clinical', {
      params: { timeRange: selectedTimeRange }
    });
    setMetrics(response['data']);
  } catch (error) {
    logger.error('Error fetching clinical metrics', { error, timeRange: selectedTimeRange });
  } finally {
    setLoading(false);
  }
};
```

**Issues**:
- Manual loading state management
- Manual error handling
- No automatic retry logic
- No caching
- No request deduplication
- Array bracket notation `response['data']` instead of dot notation

**Technical Debt**: 2-3 hours

**Recommended Fix**:
```typescript
const { data: metrics, isLoading, error, refetch } = useQuery({
  queryKey: ['clinical-metrics', selectedTimeRange],
  queryFn: async () => {
    const response = await apiClient.get<ApiResponse<ClinicalMetrics>>(
      '/api/v1/metrics/clinical',
      { params: { timeRange: selectedTimeRange } }
    );
    return response.data;
  },
  staleTime: 30000, // 30 seconds
  retry: 3
});
```

#### 1.2 Multiple Separate API Calls Without Coordination
- **Lines**: 123-127
- **Severity**: Critical
- **Category**: Performance

**Problem**:
```typescript
useEffect(() => {
  fetchClinicalMetrics();
  fetchRiskPatients();
  fetchAdherenceData();
}, [selectedTimeRange]);
```

**Issues**:
- Three separate API calls triggered simultaneously
- No coordination or loading state management
- No error boundary if one fails
- Waterfalls possible if backend is slow
- Duplicate loading logic across three functions

**Technical Debt**: 2-3 hours

**Recommended Fix**:
```typescript
const { data: dashboardData, isLoading, error } = useQuery({
  queryKey: ['clinical-dashboard', selectedTimeRange],
  queryFn: async () => {
    const [metrics, riskPatients, adherenceData] = await Promise.all([
      apiClient.get('/api/v1/metrics/clinical', { params: { timeRange: selectedTimeRange }}),
      apiClient.get('/api/v1/patients/at-risk'),
      apiClient.get('/api/v1/analytics/adherence', { params: { days: parseInt(selectedTimeRange) }})
    ]);

    return {
      metrics: metrics.data,
      riskPatients: riskPatients.data,
      adherenceData: adherenceData.data
    };
  },
  staleTime: 30000,
  retry: 3
});
```

### High Severity Issues

#### 1.3 Hardcoded Mock Data
- **Lines**: 190-201, 478-485
- **Severity**: High
- **Category**: Code Smell

**Problem**:
```typescript
const sentimentDistribution = [
  { name: 'Positivo', value: 45, color: '#10b981' },
  { name: 'Neutro', value: 35, color: '#6b7280' },
  { name: 'Negativo', value: 20, color: '#ef4444' },
];
```

**Issues**:
- Hardcoded values not from API
- Inconsistent with real-time data pattern
- Misleading to end users
- Could cause confusion in production

**Technical Debt**: 1-2 hours

**Recommended Fix**:
```typescript
// Should come from API or be calculated from real data
const sentimentDistribution = useMemo(() => {
  const total = riskPatients.length;
  if (total === 0) return [];

  const positive = riskPatients.filter(p => p.sentiment > 0.3).length;
  const negative = riskPatients.filter(p => p.sentiment < -0.3).length;
  const neutral = total - positive - negative;

  return [
    { name: 'Positivo', value: (positive / total) * 100, color: '#10b981' },
    { name: 'Neutro', value: (neutral / total) * 100, color: '#6b7280' },
    { name: 'Negativo', value: (negative / total) * 100, color: '#ef4444' },
  ];
}, [riskPatients]);
```

#### 1.4 Magic Numbers and Hardcoded Values
- **Lines**: 229-232, 255, 269
- **Severity**: High
- **Category**: Maintainability

**Problem**:
```typescript
<option value="7">Últimos 7 dias</option>
<option value="30">Últimos 30 dias</option>
<option value="90">Últimos 90 dias</option>

Meta: 60% • {metrics.patientEngagement >= 0.6 ? '✅ Atingida' : '⚠️ Abaixo'}
Meta: 70% • {metrics.quizCompletion >= 0.7 ? '✅ Atingida' : '⚠️ Melhorar'}
```

**Issues**:
- Hardcoded thresholds (0.6, 0.7)
- Hardcoded time ranges
- No central configuration
- Difficult to adjust business rules

**Technical Debt**: 1 hour

**Recommended Fix**:
```typescript
// config/clinical-thresholds.ts
export const CLINICAL_THRESHOLDS = {
  patientEngagement: 0.6,
  quizCompletion: 0.7,
  averageSentiment: 0.3,
  maxRiskPatients: 5
} as const;

export const TIME_RANGES = [
  { value: '7', label: 'Últimos 7 dias' },
  { value: '30', label: 'Últimos 30 dias' },
  { value: '90', label: 'Últimos 90 dias' }
] as const;

// In component:
import { CLINICAL_THRESHOLDS, TIME_RANGES } from '@/config/clinical-thresholds';

metrics.patientEngagement >= CLINICAL_THRESHOLDS.patientEngagement
```

#### 1.5 WebSocket Type Safety Issues
- **Lines**: 68-75, 131-137
- **Severity**: High
- **Category**: Type Safety

**Problem**:
```typescript
interface ClinicalWebSocketMessage {
  type: 'metrics_update' | 'risk_alert';
  data: {
    metrics?: ClinicalMetrics;
    alert?: any; // ❌ any type
  };
  timestamp: string;
}

useEffect(() => {
  if (wsData?.type === 'metrics_update' && wsData.data?.metrics) {
    setMetrics(wsData.data.metrics as ClinicalMetrics); // ❌ type assertion
  }
  if (wsData?.type === 'risk_alert') {
    fetchRiskPatients(); // ❌ no validation
  }
}, [wsData]);
```

**Issues**:
- `any` type used
- Type assertions without validation
- No runtime type checking
- Could crash on malformed WebSocket data

**Technical Debt**: 2 hours

**Recommended Fix**:
```typescript
import { z } from 'zod';

const ClinicalMetricsSchema = z.object({
  patientEngagement: z.number(),
  quizCompletion: z.number(),
  messageResponseRate: z.number(),
  averageSentiment: z.number(),
  riskPatients: z.number(),
  totalPatients: z.number(),
  activeFlows: z.number(),
  completedFlows: z.number(),
});

const RiskAlertSchema = z.object({
  patientId: z.string(),
  severity: z.enum(['low', 'medium', 'high', 'critical']),
  message: z.string()
});

const WebSocketMessageSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('metrics_update'),
    data: z.object({ metrics: ClinicalMetricsSchema }),
    timestamp: z.string()
  }),
  z.object({
    type: z.literal('risk_alert'),
    data: z.object({ alert: RiskAlertSchema }),
    timestamp: z.string()
  })
]);

useEffect(() => {
  if (!wsData) return;

  try {
    const validated = WebSocketMessageSchema.parse(wsData);

    if (validated.type === 'metrics_update') {
      setMetrics(validated.data.metrics);
    } else if (validated.type === 'risk_alert') {
      fetchRiskPatients();
      toast({
        title: 'Alerta de Risco',
        description: validated.data.alert.message,
        variant: 'destructive'
      });
    }
  } catch (error) {
    logger.error('Invalid WebSocket message', { error, wsData });
  }
}, [wsData]);
```

### Medium Severity Issues

#### 1.6 Long Component (550+ lines)
- **Severity**: Medium
- **Category**: Maintainability

**Problem**: Component is 553 lines long, exceeding recommended 500 line limit.

**Recommended Fix**: Extract into sub-components:
- `ClinicalMetricsKPIs.tsx` (lines 245-316)
- `AdherenceTab.tsx` (lines 328-363)
- `SentimentTab.tsx` (lines 366-417)
- `RiskPatientsTab.tsx` (lines 420-465)
- `EngagementTab.tsx` (lines 468-494)
- `ClinicalRecommendations.tsx` (lines 498-548)

**Technical Debt**: 2-3 hours

#### 1.7 Duplicate Code in Risk Distribution Calculation
- **Lines**: 197-201
- **Severity**: Medium
- **Category**: DRY Principle

**Problem**:
```typescript
const riskDistribution = [
  { name: 'Baixo', value: riskPatients.filter(p => p.riskLevel === 'low').length },
  { name: 'Médio', value: riskPatients.filter(p => p.riskLevel === 'medium').length },
  { name: 'Alto', value: riskPatients.filter(p => p.riskLevel === 'high').length },
  { name: 'Crítico', value: riskPatients.filter(p => p.riskLevel === 'critical').length },
];
```

**Recommended Fix**:
```typescript
const riskDistribution = useMemo(() => {
  const levels = ['low', 'medium', 'high', 'critical'] as const;
  const labels = ['Baixo', 'Médio', 'Alto', 'Crítico'];

  return levels.map((level, index) => ({
    name: labels[index],
    value: riskPatients.filter(p => p.riskLevel === level).length,
    level
  }));
}, [riskPatients]);
```

#### 1.8 Inconsistent Error Handling
- **Lines**: 148-152, 162, 175
- **Severity**: Medium
- **Category**: Error Handling

**Problem**: Errors are logged but not displayed to user, creating silent failures.

**Recommended Fix**:
```typescript
const { data: metrics, error: metricsError } = useQuery({
  queryKey: ['clinical-metrics', selectedTimeRange],
  queryFn: async () => {
    // ... fetch logic
  },
  onError: (error) => {
    logger.error('Error fetching clinical metrics', { error });
    toast({
      title: 'Erro ao carregar métricas',
      description: 'Não foi possível carregar as métricas clínicas. Tente novamente.',
      variant: 'destructive'
    });
  }
});
```

#### 1.9 Missing Accessibility Attributes
- **Lines**: 224-232 (Select), multiple button elements
- **Severity**: Medium
- **Category**: Accessibility

**Problem**: Missing ARIA labels and keyboard navigation support.

**Recommended Fix**:
```typescript
<select
  aria-label="Selecionar intervalo de tempo"
  className="px-4 py-2 border rounded-lg"
  value={selectedTimeRange}
  onChange={(e) => setSelectedTimeRange(e.target.value)}
>
  <option value="7">Últimos 7 dias</option>
  <option value="30">Últimos 30 dias</option>
  <option value="90">Últimos 90 dias</option>
</select>
```

---

## 2. QuestionariosPage.tsx

**Quality Score**: 7/10
**Lines of Code**: 941
**Complexity**: Very High
**Technical Debt**: 6-8 hours

### Critical Issues

#### 2.1 Complete Client-Side Filtering
- **Lines**: 126-172
- **Severity**: Critical
- **Category**: Performance / Architecture

**Problem**:
```typescript
const { data: templatesData } = useQuery({
  queryKey: ['quiz-templates', currentPage, pageSize, filters],
  queryFn: async () => {
    const result = await apiClient.quizzes.listTemplates()
    // NO PARAMS sent to API! All filtering done client-side
  }
});

// Lines 257-314: Client-side filtering
const filteredTemplates = useMemo(() => {
  if (!templatesData?.data) return []

  let filtered = templatesData.data.filter((template: any) => {
    // Search filter
    if (filters.search && !template.name.toLowerCase().includes(filters.search.toLowerCase())) {
      return false
    }
    // Type filter
    if (filters.type !== 'all') {
      const templateType = template.name.toLowerCase().includes('medical') ||
                         template.name.toLowerCase().includes('oncolog') ? 'medical' : 'wellness'
      if (templateType !== filters.type) {
        return false
      }
    }
    // Status filter
    if (filters.status !== 'all') {
      const isActive = template.is_active
      if ((filters.status === 'active' && !isActive) || (filters.status === 'inactive' && isActive)) {
        return false
      }
    }
    return true
  })

  // Client-side sorting
  filtered.sort((a: any, b: any) => {
    // ... complex sorting logic
  })

  return filtered
}, [templatesData?.data, filters])
```

**Issues**:
- Loads ALL templates from API regardless of filters
- Client-side filtering inefficient for large datasets
- Filters are in queryKey but never sent to backend
- Unnecessary data transfer
- Poor scalability (breaks with >1000 templates)
- Pagination is fake (all data loaded at once)

**Technical Debt**: 3-4 hours

**Recommended Fix**:
```typescript
const { data: templatesData, isLoading, error, refetch } = useQuery({
  queryKey: ['quiz-templates', currentPage, pageSize, filters],
  queryFn: async () => {
    // Send filters to backend
    return await apiClient.quizzes.listTemplates({
      page: currentPage,
      size: pageSize,
      search: filters.search || undefined,
      type: filters.type !== 'all' ? filters.type : undefined,
      is_active: filters.status !== 'all'
        ? filters.status === 'active'
        : undefined,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder
    });
  },
  staleTime: 5 * 60 * 1000, // 5 minutes
  gcTime: 10 * 60 * 1000,
  retry: 3
});

// Remove useMemo client-side filtering entirely
// Use templatesData.items directly
```

### High Severity Issues

#### 2.2 Very Long Component (941 lines)
- **Severity**: High
- **Category**: Maintainability / Code Smell

**Problem**: Component is nearly 1000 lines, far exceeding best practices (500 line limit).

**Issues**:
- Difficult to test
- Difficult to understand
- Violates Single Responsibility Principle
- Mixing UI, business logic, and form management

**Technical Debt**: 3-4 hours

**Recommended Fix**: Extract into multiple components:
```
components/questionarios/
├── QuestionariosPage.tsx (main orchestrator)
├── QuestionnaireFilters.tsx (filters section)
├── QuestionnaireStats.tsx (stats cards)
├── QuestionnaireGrid.tsx (grid display)
├── QuestionnaireCard.tsx (individual card, already extracted)
├── CreateQuestionnaireDialog.tsx (creation dialog)
├── QuestionEditor.tsx (question form)
└── hooks/
    ├── useQuestionnaireFilters.ts
    ├── useQuestionnaireForm.ts
    └── useQuestionnaireQueries.ts
```

#### 2.3 Sequential Promise.all for Analytics
- **Lines**: 145-162
- **Severity**: High
- **Category**: Performance

**Problem**:
```typescript
const templatesWithAnalytics = await Promise.all(
  (transformedResult.data || []).map(async (template: QuizTemplate) => {
    try {
      const analytics = await (apiClient as any).quizzes.getTemplateAnalytics(template.id)
      return { ...template, analytics }
    } catch (error) {
      logger.warn(`Failed to get analytics for template`, { templateId: template.id, error });
      return {
        ...template,
        analytics: {
          total_responses: 0,
          completion_rate: 0,
          average_completion_time: null
        }
      }
    }
  })
)
```

**Issues**:
- N+1 query problem
- Makes N separate API calls for N templates
- Slow for large datasets
- Could cause rate limiting issues
- Unnecessary network overhead

**Technical Debt**: 2-3 hours

**Recommended Fix**:
```typescript
// Backend should return analytics with templates in single query
const { data: templatesData } = useQuery({
  queryKey: ['quiz-templates', currentPage, pageSize, filters],
  queryFn: async () => {
    // API should include analytics in response
    return await apiClient.quizzes.listTemplatesWithAnalytics({
      page: currentPage,
      size: pageSize,
      include_analytics: true,
      // ... filters
    });
  }
});

// OR if backend can't be changed, batch the analytics request:
const { data: templatesData } = useQuery({
  queryKey: ['quiz-templates', currentPage, pageSize, filters],
  queryFn: async () => {
    const templates = await apiClient.quizzes.listTemplates({ /* params */ });
    const templateIds = templates.items.map(t => t.id);

    // Single batch request for all analytics
    const analytics = await apiClient.quizzes.getBatchAnalytics(templateIds);

    return {
      ...templates,
      items: templates.items.map(template => ({
        ...template,
        analytics: analytics[template.id] || DEFAULT_ANALYTICS
      }))
    };
  }
});
```

### Medium Severity Issues

#### 2.4 Unsafe Type Assertions and 'any' Usage
- **Lines**: 136, 148, 260, 269
- **Severity**: Medium
- **Category**: Type Safety

**Problem**:
```typescript
const resultData = (result as any)?.items || (Array.isArray(result) ? result : [])
const transformedResult = {
  data: resultData,
  total: (result as any)?.total || resultData.length || 0,
  page: currentPage,
  size: pageSize
}

const analytics = await (apiClient as any).quizzes.getTemplateAnalytics(template.id)

let filtered = templatesData.data.filter((template: any) => {
  const templateType = template.name.toLowerCase().includes('medical') ||
                     template.name.toLowerCase().includes('oncolog') ? 'medical' : 'wellness'
```

**Issues**:
- Multiple `as any` type casts
- Loses type safety benefits
- Could hide runtime errors
- Makes refactoring dangerous

**Recommended Fix**:
```typescript
// Define proper types
interface ListTemplatesResponse {
  items: QuizTemplate[];
  total: number;
  page: number;
  size: number;
}

interface QuizTemplateWithAnalytics extends QuizTemplate {
  analytics: QuizAnalytics;
}

// Update apiClient types
declare module '@/lib/api-client' {
  interface QuizzesAPI {
    listTemplates(params: ListTemplatesParams): Promise<ListTemplatesResponse>;
    getTemplateAnalytics(id: string): Promise<QuizAnalytics>;
  }
}

// Use proper typing
const { data: templatesData } = useQuery<ListTemplatesResponse>({
  queryKey: ['quiz-templates', currentPage, pageSize, filters],
  queryFn: () => apiClient.quizzes.listTemplates({
    page: currentPage,
    size: pageSize,
    // ... filters
  })
});

const filteredTemplates = useMemo(() => {
  return templatesData?.items.filter((template: QuizTemplate) => {
    // Type-safe filtering
  });
}, [templatesData, filters]);
```

#### 2.5 Complex Form State Management
- **Lines**: 224-372
- **Severity**: Medium
- **Category**: Complexity

**Problem**: Mixing react-hook-form with manual state updates creates complexity.

**Recommended Fix**: Use react-hook-form's `useFieldArray` for questions array:
```typescript
import { useFieldArray } from 'react-hook-form';

const { fields, append, remove, update } = useFieldArray({
  control,
  name: 'questions'
});

// Simplifies addQuestion, removeQuestion, updateQuestion functions
```

#### 2.6 Hardcoded Display Logic in Component
- **Lines**: 834-843
- **Severity**: Medium
- **Category**: Separation of Concerns

**Problem**:
```typescript
const getTypeFromName = (name: string) => {
  const lowerName = name.toLowerCase()
  if (lowerName.includes('medical') || lowerName.includes('oncolog') || lowerName.includes('sintoma')) {
    return { label: 'Médico', color: 'bg-blue-100 text-blue-800' }
  }
  return { label: 'Bem-estar', color: 'bg-purple-100 text-purple-800' }
}
```

**Issues**:
- Business logic in UI component
- Fragile string matching
- Should come from backend or metadata

**Recommended Fix**:
```typescript
// Backend should provide template.type field
// Or use metadata:
interface QuizTemplate {
  id: string;
  name: string;
  metadata: {
    category: 'medical' | 'wellness';
    tags: string[];
  };
}

// In component:
const getTypeInfo = (template: QuizTemplate) => {
  const typeConfig = {
    medical: { label: 'Médico', color: 'bg-blue-100 text-blue-800' },
    wellness: { label: 'Bem-estar', color: 'bg-purple-100 text-purple-800' }
  };

  return typeConfig[template.metadata.category];
};
```

---

## 3. ReportsPage.tsx

**Quality Score**: 7.5/10
**Lines of Code**: 290
**Complexity**: Medium
**Technical Debt**: 2-3 hours

### Critical Issues

#### 3.1 Filter Params Not Sent to API
- **Lines**: 50-56
- **Severity**: Critical
- **Category**: Data Fetching / Cache Invalidation

**Problem**:
```typescript
const { data: reportsData, isLoading, refetch } = useQuery({
  queryKey: ['reports', { page: currentPage, size: 20, search: searchQuery, status: statusFilter, type: typeFilter }],
  queryFn: () => apiClient.reports.list({
    page: currentPage,
    size: 20
    // ❌ searchQuery, statusFilter, typeFilter NOT sent to API!
  })
})
```

**Issues**:
- Filters in queryKey but not in queryFn
- Creates separate cache entries for each filter combination
- API returns same data regardless of filters
- Misleading cache behavior
- Likely requires client-side filtering (not shown in code)

**Technical Debt**: 1 hour

**Recommended Fix**:
```typescript
const { data: reportsData, isLoading, refetch } = useQuery({
  queryKey: ['reports', { page: currentPage, size: 20, search: searchQuery, status: statusFilter, type: typeFilter }],
  queryFn: () => apiClient.reports.list({
    page: currentPage,
    size: 20,
    search: searchQuery || undefined,
    status: statusFilter || undefined,
    type: typeFilter || undefined
  })
})
```

### High Severity Issues

#### 3.2 Manual File Download Implementation
- **Lines**: 63-135
- **Severity**: High
- **Category**: Error Handling / Security

**Problem**:
```typescript
const handleDownloadReport = async (reportId: string) => {
  try {
    setDownloading(reportId)

    // Make direct request to download endpoint to get blob
    const response = await fetch(`${apiClient.getBaseURL()}/api/v1/reports/${reportId}/download`, {
      method: 'GET',
      headers: {
        ['Authorization']: `Bearer ${token}`
      }
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Download failed' }))
      throw new Error(errorData.message || 'Download failed')
    }

    // Get content type and filename from headers
    const contentType = response.headers.get('content-type') || 'application/octet-stream'
    const contentDisposition = response.headers.get('content-disposition')

    // Extract filename from content-disposition header or generate default
    let filename = `report-${reportId}-${Date.now()}`
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename[^;=\n]*=(['"]?)([^'"\n]*\.[^'"\n]*)\1?/)
      if (filenameMatch && filenameMatch[2]) {
        filename = filenameMatch[2]
      }
    } else {
      // Determine file extension based on content type
      if (contentType.includes('pdf')) {
        filename += '.pdf'
      } else if (contentType.includes('excel') || contentType.includes('spreadsheetml')) {
        filename += '.xlsx'
      } else if (contentType.includes('csv')) {
        filename += '.csv'
      } else if (contentType.includes('json')) {
        filename += '.json'
      } else {
        filename += '.txt'
      }
    }

    // Get blob from response
    const blob = await response.blob()

    // Create download link
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()

    // Cleanup
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    toast({
      title: 'Download concluído',
      description: `Relatório ${filename} baixado com sucesso.`,
    })
  } catch (error: any) {
    logger.error('Download error', { reportId, error })
    toast({
      title: 'Erro no download',
      description: error.message || 'Não foi possível baixar o relatório.',
      variant: 'destructive'
    })
  } finally {
    setDownloading(null)
  }
}
```

**Issues**:
- 73 lines of complex download logic in component
- Manual fetch instead of using apiClient
- Manual token management
- Complex filename extraction logic
- Not reusable
- Violates Single Responsibility Principle

**Technical Debt**: 1-2 hours

**Recommended Fix**:
```typescript
// utils/file-download.ts
export async function downloadFile(
  url: string,
  defaultFilename: string,
  authToken?: string
): Promise<{ success: boolean; filename?: string; error?: string }> {
  try {
    const headers: HeadersInit = {};
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const response = await fetch(url, { method: 'GET', headers });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: 'Download failed' }));
      throw new Error(errorData.message || 'Download failed');
    }

    const filename = extractFilename(response, defaultFilename);
    const blob = await response.blob();

    triggerDownload(blob, filename);

    return { success: true, filename };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

function extractFilename(response: Response, fallback: string): string {
  const contentDisposition = response.headers.get('content-disposition');
  if (contentDisposition) {
    const match = contentDisposition.match(/filename[^;=\n]*=(['"]?)([^'"\n]*)\1/);
    if (match?.[2]) return match[2];
  }

  const contentType = response.headers.get('content-type') || '';
  const extension = getExtensionFromContentType(contentType);

  return `${fallback}.${extension}`;
}

function getExtensionFromContentType(contentType: string): string {
  if (contentType.includes('pdf')) return 'pdf';
  if (contentType.includes('excel') || contentType.includes('spreadsheetml')) return 'xlsx';
  if (contentType.includes('csv')) return 'csv';
  if (contentType.includes('json')) return 'json';
  return 'txt';
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  window.URL.revokeObjectURL(url);
}

// In component:
import { downloadFile } from '@/utils/file-download';

const handleDownloadReport = async (reportId: string) => {
  setDownloading(reportId);

  const result = await downloadFile(
    `${apiClient.getBaseURL()}/api/v1/reports/${reportId}/download`,
    `report-${reportId}-${Date.now()}`,
    token
  );

  setDownloading(null);

  if (result.success) {
    toast({
      title: 'Download concluído',
      description: `Relatório ${result.filename} baixado com sucesso.`,
    });
  } else {
    logger.error('Download error', { reportId, error: result.error });
    toast({
      title: 'Erro no download',
      description: result.error || 'Não foi possível baixar o relatório.',
      variant: 'destructive'
    });
  }
};
```

### Medium Severity Issues

#### 3.3 Computed Stats Not Memoized
- **Lines**: 137-145
- **Severity**: Medium
- **Category**: Performance

**Problem**:
```typescript
const getReportsStats = () => {
  const reports = reportsData?.items || []
  return {
    total: reports.length,
    completed: reports.filter(r => r.status === 'completed').length,
    generating: reports.filter(r => r.status === 'generating').length,
    failed: reports.filter(r => r.status === 'failed').length
  }
}

const stats = getReportsStats()
```

**Issues**:
- Recalculated on every render
- Multiple filter operations
- Not memoized

**Recommended Fix**:
```typescript
const stats = useMemo(() => {
  const reports = reportsData?.items || [];

  return reports.reduce((acc, report) => {
    acc.total++;
    if (report.status === 'completed') acc.completed++;
    if (report.status === 'generating') acc.generating++;
    if (report.status === 'failed') acc.failed++;
    return acc;
  }, { total: 0, completed: 0, generating: 0, failed: 0 });
}, [reportsData?.items]);
```

#### 3.4 Missing Loading States for Mutations
- **Lines**: 159, 284-286
- **Severity**: Medium
- **Category**: UX

**Problem**: Dialog doesn't show loading state when generating report.

**Recommended Fix**:
```typescript
// In ReportGenerator component
<Button onClick={handleGenerate} disabled={isGenerating}>
  {isGenerating ? (
    <>
      <LoadingSpinner size="sm" className="mr-2" />
      Gerando...
    </>
  ) : (
    'Gerar Relatório'
  )}
</Button>
```

---

## 4. AlertsPage.tsx

**Quality Score**: 8/10
**Lines of Code**: 533
**Complexity**: Medium-High
**Technical Debt**: 2-3 hours

### High Severity Issues

#### 4.1 Type Filter in State But Not Sent to API
- **Lines**: 45-53
- **Severity**: High
- **Category**: Data Fetching

**Problem**:
```typescript
const [filters, setFilters] = useState({
  severity: '',
  acknowledged: '',
  type: '' // ❌ Defined but never used
})

const { data: alertsData, isLoading } = useQuery({
  queryKey: ['alerts', { page: currentPage, size: 20, ...filters }],
  queryFn: () => apiClient.alerts.list({
    page: currentPage,
    size: 20,
    ...(filters.severity && { severity: filters.severity }),
    ...(filters.acknowledged && { acknowledged: filters.acknowledged === 'true' })
    // ❌ filters.type NOT sent to API
  })
})
```

**Issues**:
- `type` filter in queryKey but not in query parameters
- Creates different cache entries for different types
- API returns same data regardless of type filter
- Inconsistent filter application

**Technical Debt**: 30 minutes

**Recommended Fix**:
```typescript
const { data: alertsData, isLoading } = useQuery({
  queryKey: ['alerts', { page: currentPage, size: 20, ...filters }],
  queryFn: () => apiClient.alerts.list({
    page: currentPage,
    size: 20,
    ...(filters.severity && { severity: filters.severity }),
    ...(filters.acknowledged && { acknowledged: filters.acknowledged === 'true' }),
    ...(filters.type && { type: filters.type }) // ✅ Add type filter
  })
})
```

### Medium Severity Issues

#### 4.2 Client-Side Filtering With useMemo
- **Lines**: 135-148
- **Severity**: Medium
- **Category**: Performance

**Problem**:
```typescript
const filteredAlerts = useMemo(() => {
  let alerts = alertsData?.items || []

  if (searchQuery) {
    const query = searchQuery.toLowerCase()
    alerts = alerts.filter((alert: any) =>
      alert.title?.toLowerCase().includes(query) ||
      alert.message?.toLowerCase().includes(query) ||
      alert.patient_name?.toLowerCase().includes(query)
    )
  }

  return alerts
}, [alertsData?.items, searchQuery])
```

**Issues**:
- Client-side search filtering
- Not sent to backend
- Inefficient for large datasets

**Technical Debt**: 1 hour

**Recommended Fix**:
```typescript
// Add search to query
const { data: alertsData, isLoading } = useQuery({
  queryKey: ['alerts', { page: currentPage, size: 20, search: searchQuery, ...filters }],
  queryFn: () => apiClient.alerts.list({
    page: currentPage,
    size: 20,
    search: searchQuery || undefined,
    ...(filters.severity && { severity: filters.severity }),
    ...(filters.acknowledged && { acknowledged: filters.acknowledged === 'true' }),
    ...(filters.type && { type: filters.type })
  })
})

// Remove useMemo filtering - use data directly
const alerts = alertsData?.items || [];
```

#### 4.3 CSV Export Logic in Component
- **Lines**: 186-216
- **Severity**: Medium
- **Category**: Separation of Concerns

**Problem**: Complex CSV generation logic embedded in component.

**Technical Debt**: 1 hour

**Recommended Fix**:
```typescript
// utils/csv-export.ts
export function exportToCSV<T extends Record<string, any>>(
  data: T[],
  filename: string,
  columnMapping: Record<string, string>
): void {
  const headers = Object.values(columnMapping);
  const keys = Object.keys(columnMapping);

  const csv = [
    headers.join(','),
    ...data.map(row =>
      keys.map(key => `"${row[key] ?? 'N/A'}"`).join(',')
    )
  ].join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

// In component:
import { exportToCSV } from '@/utils/csv-export';

const handleExportAlerts = () => {
  exportToCSV(
    filteredAlerts,
    `alertas-${new Date().toISOString().split('T')[0]}.csv`,
    {
      id: 'ID',
      title: 'Título',
      message: 'Mensagem',
      severity: 'Severidade',
      type: 'Tipo',
      patient_name: 'Paciente',
      is_acknowledged: 'Reconhecido',
      created_at: 'Data'
    }
  );

  toast({
    title: 'Exportação concluída',
    description: 'Alertas exportados com sucesso.'
  });
};
```

#### 4.4 Component Exceeds Recommended Length
- **Severity**: Medium
- **Category**: Maintainability

**Problem**: Component is 533 lines, exceeding 500 line recommended limit.

**Technical Debt**: 1-2 hours

**Recommended Fix**: Extract sub-components:
- `AlertsFilters.tsx` (lines 324-461)
- `AlertsStats.tsx` (lines 261-321)
- `BulkActionsBar.tsx` (lines 425-458)
- `AlertsList.tsx` (lines 464-529)

---

## Summary Table: All Issues

| File | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| ClinicalMonitoringDashboard.tsx | 2 | 3 | 4 | 0 | 9 |
| QuestionariosPage.tsx | 1 | 2 | 3 | 0 | 6 |
| ReportsPage.tsx | 1 | 1 | 2 | 0 | 4 |
| AlertsPage.tsx | 0 | 1 | 2 | 0 | 3 |
| **TOTAL** | **4** | **7** | **11** | **0** | **22** |

---

## Code Smells Detected

### 1. **God Components**
- ClinicalMonitoringDashboard.tsx (553 lines)
- QuestionariosPage.tsx (941 lines)
- AlertsPage.tsx (533 lines)

### 2. **Manual Data Fetching Pattern**
- ClinicalMonitoringDashboard.tsx (not using React Query)

### 3. **Client-Side Filtering When Should Be Server-Side**
- QuestionariosPage.tsx (complete client-side filtering)
- AlertsPage.tsx (search filtering)

### 4. **Inappropriate Intimacy**
- Components directly accessing apiClient internals
- Manual token management in ReportsPage

### 5. **Duplicate Code**
- File download logic should be extracted
- CSV export logic should be extracted
- Stats calculation patterns repeated

### 6. **Hardcoded Values**
- Magic numbers (thresholds, time ranges)
- Mock data in production code
- Display logic based on string matching

### 7. **Type Safety Issues**
- Excessive use of `any` type
- Type assertions without validation
- Missing WebSocket validation

---

## Refactoring Opportunities

### 1. **Create Shared Utilities**

#### File Download Utility
```typescript
// utils/file-download.ts
export async function downloadFile(
  url: string,
  defaultFilename: string,
  authToken?: string
): Promise<DownloadResult>

// Benefits:
// - Reusable across all pages
// - Centralized error handling
// - Consistent UX
// - Testable in isolation
```

#### CSV Export Utility
```typescript
// utils/csv-export.ts
export function exportToCSV<T>(
  data: T[],
  filename: string,
  columnMapping: Record<keyof T, string>
): void

// Benefits:
// - Reusable for any data export
// - Type-safe column mapping
// - Consistent formatting
```

#### Stats Calculator Hook
```typescript
// hooks/useStatsCalculator.ts
export function useStatsCalculator<T>(
  items: T[],
  groupBy: (item: T) => string
): Record<string, number>

// Benefits:
// - Memoized calculations
// - Reusable pattern
// - Performance optimized
```

### 2. **Extract Complex Components**

#### Clinical Dashboard Refactor
```
components/clinical-dashboard/
├── ClinicalDashboardPage.tsx (main)
├── DashboardHeader.tsx
├── ClinicalMetricsKPIs.tsx
├── tabs/
│   ├── AdherenceTab.tsx
│   ├── SentimentTab.tsx
│   ├── RiskPatientsTab.tsx
│   └── EngagementTab.tsx
├── ClinicalRecommendations.tsx
└── hooks/
    ├── useClinicalMetrics.ts
    ├── useRiskPatients.ts
    └── useAdherenceData.ts
```

### 3. **Implement Zod Validation**
```typescript
// schemas/clinical-schemas.ts
export const ClinicalMetricsSchema = z.object({
  patientEngagement: z.number().min(0).max(1),
  quizCompletion: z.number().min(0).max(1),
  // ... all fields with validation
});

// Benefits:
// - Runtime type safety
// - Automatic TypeScript types
// - WebSocket message validation
// - API response validation
```

### 4. **Centralize Configuration**
```typescript
// config/clinical-config.ts
export const CLINICAL_CONFIG = {
  thresholds: {
    patientEngagement: 0.6,
    quizCompletion: 0.7,
    averageSentiment: 0.3,
    maxRiskPatients: 5
  },
  timeRanges: [
    { value: '7', label: 'Últimos 7 dias' },
    { value: '30', label: 'Últimos 30 dias' },
    { value: '90', label: 'Últimos 90 dias' }
  ],
  refreshInterval: 30000, // 30 seconds
  staleTime: 5 * 60 * 1000 // 5 minutes
} as const;
```

---

## Best Practices Violations

### 1. **SOLID Principles**

#### Single Responsibility Principle
❌ **Violated in**: All analyzed components
**Issue**: Components mixing data fetching, business logic, UI rendering, and event handling
**Fix**: Extract hooks for data, utilities for business logic

#### Open/Closed Principle
❌ **Violated in**: QuestionariosPage, ClinicalMonitoringDashboard
**Issue**: Hardcoded type detection, hardcoded thresholds
**Fix**: Use configuration, metadata-driven approach

### 2. **DRY (Don't Repeat Yourself)**
❌ **Violated in**: Stats calculation, filtering logic, download logic
**Fix**: Create reusable hooks and utilities

### 3. **KISS (Keep It Simple)**
❌ **Violated in**: QuestionariosPage (941 lines), complex nested filtering
**Fix**: Break into smaller, focused components

### 4. **Separation of Concerns**
❌ **Violated in**: ReportsPage download logic, AlertsPage CSV export
**Fix**: Extract to utility modules

---

## Performance Concerns

### 1. **N+1 Queries**
- **File**: QuestionariosPage.tsx
- **Lines**: 145-162
- **Impact**: High
- **Fix**: Batch analytics requests or include in main query

### 2. **Unnecessary Re-renders**
- **File**: ClinicalMonitoringDashboard.tsx
- **Issue**: Stats calculated on every render
- **Fix**: Wrap in useMemo

### 3. **Large Data Transfer**
- **File**: QuestionariosPage.tsx
- **Issue**: Loading all templates for client-side filtering
- **Fix**: Server-side filtering

### 4. **Multiple Simultaneous API Calls**
- **File**: ClinicalMonitoringDashboard.tsx
- **Lines**: 123-127
- **Fix**: Combine into single query or use Promise.all properly

---

## Security Concerns

### 1. **Manual Token Handling**
- **File**: ReportsPage.tsx
- **Lines**: 70-72
- **Risk**: Token exposure, inconsistent auth
- **Fix**: Use apiClient for all requests

### 2. **Unvalidated WebSocket Data**
- **File**: ClinicalMonitoringDashboard.tsx
- **Lines**: 131-137
- **Risk**: Type confusion, potential XSS
- **Fix**: Implement Zod validation

### 3. **CSV Injection Potential**
- **File**: AlertsPage.tsx
- **Lines**: 187-202
- **Risk**: Formula injection in CSV export
- **Fix**: Sanitize cell values, use proper CSV library

---

## Testing Recommendations

### Unit Tests Needed

1. **Utility Functions**
   - `downloadFile` function
   - `exportToCSV` function
   - `getTypeFromName` logic
   - Stats calculation functions

2. **Custom Hooks**
   - `useClinicalMetrics`
   - `useQuestionnaireFilters`
   - `useStatsCalculator`

3. **Component Logic**
   - Filter state management
   - Bulk operations
   - Form validation

### Integration Tests Needed

1. **Query Integration**
   - Verify queryKey matches queryFn params
   - Test cache invalidation
   - Test optimistic updates

2. **User Workflows**
   - Create questionnaire flow
   - Acknowledge/resolve alerts flow
   - Download report flow
   - Apply filters flow

### E2E Tests Needed

1. **Critical Paths**
   - Dashboard loads and updates real-time
   - Create and publish questionnaire
   - Download report successfully
   - Bulk acknowledge alerts

---

## Action Plan (Prioritized)

### Phase 1: Critical Fixes (Week 1)

#### Priority 1.1: Fix Data Fetching Anti-patterns (8 hours)
1. **ClinicalMonitoringDashboard.tsx**: Convert to React Query
   - Replace manual fetch with useQuery
   - Combine three API calls into one
   - Add proper error handling
   - **Files to modify**: ClinicalMonitoringDashboard.tsx, api-client.ts

2. **QuestionariosPage.tsx**: Implement server-side filtering
   - Send all filters to backend
   - Remove client-side filtering useMemo
   - Remove N+1 analytics queries
   - **Files to modify**: QuestionariosPage.tsx, api-client.ts

3. **ReportsPage.tsx**: Send filter params to API
   - Add search, status, type to queryFn
   - **Files to modify**: ReportsPage.tsx

4. **AlertsPage.tsx**: Send type filter to API
   - Add type param to query
   - **Files to modify**: AlertsPage.tsx

#### Priority 1.2: Create Shared Utilities (4 hours)
1. **File Download Utility**
   - Create `utils/file-download.ts`
   - Refactor ReportsPage to use it
   - **New files**: utils/file-download.ts

2. **CSV Export Utility**
   - Create `utils/csv-export.ts`
   - Refactor AlertsPage to use it
   - **New files**: utils/csv-export.ts

### Phase 2: High Priority Improvements (Week 2)

#### Priority 2.1: Component Extraction (6 hours)
1. **QuestionariosPage.tsx**: Break into smaller components
   - Extract QuestionnaireFilters
   - Extract QuestionnaireStats
   - Extract CreateQuestionnaireDialog
   - **New files**: 4 component files, 3 hook files

2. **ClinicalMonitoringDashboard.tsx**: Extract tabs
   - Create tab components
   - Extract metrics hooks
   - **New files**: 5 component files, 3 hook files

#### Priority 2.2: Type Safety (4 hours)
1. **Implement Zod Schemas**
   - Clinical metrics validation
   - WebSocket message validation
   - API response validation
   - **New files**: schemas/clinical-schemas.ts

2. **Remove 'any' Types**
   - Define proper interfaces
   - Update apiClient types
   - **Files to modify**: All 4 components, api-client.ts

### Phase 3: Medium Priority Refinements (Week 3)

#### Priority 3.1: Configuration Extraction (2 hours)
1. **Clinical Thresholds Config**
   - Extract hardcoded values
   - **New files**: config/clinical-config.ts

2. **Display Logic Config**
   - Type mappings
   - Color schemes
   - **New files**: config/display-config.ts

#### Priority 3.2: Performance Optimization (3 hours)
1. **Memoization**
   - Add useMemo to stats calculations
   - Add useCallback to event handlers

2. **Query Optimization**
   - Configure staleTime and cacheTime
   - Implement prefetching for navigation

### Phase 4: Testing & Documentation (Week 4)

#### Priority 4.1: Unit Tests (6 hours)
1. Write tests for utility functions
2. Write tests for custom hooks
3. Write tests for component logic

#### Priority 4.2: Integration Tests (4 hours)
1. Test query behavior
2. Test cache invalidation
3. Test optimistic updates

#### Priority 4.3: Documentation (2 hours)
1. Add JSDoc comments
2. Create component usage docs
3. Update README

---

## Estimated Time Investment

| Phase | Tasks | Time Estimate |
|-------|-------|---------------|
| Phase 1 | Critical fixes | 12 hours |
| Phase 2 | High priority | 10 hours |
| Phase 3 | Medium priority | 5 hours |
| Phase 4 | Testing & docs | 12 hours |
| **TOTAL** | | **39 hours** |

**Recommended Approach**:
- Address Phase 1 immediately (1-2 sprints)
- Phase 2 in following sprint
- Phases 3-4 as technical debt items

---

## Conclusion

The analyzed components demonstrate solid functionality but suffer from common React anti-patterns:

### Strengths
✅ Good use of React Query in AlertsPage and ReportsPage
✅ Proper TypeScript interfaces defined
✅ Consistent UI patterns with shadcn/ui
✅ Logging implemented for debugging
✅ Toast notifications for user feedback

### Weaknesses
❌ Manual data fetching in ClinicalMonitoringDashboard
❌ Client-side filtering instead of server-side
❌ Filter params in queryKey but not sent to API
❌ Components too long (500+ lines)
❌ Hardcoded configuration values
❌ Lack of type validation for runtime data
❌ Business logic mixed with UI components

### Impact
- **Maintainability**: Medium-Low (complex, long components)
- **Performance**: Medium (client-side filtering, N+1 queries)
- **Security**: Medium (unvalidated WebSocket data, manual token handling)
- **Scalability**: Low (client-side operations won't scale)

### Recommendation
Invest 12 hours (Phase 1) immediately to fix critical data fetching issues. This will:
- Improve performance significantly
- Enable proper caching
- Fix cache invalidation bugs
- Improve scalability

The remaining 27 hours can be spread across 2-3 sprints to address maintainability and testing.

---

**Report Generated**: 2025-10-06
**Analyst**: Code Quality Analyzer Agent
**Next Review**: After Phase 1 completion
