/**
 * MobilePatientCard Component
 * Mobile card layout for patient data (virtualized)
 */

import React, { memo } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { getStatusBadgeConfig, formatLastContact } from '../utils'
import { PatientAvatar } from './PatientAvatar'
import { QuizStatusBadge } from './QuizStatusBadge'
import { PatientActions } from './PatientActions'

import type { Patient } from '@/types/api'

interface MobilePatientCardProps {
  style: React.CSSProperties
  index: number
  patients: Patient[]
  onNavigate: (id: string) => void
  onEdit?: (patient: Patient) => void
  onDelete: (e: React.MouseEvent, patientId: string, patientName: string) => void
  onActivate: (id: string) => void
  onDeactivate: (id: string) => void
  onSendQuiz: (patient: { id: string; name: string }) => void
  confirmDeleteId: string | null
  isResending: boolean
}

export const MobilePatientCard = memo<MobilePatientCardProps>(({
  style,
  index,
  patients,
  onNavigate,
  onEdit,
  onDelete,
  onActivate,
  onDeactivate,
  onSendQuiz,
  isResending
}) => {
  const patient = patients[index]

  if (!patient) return null

  const statusConfig = getStatusBadgeConfig(patient.status)

  return (
    <div style={style} className="px-4 pb-3">
      <Card
        className="p-4 hover:shadow-md transition-shadow cursor-pointer h-full"
        onClick={() => onNavigate(patient.id)}
      >
        {/* Header with Avatar and Status */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <PatientAvatar name={patient.name} size="md" />
            <div className="min-w-0 flex-1">
              <p className="font-medium truncate">{patient.name}</p>
              <p className="text-sm text-muted-foreground truncate">
                {patient.phone}
              </p>
              {patient.email && (
                <p className="text-xs text-muted-foreground truncate">
                  {patient.email}
                </p>
              )}
            </div>
          </div>
          <div className="flex-shrink-0">
            <Badge className={statusConfig.className}>
              {statusConfig.label}
            </Badge>
          </div>
        </div>

        {/* Patient Details Grid */}
        <div className="grid grid-cols-2 gap-2 text-sm mb-3">
          <div>
            <span className="text-muted-foreground text-xs">Tratamento:</span>
            <p className="font-medium truncate">
              <Badge variant="outline" className="text-xs">
                {patient.treatment_type}
              </Badge>
            </p>
          </div>
          <div>
            <span className="text-muted-foreground text-xs">Dia Atual:</span>
            <p className="font-medium">{patient.current_day ?? 0}</p>
          </div>
        </div>

        {/* Quiz Status */}
        <div className="mb-3" onClick={(e) => e.stopPropagation()}>
          <span className="text-muted-foreground text-xs block mb-1">
            Quiz Mensal:
          </span>
          <QuizStatusBadge
            patientId={patient.id}
            patientName={patient.name}
            onSendQuiz={onSendQuiz}
            isResending={isResending}
            compact
          />
        </div>

        {/* Footer with Last Contact and Actions */}
        <div className="flex justify-between items-center pt-3 border-t text-xs text-muted-foreground">
          <span className="truncate flex-1">
            Último contato: {formatLastContact(patient.last_contact)}
          </span>
          <div className="flex-shrink-0 ml-2">
            <PatientActions
              patient={patient}
              onView={onNavigate}
              onEdit={onEdit}
              onDelete={onDelete}
              onActivate={onActivate}
              onDeactivate={onDeactivate}
              compact
            />
          </div>
        </div>
      </Card>
    </div>
  )
})

MobilePatientCard.displayName = 'MobilePatientCard'
