import type React from 'react'
import type { Patient } from '@/types/api'
import { getStatusBadgeConfig } from '../utils'

export interface PatientListItemData {
  patients: Patient[]
  onNavigate: (id: string) => void
  onEdit?: (patient: Patient) => void
  onDelete: (e: React.MouseEvent, patientId: string, patientName: string) => void
  onActivate: (id: string) => void
  onDeactivate: (id: string) => void
  onSendQuiz: (patient: { id: string; name: string }) => void
  confirmDeleteId: string | null
  isResending: boolean
  canDelete: boolean
}

export interface PatientListItemContext {
  patient: Patient
  onNavigate: (id: string) => void
  onEdit?: (patient: Patient) => void
  onDelete: (e: React.MouseEvent, patientId: string, patientName: string) => void
  onActivate: (id: string) => void
  onDeactivate: (id: string) => void
  onSendQuiz: (patient: { id: string; name: string }) => void
  confirmDeleteId: string | null
  isResending: boolean
  canDelete: boolean
}

export interface PatientListItemRenderContext extends PatientListItemContext {
  statusConfig: ReturnType<typeof getStatusBadgeConfig>
  navigateProps: ReturnType<typeof getPatientNavigateProps>
}

export function resolvePatientListItem(
  data: PatientListItemData,
  index: number
): PatientListItemContext | null {
  if (!data.patients?.length) {
    return null
  }

  const patient = data.patients[index]
  if (!patient) {
    return null
  }

  return {
    patient,
    onNavigate: data.onNavigate,
    onEdit: data.onEdit,
    onDelete: data.onDelete,
    onActivate: data.onActivate,
    onDeactivate: data.onDeactivate,
    onSendQuiz: data.onSendQuiz,
    confirmDeleteId: data.confirmDeleteId,
    isResending: data.isResending,
    canDelete: data.canDelete,
  }
}

export function handleNavigateOnKeyboard(
  event: React.KeyboardEvent<HTMLElement>,
  onNavigate: (id: string) => void,
  patientId: string
) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    onNavigate(patientId)
  }
}

export function getPatientNavigateProps(onNavigate: (id: string) => void, patient: Patient) {
  return {
    onClick: () => onNavigate(patient.id),
    onKeyDown: (event: React.KeyboardEvent<HTMLElement>) =>
      handleNavigateOnKeyboard(event, onNavigate, patient.id),
    role: 'button' as const,
    tabIndex: 0,
    'aria-label': `Ver detalhes do paciente ${patient.name}`,
  }
}

export function resolvePatientListItemRenderContext(
  data: PatientListItemData,
  index: number
): PatientListItemRenderContext | null {
  const item = resolvePatientListItem(data, index)
  if (!item) {
    return null
  }
  return {
    ...item,
    statusConfig: getStatusBadgeConfig(item.patient.status),
    navigateProps: getPatientNavigateProps(item.onNavigate, item.patient),
  }
}
