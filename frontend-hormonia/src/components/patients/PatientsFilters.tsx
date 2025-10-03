import React, { useState, useEffect } from 'react'
import { Search, X, Calendar, Filter } from 'lucide-react'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { DateRange } from 'react-day-picker'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Calendar as CalendarComponent } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import type { PatientFilters } from '@/hooks/usePatients'

interface PatientsFiltersProps {
  filters: PatientFilters
  onFiltersChange: (filters: PatientFilters) => void
  treatmentTypes?: string[]
  isLoadingTreatmentTypes?: boolean
  disabled?: boolean
}

export function PatientsFilters({
  filters,
  onFiltersChange,
  treatmentTypes = [],
  isLoadingTreatmentTypes = false,
  disabled = false
}: PatientsFiltersProps) {
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined)

  // Initialize date range from filters
  useEffect(() => {
    if (filters.start_date_from || filters.start_date_to) {
      const newDateRange: DateRange = {
        from: filters.start_date_from ? new Date(filters.start_date_from) : undefined,
        to: filters.start_date_to ? new Date(filters.start_date_to) : undefined
      }
      setDateRange(newDateRange)
    } else {
      setDateRange(undefined)
    }
  }, [filters.start_date_from, filters.start_date_to])

  // Calculate active filters
  const hasActiveFilters = Boolean(
    filters.search ||
    filters.status ||
    filters.treatment_type ||
    filters.start_date_from ||
    filters.start_date_to
  )

  const activeFilterCount = [
    filters.search,
    filters.status,
    filters.treatment_type,
    filters.start_date_from || filters.start_date_to
  ].filter(Boolean).length

  const updateFilter = (key: keyof PatientFilters, value: any) => {
    onFiltersChange({
      ...filters,
      [key]: value,
      // Reset page when filters change
      page: key === 'page' ? value : 1
    })
  }

  const resetFilters = () => {
    setDateRange(undefined)
    const resetFiltersObj: PatientFilters = {
      search: '',
      treatment_type: '',
      start_date_from: '',
      start_date_to: '',
      page: 1,
      ...(filters.size !== undefined && { size: filters.size })
    }
    onFiltersChange(resetFiltersObj)
  }

  const handleSearchChange = (value: string) => {
    updateFilter('search', value)
  }

  const handleStatusChange = (value: string) => {
    updateFilter('status', value === 'all' ? undefined : value as any)
  }

  const handleTreatmentTypeChange = (value: string) => {
    updateFilter('treatment_type', value === 'all' ? '' : value)
  }

  const handleDateRangeChange = (range: DateRange | undefined) => {
    setDateRange(range)
    updateFilter('start_date_from', range?.from ? format(range.from, 'yyyy-MM-dd') : '')
    updateFilter('start_date_to', range?.to ? format(range.to, 'yyyy-MM-dd') : '')
  }

  const clearDateRange = () => {
    setDateRange(undefined)
    onFiltersChange({
      ...filters,
      start_date_from: '',
      start_date_to: '',
      page: 1
    })
  }

  const getStatusLabel = (status: string) => {
    const statusLabels = {
      active: 'Ativo',
      paused: 'Pausado',
      completed: 'Concluído',
      inactive: 'Inativo'
    }
    return statusLabels[status as keyof typeof statusLabels] || status
  }

  return (
    <div className="space-y-4">
      {/* Header with title and clear button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-600" />
          <h3 className="text-sm font-medium text-gray-900">Filtros</h3>
          {activeFilterCount > 0 && (
            <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-blue-600 rounded-full">
              {activeFilterCount}
            </span>
          )}
        </div>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={resetFilters}
            disabled={disabled}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="mr-1 h-3 w-3" />
            Limpar filtros
          </Button>
        )}
      </div>

      {/* Search input */}
      <div className="space-y-2">
        <Label htmlFor="search-input">Buscar pacientes</Label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            id="search-input"
            type="text"
            placeholder="Nome, email ou telefone..."
            value={filters.search || ''}
            onChange={(e) => handleSearchChange(e.target.value)}
            disabled={disabled}
            className="pl-10"
          />
        </div>
      </div>

      {/* Filter controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Status filter */}
        <div className="space-y-2">
          <Label htmlFor="status-filter">Status</Label>
          <Select
            value={filters.status || 'all'}
            onValueChange={handleStatusChange}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue placeholder="Todos os status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os status</SelectItem>
              <SelectItem value="active">Ativo</SelectItem>
              <SelectItem value="paused">Pausado</SelectItem>
              <SelectItem value="completed">Concluído</SelectItem>
              <SelectItem value="inactive">Inativo</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Treatment type filter */}
        <div className="space-y-2">
          <Label htmlFor="treatment-filter">Tipo de Tratamento</Label>
          <Select
            value={filters.treatment_type || 'all'}
            onValueChange={handleTreatmentTypeChange}
            disabled={disabled || isLoadingTreatmentTypes}
          >
            <SelectTrigger>
              <SelectValue placeholder="Todos os tratamentos" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os tratamentos</SelectItem>
              {treatmentTypes?.map((type) => (
                <SelectItem key={type} value={type}>
                  {type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Start date range filter */}
        <div className="space-y-2">
          <Label>Data de Início do Tratamento</Label>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                disabled={disabled}
                className={cn(
                  "w-full justify-start text-left font-normal",
                  !dateRange?.from && "text-muted-foreground"
                )}
              >
                <Calendar className="mr-2 h-4 w-4" />
                {dateRange?.from ? (
                  dateRange?.to ? (
                    <>
                      {format(dateRange.from, "dd/MM/yyyy", { locale: ptBR })} -{" "}
                      {format(dateRange.to, "dd/MM/yyyy", { locale: ptBR })}
                    </>
                  ) : (
                    format(dateRange.from, "dd/MM/yyyy", { locale: ptBR })
                  )
                ) : (
                  "Selecionar período"
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <CalendarComponent
                initialFocus
                mode="range"
                {...(dateRange?.from && { defaultMonth: dateRange.from })}
                selected={dateRange}
                onSelect={handleDateRangeChange}
                numberOfMonths={2}
                locale={ptBR}
              />
              {(dateRange?.from || dateRange?.to) && (
                <div className="p-3 border-t">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearDateRange}
                    disabled={disabled}
                    className="w-full"
                  >
                    Limpar período
                  </Button>
                </div>
              )}
            </PopoverContent>
          </Popover>
        </div>

      </div>

      {/* Active filters display */}
      {hasActiveFilters && (
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t">
          <span className="text-sm text-gray-600">Filtros ativos:</span>

          {filters.search && (
            <div className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-md text-sm">
              <Search className="h-3 w-3" />
              <span>"{filters.search}"</span>
              <button
                onClick={() => updateFilter('search', '')}
                disabled={disabled}
                className="ml-1 hover:bg-blue-200 rounded disabled:opacity-50"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          {filters.status && (
            <div className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 rounded-md text-sm">
              <span>Status: {getStatusLabel(filters.status)}</span>
              <button
                onClick={() => updateFilter('status', '')}
                disabled={disabled}
                className="ml-1 hover:bg-green-200 rounded disabled:opacity-50"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          {filters.treatment_type && (
            <div className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-800 rounded-md text-sm">
              <span>Tratamento: {filters.treatment_type}</span>
              <button
                onClick={() => updateFilter('treatment_type', '')}
                disabled={disabled}
                className="ml-1 hover:bg-purple-200 rounded disabled:opacity-50"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          {(dateRange?.from || dateRange?.to) && (
            <div className="inline-flex items-center gap-1 px-2 py-1 bg-orange-100 text-orange-800 rounded-md text-sm">
              <Calendar className="h-3 w-3" />
              <span>
                {dateRange?.from && dateRange?.to ? (
                  `${format(dateRange.from, "dd/MM/yy")} - ${format(dateRange.to, "dd/MM/yy")}`
                ) : dateRange?.from ? (
                  `A partir de ${format(dateRange.from, "dd/MM/yy")}`
                ) : dateRange?.to ? (
                  `Até ${format(dateRange.to, "dd/MM/yy")}`
                ) : (
                  'Data'
                )}
              </span>
              <button
                onClick={clearDateRange}
                disabled={disabled}
                className="ml-1 hover:bg-orange-200 rounded disabled:opacity-50"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>
      )}

    </div>
  )
}
