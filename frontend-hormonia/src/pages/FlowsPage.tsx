import React, { useState } from 'react'
import { RefreshCw, AlertCircle } from 'lucide-react'
import { useFlows, useFlowStats } from '@/hooks/useFlows'
import { FlowsStats } from '@/features/flows/FlowsStats'
import { FlowsTable } from '@/features/flows/FlowsTable'
import { FlowsFilters } from '@/features/flows/FlowsFilters'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export function FlowsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const { data: flowsData, isLoading: flowsLoading, error: flowsError, refetch } = useFlows({
    ...(statusFilter !== 'all' && { status: statusFilter }),
  })

  const { data: statsData, isLoading: statsLoading } = useFlowStats()

  const handleRefresh = () => {
    refetch()
  }

  return (
    <div className="flex-1 p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold mb-2">Fluxos de Atendimento</h1>
          <p className="text-muted-foreground">
            Gerencie fluxos automatizados de mensagens
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={flowsLoading}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${flowsLoading ? 'animate-spin' : ''}`} />
          Atualizar
        </Button>
      </div>

      {flowsError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Erro ao carregar fluxos</AlertTitle>
          <AlertDescription>
            {(flowsError as any)?.data?.message || 'Não foi possível carregar os dados dos fluxos. Tente novamente.'}
          </AlertDescription>
        </Alert>
      )}

      <FlowsStats stats={statsData} isLoading={statsLoading} />

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Fluxos Ativos</h2>
          <FlowsFilters
            selectedStatus={statusFilter}
            onStatusChange={setStatusFilter}
          />
        </div>

        <FlowsTable
          flows={flowsData?.items || []}
          isLoading={flowsLoading}
        />
      </div>
    </div>
  )
}