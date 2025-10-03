/**
 * Mock Analytics Data
 */

export interface MockDashboardStats {
  total_patients: number
  active_patients: number
  completed_treatments: number
  pending_alerts: number
  message_response_rate: number
  average_engagement_score: number
}

export interface MockEngagementData {
  date: string
  messages_sent: number
  messages_received: number
  response_rate: number
}

export const MOCK_DASHBOARD_STATS: MockDashboardStats = {
  total_patients: 8,
  active_patients: 6,
  completed_treatments: 2,
  pending_alerts: 3,
  message_response_rate: 87.5,
  average_engagement_score: 8.2
}

export const MOCK_ENGAGEMENT_DATA: MockEngagementData[] = [
  { date: '2024-09-25', messages_sent: 12, messages_received: 10, response_rate: 83.3 },
  { date: '2024-09-26', messages_sent: 15, messages_received: 14, response_rate: 93.3 },
  { date: '2024-09-27', messages_sent: 18, messages_received: 15, response_rate: 83.3 },
  { date: '2024-09-28', messages_sent: 10, messages_received: 9, response_rate: 90.0 },
  { date: '2024-09-29', messages_sent: 14, messages_received: 11, response_rate: 78.6 },
  { date: '2024-09-30', messages_sent: 16, messages_received: 14, response_rate: 87.5 },
  { date: '2024-10-01', messages_sent: 20, messages_received: 18, response_rate: 90.0 }
]

/**
 * Get mock dashboard analytics
 */
export function getMockDashboardAnalytics(): MockDashboardStats {
  return { ...MOCK_DASHBOARD_STATS }
}

/**
 * Get mock engagement data
 */
export function getMockEngagementData(params?: {
  start_date?: string
  end_date?: string
}): MockEngagementData[] {
  let data = [...MOCK_ENGAGEMENT_DATA]

  if (params?.start_date) {
    data = data.filter(d => d.date >= params.start_date!)
  }

  if (params?.end_date) {
    data = data.filter(d => d.date <= params.end_date!)
  }

  return data
}
