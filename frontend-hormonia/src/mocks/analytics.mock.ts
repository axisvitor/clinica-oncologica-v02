/**
 * Mock Analytics Data
 */

export interface MockOverviewAnalytics {
  total_patients: number
  total_quizzes: number
  completed_quizzes: number
  completion_rate: number
  active_patients_30d: number
  period: {
    start_date: string | null
    end_date: string | null
  }
}

export interface MockEngagementLevels {
  engagement_levels: {
    no_quizzes: number
    low_engagement: number
    high_engagement: number
  }
  average_quizzes_per_patient: number
  total_active_patients: number
}

export interface MockTreatmentDistribution {
  period: '7d' | '30d' | '90d' | 'all'
  total_patients: number
  distribution: Array<{
    treatment_type: string
    count: number
    percentage: number
    color: string
  }>
  trend_data: Array<{ week: string; count: number }>
  last_updated: string
}

const MOCK_OVERVIEW_ANALYTICS: MockOverviewAnalytics = {
  total_patients: 145,
  total_quizzes: 420,
  completed_quizzes: 360,
  completion_rate: 85.7,
  active_patients_30d: 118,
  period: {
    start_date: null,
    end_date: null,
  },
}

const MOCK_ENGAGEMENT_LEVELS: MockEngagementLevels = {
  engagement_levels: {
    no_quizzes: 12,
    low_engagement: 82,
    high_engagement: 51,
  },
  average_quizzes_per_patient: 3.4,
  total_active_patients: 145,
}

const BASE_TREATMENT_DISTRIBUTION = {
  total_patients: 145,
  distribution: [
    { treatment_type: 'Quimioterapia', count: 54, percentage: 37.24, color: '#2563eb' },
    { treatment_type: 'Radioterapia', count: 42, percentage: 28.97, color: '#10b981' },
    { treatment_type: 'Imunoterapia', count: 31, percentage: 21.38, color: '#f59e0b' },
    { treatment_type: 'Acompanhamento', count: 18, percentage: 12.41, color: '#ef4444' },
  ],
  trend_data: [
    { week: '2024-12-02', count: 120 },
    { week: '2024-12-09', count: 130 },
    { week: '2024-12-16', count: 140 },
    { week: '2024-12-23', count: 145 },
  ],
}

/**
 * Get mock overview analytics
 */
export function getMockDashboardAnalytics(): MockOverviewAnalytics {
  return { ...MOCK_OVERVIEW_ANALYTICS }
}

/**
 * Get mock patient engagement analytics
 */
export function getMockEngagementData(): MockEngagementLevels {
  return { ...MOCK_ENGAGEMENT_LEVELS }
}

/**
 * Get mock treatment distribution data
 */
export function getMockTreatmentDistribution(
  period: '7d' | '30d' | '90d' | 'all'
): MockTreatmentDistribution {
  return {
    period,
    total_patients: BASE_TREATMENT_DISTRIBUTION.total_patients,
    distribution: BASE_TREATMENT_DISTRIBUTION.distribution.map((item) => ({ ...item })),
    trend_data: BASE_TREATMENT_DISTRIBUTION.trend_data.map((item) => ({ ...item })),
    last_updated: new Date().toISOString(),
  }
}
