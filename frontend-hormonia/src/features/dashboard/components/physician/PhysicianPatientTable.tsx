import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Brain, AlertTriangle, Clock, ChevronRight } from 'lucide-react'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { PhysicianPatient } from '@/lib/api-client/physician'

interface PhysicianPatientTableProps {
  patients: PhysicianPatient[]
  total: number
  page: number
  size: number
  onPageChange: (page: number) => void
}

const FLOW_PHASE_LABELS: Record<string, string> = {
  onboarding: 'Onboarding',
  daily_follow_up: 'Follow-up Diário',
  quiz_mensal: 'Quiz Mensal',
  custom: 'Personalizado',
}

const FLOW_STATUS_LABELS: Record<string, string> = {
  active: 'Ativo',
  paused: 'Pausado',
  completed: 'Concluído',
}

const FLOW_STATUS_VARIANTS: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  active: 'default',
  paused: 'secondary',
  completed: 'outline',
}

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMin / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMin < 1) return 'Agora'
  if (diffMin < 60) return `${diffMin}min atrás`
  if (diffHours < 24) return `${diffHours}h atrás`
  if (diffDays === 1) return 'Ontem'
  if (diffDays < 7) return `${diffDays}d atrás`
  return date.toLocaleDateString('pt-BR')
}

// ============================================================
// Mobile Card — one card per patient, touch-friendly
// ============================================================

function PatientCard({ patient, onNavigate, onAISummary }: {
  patient: PhysicianPatient
  onNavigate: () => void
  onAISummary: () => void
}) {
  return (
    <Card
      className="cursor-pointer hover:shadow-md transition-shadow active:bg-muted/30"
      onClick={onNavigate}
    >
      <CardContent className="p-4">
        {/* Top row: name + alerts */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="font-medium text-base truncate">{patient.name}</p>
            {patient.treatment_type && (
              <p className="text-xs text-muted-foreground truncate">{patient.treatment_type}</p>
            )}
          </div>
          {patient.unacknowledged_alerts_count > 0 && (
            <Badge variant="destructive" className="gap-1 shrink-0">
              <AlertTriangle className="h-3 w-3" />
              {patient.unacknowledged_alerts_count}
            </Badge>
          )}
        </div>

        {/* Middle: flow info */}
        <div className="flex flex-wrap items-center gap-2 mt-3">
          {patient.flow_phase && (
            <Badge variant="outline" className="font-normal text-xs">
              {FLOW_PHASE_LABELS[patient.flow_phase] || patient.flow_phase}
            </Badge>
          )}
          {patient.flow_status && (
            <Badge
              variant={FLOW_STATUS_VARIANTS[patient.flow_status] || 'secondary'}
              className="text-xs"
            >
              {FLOW_STATUS_LABELS[patient.flow_status] || patient.flow_status}
            </Badge>
          )}
          {patient.flow_current_day > 0 && (
            <span className="text-xs text-muted-foreground">
              Dia <span className="font-mono font-medium">{patient.flow_current_day}</span>
            </span>
          )}
        </div>

        {/* Bottom: last interaction + actions */}
        <div className="flex items-center justify-between mt-3 pt-2 border-t">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>{formatRelativeTime(patient.last_interaction)}</span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2"
              onClick={(e) => {
                e.stopPropagation()
                onAISummary()
              }}
            >
              <Brain className="h-4 w-4 mr-1" />
              <span className="text-xs">IA</span>
            </Button>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================
// Main component — table on desktop, cards on mobile
// ============================================================

export function PhysicianPatientTable({
  patients,
  total,
  page,
  size,
  onPageChange,
}: PhysicianPatientTableProps) {
  const navigate = useNavigate()
  const totalPages = Math.ceil(total / size)

  return (
    <TooltipProvider>
      {/* ===== DESKTOP TABLE (hidden on mobile) ===== */}
      <div className="hidden md:block rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Paciente</TableHead>
              <TableHead>Fase do Fluxo</TableHead>
              <TableHead className="text-center">Dia</TableHead>
              <TableHead>Último Contato</TableHead>
              <TableHead className="text-center">Alertas</TableHead>
              <TableHead className="text-center">Status</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {patients.map((patient) => (
              <TableRow
                key={patient.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => navigate(`/physician/patients/${patient.id}`)}
              >
                <TableCell>
                  <div>
                    <p className="font-medium">{patient.name}</p>
                    {patient.treatment_type && (
                      <p className="text-xs text-muted-foreground">{patient.treatment_type}</p>
                    )}
                  </div>
                </TableCell>

                <TableCell>
                  {patient.flow_phase ? (
                    <Badge variant="outline" className="font-normal">
                      {FLOW_PHASE_LABELS[patient.flow_phase] || patient.flow_phase}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground text-sm">Sem fluxo</span>
                  )}
                </TableCell>

                <TableCell className="text-center">
                  {patient.flow_current_day > 0 ? (
                    <span className="font-mono tabular-nums font-medium">
                      {patient.flow_current_day}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>

                <TableCell>
                  <div className="flex items-center gap-1.5 text-sm">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>{formatRelativeTime(patient.last_interaction)}</span>
                  </div>
                </TableCell>

                <TableCell className="text-center">
                  {patient.unacknowledged_alerts_count > 0 ? (
                    <Tooltip>
                      <TooltipTrigger>
                        <Badge variant="destructive" className="gap-1">
                          <AlertTriangle className="h-3 w-3" />
                          {patient.unacknowledged_alerts_count}
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent>
                        {patient.unacknowledged_alerts_count} alerta(s) não reconhecido(s)
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>

                <TableCell className="text-center">
                  {patient.flow_status ? (
                    <Badge variant={FLOW_STATUS_VARIANTS[patient.flow_status] || 'secondary'}>
                      {FLOW_STATUS_LABELS[patient.flow_status] || patient.flow_status}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>

                <TableCell className="text-right">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/physician/patients/${patient.id}?tab=ai-summary`)
                        }}
                      >
                        <Brain className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Resumo IA</TooltipContent>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* ===== MOBILE CARDS (hidden on desktop) ===== */}
      <div className="md:hidden space-y-3">
        {patients.map((patient) => (
          <PatientCard
            key={patient.id}
            patient={patient}
            onNavigate={() => navigate(`/physician/patients/${patient.id}`)}
            onAISummary={() => navigate(`/physician/patients/${patient.id}?tab=ai-summary`)}
          />
        ))}
      </div>

      {/* Pagination — shared */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-muted-foreground">
            {total} paciente{total !== 1 ? 's' : ''} no total
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              Anterior
            </Button>
            <span className="text-sm text-muted-foreground">
              {page}/{totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}
    </TooltipProvider>
  )
}
