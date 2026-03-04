/**
 * PatientRow Component
 * Desktop table row for patient data (virtualized)
 */

import React, { memo } from 'react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { formatLastContact } from '../utils'
import { PatientAvatar } from './PatientAvatar'
import { QuizStatusBadge } from './QuizStatusBadge'
import { PatientActions } from './PatientActions'
import {
  resolvePatientListItemRenderContext,
  type PatientListItemData,
} from './patient-list-item-shared'

interface PatientRowProps {
  style: React.CSSProperties
  index: number
  data: PatientListItemData
}

const GRID_COLS = 'grid-cols-[2.5fr_1.5fr_1fr_1fr_1fr_0.8fr_1.2fr_70px]'

export const PatientRow = memo<PatientRowProps>(({ style, index, data }) => {
  const item = resolvePatientListItemRenderContext(data, index)
  if (!item) return null

  const {
    patient,
    onNavigate,
    onEdit,
    onDelete,
    onActivate,
    onDeactivate,
    onSendQuiz,
    isResending,
    canDelete,
    statusConfig,
    navigateProps,
  } = item

  return (
    <div
      style={style}
      className={cn(
        'grid items-center gap-4 px-4 py-2 border-b hover:bg-muted/50 transition-colors cursor-pointer',
        GRID_COLS
      )}
      {...navigateProps}
    >
      {/* Patient Info */}
      <div className="flex items-center space-x-3 min-w-0">
        <PatientAvatar name={patient.name} size="sm" />
        <div className="min-w-0">
          <p className="font-medium text-gray-900 truncate">{patient.name}</p>
          {patient.email && <p className="text-sm text-gray-500 truncate">{patient.email}</p>}
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
        <Badge className={statusConfig.className}>{statusConfig.label}</Badge>
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
          canDelete={canDelete}
        />
      </div>
    </div>
  )
})

PatientRow.displayName = 'PatientRow'
