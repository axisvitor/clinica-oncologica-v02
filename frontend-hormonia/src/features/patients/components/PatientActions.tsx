/**
 * PatientActions Component
 * Dropdown menu with patient action items
 */

import React from 'react'
import { Eye, CreditCard as Edit, Trash2, Play, Pause } from 'lucide-react'
import { MoveHorizontal as MoreHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

import type { Patient } from '@/types/api'

interface PatientActionsProps {
  patient: Patient
  onView: (id: string) => void
  onEdit?: (patient: Patient) => void
  onDelete: (e: React.MouseEvent, patientId: string, patientName: string) => void
  onActivate: (id: string) => void
  onDeactivate: (id: string) => void
  compact?: boolean
}

export const PatientActions: React.FC<PatientActionsProps> = ({
  patient,
  onView,
  onEdit,
  onDelete,
  onActivate,
  onDeactivate,
  compact = false
}) => {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className={compact ? 'h-8 w-8 p-0' : 'h-8 w-8 p-0'}
          onClick={(e) => e.stopPropagation()}
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Ações</DropdownMenuLabel>

        <DropdownMenuItem
          onClick={(e) => {
            e.stopPropagation()
            onView(patient.id)
          }}
        >
          <Eye className="mr-2 h-4 w-4" />
          Visualizar
        </DropdownMenuItem>

        {onEdit && (
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation()
              onEdit(patient)
            }}
          >
            <Edit className="mr-2 h-4 w-4" />
            Editar
          </DropdownMenuItem>
        )}

        <DropdownMenuSeparator />

        {patient.status === 'active' ? (
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation()
              onDeactivate(patient.id)
            }}
          >
            <Pause className="mr-2 h-4 w-4" />
            Pausar
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation()
              onActivate(patient.id)
            }}
          >
            <Play className="mr-2 h-4 w-4" />
            Ativar
          </DropdownMenuItem>
        )}

        <DropdownMenuSeparator />

        <DropdownMenuItem
          className="text-red-600"
          onClick={(e) => onDelete(e, patient.id, patient.name)}
        >
          <Trash2 className="mr-2 h-4 w-4" />
          Excluir
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
