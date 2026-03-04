import { ApiClientCore } from './core'

// ============================================================================
// HIVE MIND TYPES
// ============================================================================

export interface AgentStatus {
  agent_id: string
  agent_type: string
  status: string
  capabilities: string[]
  health?: {
    is_healthy: boolean
    response_time: number
    success_rate: number
    active_tasks: number
    error_count: number
  }
}

export interface SystemHealthOverview {
  status: 'healthy' | 'degraded' | 'down'
  timestamp: string
  system_health: {
    total_agents: number
    active_agents: number
    system_uptime_seconds: number
    agents_by_status: Record<string, number>
    active_system_alerts: number
    total_active_alerts: number
  }
  system_alerts: number
}

// ============================================================================
// HIVE MIND API
// ============================================================================

export interface HiveMindApi {
  health: () => Promise<SystemHealthOverview>
  agents: {
    list: () => Promise<{ agents: AgentStatus[]; total_agents: number; timestamp: string }>
  }
}

export function createHiveMindApi(client: ApiClientCore): HiveMindApi {
  return {
    health: () => client.get('/api/v2/hive-mind/health'),

    agents: {
      list: () => client.get('/api/v2/hive-mind/agents'),
    },
  }
}
