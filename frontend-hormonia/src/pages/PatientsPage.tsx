import React, { useEffect, useState } from 'react'
import { Plus, ListFilter as Filter, Grid2x2 as Grid, List } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { PatientsTable } from '@/features/patients/PatientsTable'
import { PatientsFilters } from '@/features/patients/PatientsFilters'
import { CreatePatientDialog, EditPatientDialog } from '@/features/patients/dialogs'
import { PatientStats } from '@/features/patients/PatientStats'
import { PatientCard } from '@/features/patients/PatientCard'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePatients, useTreatmentTypes } from '@/hooks/usePatients'
import type { PatientFilters } from '@/hooks/usePatients'
import type { Patient } from '@/types/api'

type ViewMode = 'table' | 'grid'
type PatientsTab = 'all' | 'active' | 'paused' | 'completed' | 'inactive'

type TabMeta = {
  label: string
  title: string
  description: string
  errorMessage: string
  countLabel: (total: number) => string
}

const TABS: PatientsTab[] = ['all', 'active', 'paused', 'completed', 'inactive']

const TAB_TO_STATUS: Record<PatientsTab, PatientFilters['status']> = {
  all: undefined,
  active: 'active',
  paused: 'paused',
  completed: 'completed',
  inactive: 'inactive'
}

const TAB_META: Record<PatientsTab, TabMeta> = {
  all: {
    label: 'Todos',
    title: 'Lista de Pacientes',
    description: 'Visualize e gerencie todos os pacientes cadastrados',
    errorMessage: 'Erro ao carregar pacientes',
    countLabel: (total) => `(${total} total)`
  },
  active: {
    label: 'Ativos',
    title: 'Pacientes Ativos',
    description: 'Pacientes em tratamento ativo',
    errorMessage: 'Erro ao carregar pacientes ativos',
    countLabel: (total) => `(${total} pacientes)`
  },
  paused: {
    label: 'Pausados',
    title: 'Pacientes Pausados',
    description: 'Pacientes com tratamento pausado',
    errorMessage: 'Erro ao carregar pacientes pausados',
    countLabel: (total) => `(${total} pacientes)`
  },
  completed: {
    label: 'Concluídos',
    title: 'Tratamentos Concluídos',
    description: 'Pacientes que concluíram o tratamento',
    errorMessage: 'Erro ao carregar tratamentos concluídos',
    countLabel: (total) => `(${total} pacientes)`
  },
  inactive: {
    label: 'Inativos',
    title: 'Pacientes Inativos',
    description: 'Pacientes com status inativo',
    errorMessage: 'Erro ao carregar pacientes inativos',
    countLabel: (total) => `(${total} pacientes)`
  }
}

const STATUS_LABEL: Record<Exclude<PatientsTab, 'all'>, string> = {
  active: 'Ativos',
  paused: 'Pausados',
  completed: 'Concluídos',
  inactive: 'Inativos'
}

const SKELETON_ROWS = Array.from({ length: 5 }, (_, i) => i)

function getTabFromStatus(status: PatientFilters['status']): PatientsTab {
  if (status === 'active') return 'active'
  if (status === 'paused') return 'paused'
  if (status === 'completed') return 'completed'
  if (status === 'inactive') return 'inactive'
  return 'all'
}

