import type {
  AIInsights,
  AIRecommendations,
  AIInsight,
  TrendData,
} from '@/lib/api-client/types'
import type {
  AIRecommendation,
  AIAnalyticsDashboard,
  PatientEngagementMetrics,
  PerformanceTrend,
  SentimentTrend,
} from '@/types/api'
import { InsightType } from '@/types/api'

const normalizePriority = (riskLevel: AIInsights['risk_level']) => {
  if (riskLevel === 'critical') return 'critical'
  if (riskLevel === 'high') return 'high'
  if (riskLevel === 'medium') return 'medium'
  return 'low'
}

const inferInsightType = (text: string): InsightType => {
  const lower = text.toLowerCase()
  if (lower.includes('risco')) return InsightType.RISK
  if (lower.includes('engaj')) return InsightType.ENGAGEMENT
  if (lower.includes('sentiment')) return InsightType.EMOTIONAL
  return InsightType.PATTERN
}

const clamp01 = (value: number) => Math.max(0, Math.min(1, value))

const toNumber = (value: unknown, fallback = 0) =>
  typeof value === 'number' && !Number.isNaN(value) ? value : fallback

const getAvgSentiment = (trends: TrendData[]) => {
  if (!trends?.length) return 0.5
  const values = trends
    .map((trend) => (typeof trend.current_value === 'number' ? trend.current_value : undefined))
    .filter((value): value is number => value !== undefined)
  if (!values.length) return 0.5
  const sum = values.reduce((acc, value) => acc + value, 0)
  return clamp01(sum / values.length)
}

export const mapInsightsToCards = (insights: AIInsights): AIInsight[] => {
  const priority = normalizePriority(insights.risk_level)
  return (insights.key_insights || []).map((text, index) => {
    const trimmed = text.trim()
    const title = trimmed.length > 60 ? `${trimmed.slice(0, 57)}...` : trimmed
    return {
      id: `${insights.patient_id}-insight-${index}`,
      type: inferInsightType(trimmed),
      title,
      description: trimmed,
      confidence: 0.75,
      priority,
      metadata: {
        source: 'key_insights',
      },
      created_at: insights.generated_at,
      patient_id: insights.patient_id,
    }
  })
}

export const mapRecommendationsToCards = (
  recommendations: AIRecommendations,
): AIRecommendation[] => {
  return (recommendations.recommendations || []).map((rec, index) => {
    const mappedType =
      rec.type === 'clinical' || rec.type === 'treatment'
        ? 'treatment'
        : rec.type === 'engagement'
          ? 'communication'
          : rec.type === 'alert'
            ? 'alert'
            : 'follow_up'

    const generatedAt = recommendations.generated_at || new Date().toISOString()

    return {
      id: `${recommendations.patient_id}-rec-${index}`,
      type: mappedType,
      title: rec.description,
      description: rec.description,
      rationale: rec.rationale,
      confidence: rec.priority === 'high' ? 0.85 : rec.priority === 'medium' ? 0.7 : 0.6,
      priority: rec.priority,
      actions: [],
      created_at: generatedAt,
      updated_at: generatedAt,
      patient_id: recommendations.patient_id,
    }
  })
}

const mapSentimentTrends = (trends: TrendData[]): SentimentTrend[] => {
  if (!trends?.length) return []
  const result: SentimentTrend[] = []
  trends.forEach((trend) => {
    trend.data_points?.forEach((point) => {
      const date = typeof point['date'] === 'string'
        ? point['date']
        : typeof point['timestamp'] === 'string'
          ? point['timestamp']
          : undefined
      if (!date) return
      result.push({
        date,
        sentiment_score: clamp01(toNumber(point['value'], 0.5)),
        message_count: toNumber(point['count'], 0),
      })
    })
  })
  return result
}

const mapEngagementMetrics = (insights: AIInsights): PatientEngagementMetrics[] => {
  const metrics = insights.engagement_metrics || {}
  const responseRate = clamp01(toNumber(metrics['response_rate'], 0))
  const avgResponseHours = toNumber(metrics['avg_response_time_hours'], 0)
  const avgResponseMinutes = avgResponseHours > 0 ? Math.round(avgResponseHours * 60) : 0
  const totalMessages = toNumber(metrics['total_messages'], 0)
  const engagementScore = toNumber(metrics['engagement_score'], responseRate * 100)
  return [
    {
      patient_id: insights.patient_id,
      response_rate: responseRate,
      avg_response_time: avgResponseMinutes,
      sentiment_trend: mapSentimentTrends(insights.sentiment_trends || []),
      engagement_score: engagementScore,
      last_interaction: insights.last_contact || insights.generated_at,
      total_interactions: totalMessages,
      preferred_communication_time:
        typeof metrics['preferred_time'] === 'string' ? metrics['preferred_time'] : undefined,
    },
  ]
}

const mapPerformanceTrends = (insights: AIInsights): PerformanceTrend[] => {
  const sentimentTrends = mapSentimentTrends(insights.sentiment_trends || [])
  if (!sentimentTrends.length) return []
  return sentimentTrends.map((trend) => ({
    patient_id: insights.patient_id,
    date: trend.date,
    conversations: trend.message_count,
    avg_sentiment: clamp01(trend.sentiment_score),
    response_accuracy: clamp01(toNumber(insights.engagement_metrics?.['response_rate'], 0)),
    resolution_rate: 0,
  }))
}

export const toAnalyticsDashboard = (
  insights: AIInsights,
  recommendations?: AIRecommendations,
): AIAnalyticsDashboard => {
  const responseRate = clamp01(toNumber(insights.engagement_metrics?.['response_rate'], 0))
  return {
    overview: {
      total_conversations: toNumber(insights.engagement_metrics?.['total_messages'], 0),
      avg_sentiment: getAvgSentiment(insights.sentiment_trends || []),
      response_accuracy: responseRate,
      human_handoff_rate: clamp01(
        toNumber(insights.engagement_metrics?.['human_handoff_rate'], 0),
      ),
    },
    engagement_metrics: mapEngagementMetrics(insights),
    insights: mapInsightsToCards(insights),
    recommendations: recommendations ? mapRecommendationsToCards(recommendations) : [],
    performance_trends: mapPerformanceTrends(insights),
  }
}
