/**
 * PatientsTable Component (Orchestrator)
 * Main table component that coordinates desktop/mobile views
 * Refactored from 617 lines to ~100 lines with modular architecture
 */

import React from 'react'
import { useNavigate } from 'react-router-dom'
import { FixedSizeList } from 'react-window'
import AutoSizer from 'react-virtualized-auto-sizer'
import { cn } from '@/lib/utils'
import { Pagination } from '@/components/ui/pagination'
import { SendQuizLinkModal } from '@/features/quiz/SendQuizLinkModal'
import { useResendQuizLink } from '@/hooks/useMonthlyQuizStatus'
import { PatientRow } from './components/PatientRow'
import { MobilePatientCard } from './components/MobilePatientCard'
import { usePatientActions } from './hooks/usePatientActions'
import { usePatientTable } from './hooks/usePatientTable'

import type { Patient } from '@/types/api'

interface PatientsTableProps {
  patients: Patient[]
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  onEditPatient?: (patient: Patient) => void
}

interface RowData {
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

const GRID_COLS = 'grid-cols-[2.5fr_1.5fr_1fr_1fr_1fr_0.8fr_1.2fr_70px]'

export function PatientsTable({
  patients,
  currentPage,
  totalPages,
  onPageChange,
  onEditPatient,
}: PatientsTableProps) {
  const navigate = useNavigate()
  const resendQuizLinkMutation = useResendQuizLink()

  const { handleDelete, handleActivate, handleDeactivate, confirmDeleteId, canDelete } =
    usePatientActions()

  const {
    selectedPatient,
    showSendQuizModal,
    handleSendQuiz,
    handleQuizSuccess,
    setShowSendQuizModal,
  } = usePatientTable()

  if (patients.length === 0) {
    return (
      <div className="text-center py-8" role="status" aria-live="polite" aria-atomic="true">
        <p className="text-gray-500">Nenhum paciente encontrado</p>
        <p className="text-sm text-gray-400 mt-1">
          Tente ajustar os filtros ou criar um novo paciente
        </p>
      </div>
    )
  }

  const itemData: RowData = {
    patients,
    onNavigate: (id) => navigate(`/patients/${id}`),
    onEdit: onEditPatient,
    onDelete: handleDelete,
    onActivate: handleActivate,
    onDeactivate: handleDeactivate,
    onSendQuiz: handleSendQuiz,
    confirmDeleteId,
    isResending: resendQuizLinkMutation.isPending,
    canDelete,
  }

  return (
    <div className="space-y-4 h-[calc(100dvh-220px)] min-h-[500px] flex flex-col">
      {/* Desktop Table - hidden on mobile */}
      <div className="hidden md:flex flex-1 flex-col overflow-hidden border md:rounded-lg">
        <div className={cn('grid bg-muted/50 font-medium text-sm border-b', GRID_COLS)}>
          <div className="px-4 py-3">Paciente</div>
          <div className="px-4 py-3">Contato</div>
          <div className="px-4 py-3">Tratamento</div>
          <div className="px-4 py-3">Status</div>
          <div className="px-4 py-3">Quiz Mensal</div>
          <div className="px-4 py-3">Dia Atual</div>
          <div className="px-4 py-3">Último Contato</div>
          <div className="px-4 py-3 w-[70px]">Ações</div>
        </div>

        <div className="flex-1">
          <AutoSizer>
            {({ height, width }) => (
              <FixedSizeList
                height={height}
                width={width}
                itemCount={patients.length}
                itemSize={80}
                itemData={itemData}
              >
                {PatientRow}
              </FixedSizeList>
            )}
          </AutoSizer>
        </div>
      </div>

      {/* Mobile Cards - hidden on desktop */}
      <div className="md:hidden flex-1">
        <AutoSizer>
          {({ height, width }) => (
            <FixedSizeList
              height={height}
              width={width}
              itemCount={patients.length}
              itemSize={300}
              itemData={itemData}
            >
              {MobilePatientCard}
            </FixedSizeList>
          )}
        </AutoSizer>
      </div>

      {totalPages > 1 && (
        <div className="pt-2">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={onPageChange}
          />
        </div>
      )}

      {/* Send Quiz Modal */}
      {selectedPatient && (
        <SendQuizLinkModal
          open={showSendQuizModal}
          onOpenChange={setShowSendQuizModal}
          patientId={selectedPatient.id}
          patientName={selectedPatient.name}
          onSuccess={handleQuizSuccess}
        />
      )}
    </div>
  )
}