export function PatientsPage() {
  const navigate = useNavigate()
  const [viewMode, setViewMode] = useState<ViewMode>('table')
  const [activeTab, setActiveTab] = useState<PatientsTab>('all')
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [editingPatient, setEditingPatient] = useState<Patient | null>(null)
  const [showFilters, setShowFilters] = useState(false)

  const {
    patients,
    total,
    page,
    limit,
    isLoading,
    error,
    filters,
    activeFilterCount,
    updateFilter,
    updateFilters,
    refetch
  } = usePatients({
    pageSize: 20
  })

  const {
    data: treatmentTypes = [],
    isLoading: isLoadingTreatmentTypes
  } = useTreatmentTypes()

  useEffect(() => {
    const expectedTab = getTabFromStatus(filters.status)
    if (activeTab !== expectedTab) {
      setActiveTab(expectedTab)
    }
  }, [filters.status, activeTab])

  const handleTabChange = (value: string) => {
    const nextTab = (TABS.includes(value as PatientsTab) ? value : 'all') as PatientsTab
    setActiveTab(nextTab)

    updateFilter('status', TAB_TO_STATUS[nextTab])
    if (filters.page !== 1) {
      updateFilter('page', 1)
    }
  }

  const handleFiltersChange = (newFilters: PatientFilters) => {
    updateFilters(newFilters)
  }

  const totalPages = limit > 0 ? Math.ceil(total / limit) : 0

  const handlePageChange = (pageNum: number) => {
    updateFilter('page', pageNum)
  }

  const handleEditPatient = (patient: Patient) => {
    setEditingPatient(patient)
    setShowEditDialog(true)
  }

  const handleMessagePatient = (patient: Patient) => {
    navigate(`/messages?patient=${patient.id}`)
  }

  const renderContent = (errorMessage: string) => {
    if (isLoading) {
      return (
        <div className="space-y-4 p-4">
          {SKELETON_ROWS.map((row) => (
            <div key={row} className="flex items-center gap-4">
              <Skeleton className="h-10 w-10 rounded-full" />
              <div className="flex-1">
                <Skeleton className="h-4 w-32 mb-2" />
                <Skeleton className="h-3 w-24" />
              </div>
              <Skeleton className="h-5 w-16" />
            </div>
          ))}
        </div>
      )
    }

    if (error) {
      return (
        <div className="text-center py-8">
          <p className="text-red-600">{errorMessage}</p>
          <Button
            variant="outline"
            onClick={() => refetch()}
            className="mt-2"
          >
            Tentar novamente
          </Button>
        </div>
      )
    }

    if (viewMode === 'table') {
      return (
        <PatientsTable
          patients={patients}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={handlePageChange}
          onEditPatient={handleEditPatient}
        />
      )
    }

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {patients.map((patient: Patient) => (
          <PatientCard
            key={patient.id}
            patient={patient}
            onEdit={handleEditPatient}
            onMessage={handleMessagePatient}
          />
        ))}
      </div>
    )
  }

  const currentStatusLabel = activeTab !== 'all' ? STATUS_LABEL[activeTab] : null

  return (
    <div className="space-y-4 md:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900 truncate">
            Pacientes
            {currentStatusLabel && (
              <span className="text-base md:text-lg font-medium text-blue-600 ml-2">
                - {currentStatusLabel}
              </span>
            )}
          </h1>
          <p className="text-sm md:text-base text-gray-600 mt-1">
            {currentStatusLabel
              ? `Status: ${currentStatusLabel.toLowerCase()}`
              : 'Gerencie os pacientes'}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="flex items-center bg-muted rounded-md p-1 mr-2">
            <Button
              variant={viewMode === 'table' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setViewMode('table')}
            >
              <List className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => setViewMode('grid')}
            >
              <Grid className="h-4 w-4" />
            </Button>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="mr-1 md:mr-2 h-4 w-4" />
            <span className="hidden sm:inline">Filtros</span>
            {activeFilterCount > 0 && (
              <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-blue-600 rounded-full ml-2">
                {activeFilterCount}
              </span>
            )}
          </Button>
          <Button onClick={() => setShowCreateDialog(true)} size="sm">
            <Plus className="mr-1 md:mr-2 h-4 w-4" />
            <span className="hidden sm:inline">Novo Paciente</span>
            <span className="sm:hidden">Novo</span>
          </Button>
        </div>
      </div>

      {showFilters && (
        <Card>
          <CardContent className="pt-4 md:pt-6">
            <div className="flex items-center justify-between mb-3 md:mb-4">
              <h3 className="text-sm font-medium text-gray-900">
                Filtros
                {activeFilterCount > 0 && (
                  <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-blue-600 rounded-full ml-2">
                    {activeFilterCount}
                  </span>
                )}
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowFilters(false)}
                className="text-xs md:text-sm"
              >
                Ocultar
              </Button>
            </div>

            <PatientsFilters
              filters={filters}
              onFiltersChange={handleFiltersChange}
              treatmentTypes={treatmentTypes.map((t: string | { name?: string }) => (
                typeof t === 'string' ? t : (t?.name || String(t))
              ))}
              isLoadingTreatmentTypes={isLoadingTreatmentTypes}
              disabled={isLoading}
            />
          </CardContent>
        </Card>
      )}

      <PatientStats />

      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
        <TabsList>
          {TABS.map((tab) => (
            <TabsTrigger key={tab} value={tab}>{TAB_META[tab].label}</TabsTrigger>
          ))}
        </TabsList>

        {TABS.map((tab) => (
          <TabsContent key={tab} value={tab} className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>
                  {TAB_META[tab].title}
                  {activeTab === tab && (
                    <span className="text-sm font-normal text-gray-500 ml-2">
                      {TAB_META[tab].countLabel(total)}
                    </span>
                  )}
                </CardTitle>
                <CardDescription>
                  {TAB_META[tab].description}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {renderContent(TAB_META[tab].errorMessage)}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>

      <CreatePatientDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
      />

      <EditPatientDialog
        open={showEditDialog}
        onOpenChange={setShowEditDialog}
        patient={editingPatient}
      />
    </div>
  )
}
