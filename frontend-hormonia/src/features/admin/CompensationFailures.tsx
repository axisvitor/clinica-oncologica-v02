import React, { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import type { CompensationFailure } from '@/lib/api-client/admin'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Pagination } from '@/components/ui/pagination'
import { TableSkeleton } from '@/components/ui/skeleton'
import { useToast } from '@/components/ui/use-toast'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { ErrorBoundary } from '@/components/error/ErrorBoundary'

type ActionStatus = 'retrying' | 'cleaned'

function formatTimestamp(value?: string | null): string {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('pt-BR')
  } catch {
    return value
  }
}

function getStatusLabel(
  failure: CompensationFailure,
  actionStatus?: ActionStatus
): { label: string; variant: 'destructive' | 'outline' | 'secondary' } {
  if (actionStatus === 'retrying') {
    return { label: 'Retrying', variant: 'outline' }
  }
  if (actionStatus === 'cleaned') {
    return { label: 'Cleaned Up', variant: 'secondary' }
  }
  const normalized = failure.status?.toLowerCase()
  if (normalized === 'cleaned_up') {
    return { label: 'Cleaned Up', variant: 'secondary' }
  }
  return { label: 'Failed', variant: 'destructive' }
}

const PAGE_SIZE = 20

function CompensationFailuresContent() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [currentPage, setCurrentPage] = useState(1)
  const [cleanupTarget, setCleanupTarget] = useState<CompensationFailure | null>(null)
  const [actionStatuses, setActionStatuses] = useState<Record<string, ActionStatus>>({})

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['compensation-failures', currentPage],
    queryFn: () => apiClient.adminV2.listCompensationFailures(currentPage, PAGE_SIZE),
  })

  const failures = useMemo(() => data?.items ?? [], [data])
  const totalPages = useMemo(() => {
    if (!data?.total) return 1
    return Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  }, [data])

  const retryMutation = useMutation({
    mutationFn: (sagaId: string) => apiClient.adminV2.retryCompensation(sagaId),
    onMutate: (sagaId: string) => {
      setActionStatuses((prev) => ({ ...prev, [sagaId]: 'retrying' }))
    },
    onSuccess: (_result: unknown, sagaId: string) => {
      toast({
        title: 'Retry iniciado',
        description: 'A compensacao foi executada novamente.',
      })
      setActionStatuses((prev) => {
        const next = { ...prev }
        delete next[sagaId]
        return next
      })
      queryClient.invalidateQueries({ queryKey: ['compensation-failures'] })
    },
    onError: (mutationError: unknown, sagaId: string) => {
      const message =
        mutationError instanceof Error ? mutationError.message : 'Falha ao executar retry.'
      toast({
        title: 'Retry falhou',
        description: message,
        variant: 'destructive',
      })
      setActionStatuses((prev) => {
        const next = { ...prev }
        delete next[sagaId]
        return next
      })
    },
  })

  const cleanupMutation = useMutation({
    mutationFn: (sagaId: string) => apiClient.adminV2.cleanupCompensation(sagaId),
    onSuccess: (_result: unknown, sagaId: string) => {
      toast({
        title: 'Cleanup concluido',
        description: 'O paciente foi marcado como removido e a saga foi atualizada.',
      })
      setActionStatuses((prev) => ({ ...prev, [sagaId]: 'cleaned' }))
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['compensation-failures'] })
        setActionStatuses((prev) => {
          const next = { ...prev }
          delete next[sagaId]
          return next
        })
      }, 1500)
    },
    onError: (mutationError: unknown, sagaId: string) => {
      const message =
        mutationError instanceof Error ? mutationError.message : 'Falha ao executar cleanup.'
      toast({
        title: 'Cleanup falhou',
        description: message,
        variant: 'destructive',
      })
      setActionStatuses((prev) => {
        const next = { ...prev }
        delete next[sagaId]
        return next
      })
    },
  })

  return (
    <div className="space-y-6" data-testid="compensation-failures-page">
      <Card className="shadow-sm">
        <CardHeader className="border-b">
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle>Compensation Failures</CardTitle>
              <CardDescription>
                Sagas com falhas de compensacao exigindo intervencao manual.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              onClick={() => refetch()}
              disabled={isLoading}
              data-testid="compensation-refresh"
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          {isLoading ? (
            <TableSkeleton rows={5} columns={5} />
          ) : error ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {error instanceof Error ? error.message : 'Erro ao carregar falhas de compensacao.'}
              </AlertDescription>
            </Alert>
          ) : failures.length === 0 ? (
            <div className="text-center py-12 text-sm text-muted-foreground">
              Nenhuma falha de compensacao encontrada.
            </div>
          ) : (
            <div className="space-y-4">
              <Table data-testid="compensation-failures-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Saga ID</TableHead>
                    <TableHead>Patient</TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Error</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {failures.map((failure: CompensationFailure) => {
                    const actionStatus = actionStatuses[failure.saga_id]
                    const status = getStatusLabel(failure, actionStatus)
                    const isRetrying =
                      retryMutation.isPending && retryMutation.variables === failure.saga_id
                    const isCleaning =
                      cleanupMutation.isPending && cleanupMutation.variables === failure.saga_id

                    return (
                      <TableRow key={failure.saga_id} data-testid="compensation-row">
                        <TableCell className="font-mono text-xs">{failure.saga_id}</TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            <span className="font-medium">
                              {failure.patient_name ?? 'Paciente desconhecido'}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {failure.patient_id ?? '-'}
                            </span>
                            <Badge variant={status.variant} data-testid="compensation-status">
                              {status.label}
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell>{formatTimestamp(failure.timestamp)}</TableCell>
                        <TableCell>
                          <div className="space-y-2">
                            <p className="text-sm">{failure.error_details}</p>
                            {failure.failed_steps.length > 0 && (
                              <div className="space-y-1 text-xs text-muted-foreground">
                                {failure.failed_steps.map(
                                  (step: { step: number; error: string }) => (
                                    <div key={`${failure.saga_id}-${step.step}`}>
                                      Step {step.step}: {step.error}
                                    </div>
                                  )
                                )}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => retryMutation.mutate(failure.saga_id)}
                              disabled={isRetrying || isCleaning}
                              data-testid={`retry-compensation-${failure.saga_id}`}
                            >
                              {isRetrying ? 'Retrying...' : 'Retry'}
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => setCleanupTarget(failure)}
                              disabled={isRetrying || isCleaning}
                              data-testid={`cleanup-compensation-${failure.saga_id}`}
                            >
                              Cleanup
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>

              {totalPages > 1 && (
                <Pagination
                  currentPage={currentPage}
                  totalPages={totalPages}
                  onPageChange={setCurrentPage}
                />
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={!!cleanupTarget} onOpenChange={(open) => !open && setCleanupTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm cleanup?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acao faz o soft delete do paciente e marca a saga como cleaned up.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={() => cleanupTarget && cleanupMutation.mutate(cleanupTarget.saga_id)}
            >
              Confirmar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export default function CompensationFailures() {
  return (
    <ErrorBoundary level="page">
      <CompensationFailuresContent />
    </ErrorBoundary>
  )
}
