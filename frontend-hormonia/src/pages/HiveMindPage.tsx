import { SystemHealth } from '@/components/hive-mind/SystemHealth'
import { AgentSwarm } from '@/components/hive-mind/AgentSwarm'
import { Separator } from '@/components/ui/separator'

export function HiveMindPage() {
  return (
    <div className="space-y-6 p-6 pb-16">
      <div className="space-y-0.5">
        <h2 className="text-2xl font-bold tracking-tight">Hive Mind Dashboard</h2>
        <p className="text-muted-foreground">
          Monitor system health, agent swarm status, and integration metrics.
        </p>
      </div>
      <Separator className="my-6" />

      <div className="space-y-6">
        <section>
          <h3 className="text-lg font-medium mb-4">System Health</h3>
          <SystemHealth />
        </section>

        <Separator className="my-6" />

        <section>
          <h3 className="text-lg font-medium mb-4">Agent Swarm</h3>
          <AgentSwarm />
        </section>
      </div>
    </div>
  )
}
