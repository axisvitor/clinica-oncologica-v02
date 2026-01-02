/**
 * PatientRow Component
 * Desktop table row for patient data (virtualized)
 */

import React, { memo } from 'react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { getStatusBadgeConfig, formatLastContact } from '../utils'
import { PatientAvatar } from './PatientAvatar'
import { QuizStatusBadge } from './QuizStatusBadge'
import { PatientActions } from './PatientActions'

import type { Patient } from '@/types/api'

interface PatientRowData {
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

interface PatientRowProps {
  style: React.CSSProperties
  index: number
  data: PatientRowData
}

const GRID_COLS = "grid-cols-[2.5fr_1.5fr_1fr_1fr_1fr_0.8fr_1.2fr_70px]"

export const PatientRow = memo<PatientRowProps>(({
  style,
  index,
  data
}) => {
  const {
    patients,
    onNavigate,
    onEdit,
    onDelete,
    onActivate,
    onDeactivate,
    onSendQuiz,
    isResending
  } = data ?? {}

  if (!patients || !patients.length) return null

  const patient = patients[index]

  if (!patient) return null

  const statusConfig = getStatusBadgeConfig(patient.status)

  return (
    <div
      style={style}
      className={cn(
        "grid items-center gap-4 px-4 py-2 border-b hover:bg-muted/50 transition-colors cursor-pointer",
        GRID_COLS
      )}
      onClick={() => onNavigate(patient.id)}
    >
      {/* Patient Info */}
      <div className="flex items-center space-x-3 min-w-0">
        <PatientAvatar name={patient.name} size="sm" />
        <div className="min-w-0">
          <p className="font-medium text-gray-900 truncate">{patient.name}</p>
          {patient.email && (
            <p className="text-sm text-gray-500 truncate">{patient.email}</p>
          )}
        </div>
      </div>

      {/* Contact */}
      <div className="text-sm truncate">{patient.phone}</div>

      {/* Treatment */}
      <div>
        <Badge variant="outline" className="truncate">
          {patient.treatment_type}
        </Badge>
      </div>

      {/* Status */}
      <div>
        <Badge className={statusConfig.className}>
          {statusConfig.label}
        </Badge>
      </div>

      {/* Quiz Status */}
      <div onClick={(e) => e.stopPropagation()} className="min-w-0">
        <QuizStatusBadge
          patientId={patient.id}
          patientName={patient.name}
          onSendQuiz={onSendQuiz}
          isResending={isResending}
        />
      </div>

      {/* Current Day */}
      <div className="font-medium">{patient.current_day ?? 0}</div>

      {/* Last Contact */}
      <div className="text-sm text-gray-600 truncate">
        {formatLastContact(patient.last_contact)}
      </div>

      {/* Actions */}
      <div>
        <PatientActions
          patient={patient}
          onView={onNavigate}
          onEdit={onEdit}
          onDelete={onDelete}
          onActivate={onActivate}
          onDeactivate={onDeactivate}
        />
      </div>
    </div>
  )
})

PatientRow.displayName = 'PatientRow'
