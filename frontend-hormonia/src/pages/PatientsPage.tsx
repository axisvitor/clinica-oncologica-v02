import React, { useState, useEffect } from 'react'
import { Plus, ListFilter as Filter, Grid2x2 as Grid, List } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { PatientsTable } from '@/features/patients/PatientsTable'
import { PatientsFilters } from '@/features/patients/PatientsFilters'
import { CreatePatientDialog, EditPatientDialog } from '@/features/patients/dialogs'
import { PatientStats } from '@/features/patients/PatientStats'
import { PatientCard } from '@/features/patients/PatientCard'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePatients, useTreatmentTypes } from '@/hooks/usePatients'
import type { PatientFilters } from '@/hooks/usePatients'
import type { Patient } from '@/types/api'

export function PatientsPage() {
  const navigate = useNavigate()
  const [viewMode] = useState<'table' | 'grid'>('table')
  const [activeTab, setActiveTab] = useState('all')
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [editingPatient, setEditingPatient] = useState<Patient | null>(null)
  const [showFilters, setShowFilters] = useState(false)

  // Use the patients hook for data fetching and filter management
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

  // Fetch treatment types for filter dropdown
  const {
    data: treatmentTypes = [],
    isLoading: isLoadingTreatmentTypes
  } = useTreatmentTypes()

  // Calculate status filter based on active tab
  const getStatusFromTab = (tab: string): PatientFilters['status'] => {
    switch (tab) {
      case 'active': return 'active'
      case 'paused': return 'paused'
      case 'completed': return 'completed'
      case 'inactive': return 'inactive'
      default: return '' as any
    }
  }

  // Calculate tab based on status filter
  const getTabFromStatus = (status: PatientFilters['status']): string => {
    switch (status) {
      case 'active': return 'active'
      case 'paused': return 'paused'
      case 'completed': return 'completed'
      case 'inactive': return 'inactive'
      default: return 'all'
    }
  }

  // Sync active tab with status filter changes from other sources
  useEffect(() => {
    const expectedTab = getTabFromStatus(filters.status)
    if (activeTab !== expectedTab) {
      setActiveTab(expectedTab)
    }
  }, [filters.status, activeTab])

  // Handle tab changes by updating status filter
  const handleTabChange = (value: string) => {
    setActiveTab(value)
    const statusFromTab = getStatusFromTab(value)

    // Update status filter and reset page to 1
    updateFilter('status', statusFromTab)
    if (filters.page !== 1) {
      updateFilter('page', 1)
    }
  }

  // Handle filter changes from the PatientsFilters component
  const handleFiltersChange = (newFilters: PatientFilters) => {
    updateFilters(newFilters)
  }

  // Calculate total pages for pagination
  const totalPages = limit > 0 ? Math.ceil(total / limit) : 0

  const handlePageChange = (pageNum: number) => {
    updateFilter('page', pageNum)
  }

  const handleEditPatient = (patient: Patient) => {
    setEditingPatient(patient)
    setShowEditDialog(true)
  }

  const handleMessagePatient = (patient: Patient) => {
    // Navigate to messages page with patient selected
    navigate(`/messages?patient=${patient.id}`)
  }

  // Get current tab display name for better UX
  const getCurrentTabDisplayName = () => {
    switch (activeTab) {
      case 'active': return 'Ativos'
      case 'paused': return 'Pausados'
      case 'completed': return 'Concluídos'
      case 'inactive': return 'Inativos'
      default: return 'Todos'
    }
  }

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900 truncate">
            Pacientes
            {activeTab !== 'all' && (
              <span className="text-base md:text-lg font-medium text-blue-600 ml-2">
                - {getCurrentTabDisplayName()}
              </span>
            )}
          </h1>
          <p className="text-sm md:text-base text-gray-600 mt-1">
            {activeTab === 'all'
              ? 'Gerencie os pacientes'
              : `Status: ${getCurrentTabDisplayName().toLowerCase()}`
            }
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
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

      {/* Filters */}
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
              treatmentTypes={treatmentTypes.map((t: any) => typeof t === 'string' ? t : (t?.name || String(t)))}
              isLoadingTreatmentTypes={isLoadingTreatmentTypes}
              disabled={isLoading}
            />
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <PatientStats />

      {/* Patients Content */}
      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
        <TabsList>
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="active">Ativos</TabsTrigger>
          <TabsTrigger value="paused">Pausados</TabsTrigger>
          <TabsTrigger value="completed">Concluídos</TabsTrigger>
          <TabsTrigger value="inactive">Inativos</TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                Lista de Pacientes
                <span className="text-sm font-normal text-gray-500 ml-2">
                  ({total} total)
                </span>
              </CardTitle>
              <CardDescription>
                Visualize e gerencie todos os pacientes cadastrados
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="lg" />
                </div>
              ) : error ? (
                <div className="text-center py-8">
                  <p className="text-red-600">Erro ao carregar pacientes</p>
                  <Button
                    variant="outline"
                    onClick={() => refetch()}
                    className="mt-2"
                  >
                    Tentar novamente
                  </Button>
                </div>
              ) : viewMode === 'table' ? (
                <PatientsTable
                  patients={patients}
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                  onEditPatient={handleEditPatient}
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {patients.map((patient) => (
                    <PatientCard
                      key={patient.id}
                      patient={patient}
                      onEdit={handleEditPatient}
                      onMessage={handleMessagePatient}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="active" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                Pacientes Ativos
                {activeTab === 'active' && (
                  <span className="text-sm font-normal text-gray-500 ml-2">
                    ({total} pacientes)
                  </span>
                )}
              </CardTitle>
              <CardDescription>
                Pacientes em tratamento ativo
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="lg" />
                </div>
              ) : error ? (
                <div className="text-center py-8">
                  <p className="text-red-600">Erro ao carregar pacientes ativos</p>
                  <Button
                    variant="outline"
                    onClick={() => refetch()}
                    className="mt-2"
                  >
                    Tentar novamente
                  </Button>
                </div>
              ) : viewMode === 'table' ? (
                <PatientsTable
                  patients={patients}
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                  onEditPatient={handleEditPatient}
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {patients.map((patient) => (
                    <PatientCard
                      key={patient.id}
                      patient={patient}
                      onEdit={handleEditPatient}
                      onMessage={handleMessagePatient}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="paused" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                Pacientes Pausados
                {activeTab === 'paused' && (
                  <span className="text-sm font-normal text-gray-500 ml-2">
                    ({total} pacientes)
                  </span>
                )}
              </CardTitle>
              <CardDescription>
                Pacientes com tratamento pausado
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="lg" />
                </div>
              ) : error ? (
                <div className="text-center py-8">
                  <p className="text-red-600">Erro ao carregar pacientes pausados</p>
                  <Button
                    variant="outline"
                    onClick={() => refetch()}
                    className="mt-2"
                  >
                    Tentar novamente
                  </Button>
                </div>
              ) : viewMode === 'table' ? (
                <PatientsTable
                  patients={patients}
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                  onEditPatient={handleEditPatient}
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {patients.map((patient) => (
                    <PatientCard
                      key={patient.id}
                      patient={patient}
                      onEdit={handleEditPatient}
                      onMessage={handleMessagePatient}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="completed" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                Tratamentos Concluídos
                {activeTab === 'completed' && (
                  <span className="text-sm font-normal text-gray-500 ml-2">
                    ({total} pacientes)
                  </span>
                )}
              </CardTitle>
              <CardDescription>
                Pacientes que concluíram o tratamento
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="lg" />
                </div>
              ) : error ? (
                <div className="text-center py-8">
                  <p className="text-red-600">Erro ao carregar tratamentos concluídos</p>
                  <Button
                    variant="outline"
                    onClick={() => refetch()}
                    className="mt-2"
                  >
                    Tentar novamente
                  </Button>
                </div>
              ) : viewMode === 'table' ? (
                <PatientsTable
                  patients={patients}
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                  onEditPatient={handleEditPatient}
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {patients.map((patient) => (
                    <PatientCard
                      key={patient.id}
                      patient={patient}
                      onEdit={handleEditPatient}
                      onMessage={handleMessagePatient}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="inactive" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                Pacientes Inativos
                {activeTab === 'inactive' && (
                  <span className="text-sm font-normal text-gray-500 ml-2">
                    ({total} pacientes)
                  </span>
                )}
              </CardTitle>
              <CardDescription>
                Pacientes com status inativo
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="lg" />
                </div>
              ) : error ? (
                <div className="text-center py-8">
                  <p className="text-red-600">Erro ao carregar pacientes inativos</p>
                  <Button
                    variant="outline"
                    onClick={() => refetch()}
                    className="mt-2"
                  >
                    Tentar novamente
                  </Button>
                </div>
              ) : viewMode === 'table' ? (
                <PatientsTable
                  patients={patients}
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                  onEditPatient={handleEditPatient}
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {patients.map((patient) => (
                    <PatientCard
                      key={patient.id}
                      patient={patient}
                      onEdit={handleEditPatient}
                      onMessage={handleMessagePatient}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
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

