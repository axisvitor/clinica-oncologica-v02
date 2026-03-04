import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { apiClient } from '@/lib/api-client'
import { AgentStatus } from '@/lib/api-client/hive-mind'
import { Bot, CheckCircle, XCircle } from 'lucide-react'

export function AgentSwarm() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['hive-mind', 'agents'],
    queryFn: () => apiClient.hiveMind.agents.list(),
    refetchInterval: 30_000,
    retry: 2,
  })

  const agents: AgentStatus[] = data?.agents ?? []

  if (isLoading) {
    return <AgentSwarmSkeleton />
  }

  if (error) {
    return (
      <div className="text-red-500">
        {error instanceof Error ? error.message : 'Failed to fetch agents'}
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {agents.map((agent) => (
        <AgentCard key={agent.agent_id} agent={agent} />
      ))}
    </div>
  )
}

function AgentCard({ agent }: { agent: AgentStatus }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Bot className="h-4 w-4" />
          {agent.agent_type}
        </CardTitle>
        {agent.health?.is_healthy ? (
          <CheckCircle className="h-4 w-4 text-green-500" />
        ) : (
          <XCircle className="h-4 w-4 text-red-500" />
        )}
      </CardHeader>
      <CardContent>
        <div className="text-xs text-muted-foreground mb-2">ID: {agent.agent_id}</div>
        <div className="flex flex-wrap gap-1 mb-4">
          {agent.capabilities.map((cap) => (
            <Badge key={cap} variant="secondary" className="text-xs">
              {cap}
            </Badge>
          ))}
        </div>
        {agent.health && (
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span>Success Rate:</span>
              <span className="font-medium">{(agent.health.success_rate * 100).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between">
              <span>Response Time:</span>
              <span className="font-medium">{agent.health.response_time.toFixed(0)}ms</span>
            </div>
            <div className="flex justify-between">
              <span>Active Tasks:</span>
              <span className="font-medium">{agent.health.active_tasks}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AgentSwarmSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <Skeleton className="h-4 w-[100px]" />
            <Skeleton className="h-4 w-4" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-3 w-[150px] mb-4" />
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
