import { ApiClientCore } from "./core";
import { ApiResponse, PaginatedResponse } from "./types";

// ============================================================================
// HIVE MIND TYPES
// ============================================================================

export interface AgentStatus {
    agent_id: string;
    agent_type: string;
    status: string;
    capabilities: string[];
    health?: {
        is_healthy: boolean;
        response_time: number;
        success_rate: number;
        active_tasks: number;
        error_count: number;
    };
}

export interface SystemHealthOverview {
    status: 'healthy' | 'degraded' | 'down';
    timestamp: string;
    system_health: {
        total_agents: number;
        active_agents: number;
        system_uptime_seconds: number;
        agents_by_status: Record<string, number>;
        active_system_alerts: number;
        total_active_alerts: number;
    };
    system_alerts: number;
}

export interface SwarmStatus {
    swarm: {
        swarm_id: string;
        status: string;
        uptime_seconds: number;
        total_agents: number;
        active_tasks: number;
        completed_tasks: number;
        failed_tasks: number;
    };
    timestamp: string;
}

export interface IntegrationStatus {
    integration: {
        integration_mode: string;
        swarm_manager_active: boolean;
        enhanced_flow_engine_active: boolean;
        registered_agents: number;
        agent_enabled_features: Record<string, boolean>;
        migration_percentage: number;
        agent_list: string[];
    };
    timestamp: string;
}

export interface AgentMetrics {
    agent_id: string;
    metrics: Array<{
        timestamp: string;
        response_time: number;
        success_rate: number;
        cpu_usage?: number;
        memory_usage?: number;
    }>;
    count: number;
    timestamp: string;
}

export interface HiveMindSystemStats {
    system: {
        uptime_seconds: number;
        total_agents: number;
        healthy_agents: number;
        integration_mode: string;
        migration_percentage: number;
    };
    swarm: {
        swarm_id: string;
        status: string;
        total_tasks: number;
        active_tasks: number;
    };
    alerts: {
        active_alerts: number;
        total_alerts: number;
        system_alerts: number;
    };
    timestamp: string;
}

export interface ProcessFlowsResponse {
    success: boolean;
    results: {
        total_processed: number;
        agent_processed: number;
        legacy_processed: number;
        errors: Array<{ error: string; type?: string }>;
        performance_metrics: Record<string, unknown>;
    };
    timestamp: string;
}

export interface ConductQuizResponse {
    patient_id: string;
    quiz_type: string;
    result: {
        success: boolean;
        method: string;
        task_id?: string;
        result?: Record<string, unknown>;
        error?: string;
    };
    timestamp: string;
}

// ============================================================================
// HIVE MIND API
// ============================================================================

export interface HiveMindApi {
    health: () => Promise<SystemHealthOverview>;
    agents: {
        list: () => Promise<{ agents: AgentStatus[]; total_agents: number; timestamp: string }>;
        get: (agentId: string) => Promise<AgentStatus>;
        metrics: (agentId: string, limit?: number) => Promise<AgentMetrics>;
    };
    alerts: (activeOnly?: boolean, severity?: string) => Promise<{ alerts: any[]; count: number; active_count: number; timestamp: string }>;
    integration: {
        getStatus: () => Promise<IntegrationStatus>;
        setMode: (mode: string) => Promise<{ success: boolean; new_mode: string; timestamp: string }>;
        setMigrationPercentage: (percentage: number) => Promise<{ success: boolean; new_percentage: number; timestamp: string }>;
    };
    swarm: {
        getStatus: () => Promise<SwarmStatus>;
        getAgents: () => Promise<{ agents: AgentStatus[]; count: number; timestamp: string }>;
    };
    tasks: {
        processFlows: (limit?: number) => Promise<ProcessFlowsResponse>;
        conductQuiz: (patientId: string, quizType?: string) => Promise<ConductQuizResponse>;
    };
    stats: () => Promise<HiveMindSystemStats>;
}

export function createHiveMindApi(client: ApiClientCore): HiveMindApi {
    return {
        health: () => client.get("/api/v2/hive-mind/health"),

        agents: {
            list: () => client.get("/api/v2/hive-mind/agents"),
            get: (agentId: string) => client.get(`/api/v2/hive-mind/agents/${agentId}`),
            metrics: (agentId: string, limit = 10) =>
                client.get(`/api/v2/hive-mind/agents/${agentId}/metrics`, { limit }),
        },

        alerts: (activeOnly = true, severity?: string) => {
            const params: Record<string, any> = { active_only: activeOnly };
            if (severity) params['severity'] = severity;
            return client.get("/api/v2/hive-mind/alerts", params);
        },

        integration: {
            getStatus: () => client.get("/api/v2/hive-mind/integration/status"),
            setMode: (mode: string) =>
                client.put("/api/v2/hive-mind/integration/mode", undefined, { mode }),
            setMigrationPercentage: (percentage: number) =>
                client.put("/api/v2/hive-mind/integration/migration-percentage", undefined, { percentage }),
        },

        swarm: {
            getStatus: () => client.get("/api/v2/hive-mind/swarm/status"),
            getAgents: () => client.get("/api/v2/hive-mind/swarm/agents"),
        },

        tasks: {
            processFlows: (limit = 50) =>
                client.post("/api/v2/hive-mind/tasks/process-flows", undefined, { limit }),
            conductQuiz: (patientId: string, quizType = "monthly_checkup") =>
                client.post(`/api/v2/hive-mind/tasks/conduct-quiz/${patientId}`, undefined, { quiz_type: quizType }),
        },

        stats: () => client.get("/api/v2/hive-mind/stats"),
    };
}
