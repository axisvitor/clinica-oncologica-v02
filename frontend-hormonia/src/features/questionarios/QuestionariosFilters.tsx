import React from 'react'
import { Search } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

/**
 * Filter configuration interface
 */
export interface QuestionariosFiltersConfig {
  search: string
  type: 'all' | 'medical' | 'wellness'
  status: 'all' | 'active' | 'inactive'
  sortBy: 'created_at' | 'name' | 'responses'
  sortOrder: 'asc' | 'desc'
}

/**
 * Props for QuestionariosFilters component
 */
interface QuestionariosFiltersProps {
  /** Current filter values */
  filters: QuestionariosFiltersConfig
  /** Handler for search input changes */
  onSearchChange: (value: string) => void
  /** Handler for filter changes */
  onFilterChange: <K extends keyof QuestionariosFiltersConfig>(
    key: K,
    value: QuestionariosFiltersConfig[K]
  ) => void
}

/**
 * Filters and search component for questionnaires
 * Provides search input and filter controls for type, status, and sorting
 *
 * @component
 * @example
 * ```tsx
 * <QuestionariosFilters
 *   filters={filters}
 *   onSearchChange={handleSearch}
 *   onFilterChange={handleFilterChange}
 * />
 * ```
 */
export const QuestionariosFilters = React.memo<QuestionariosFiltersProps>(({
  filters,
  onSearchChange,
  onFilterChange
}) => {
  return (
    <Card className="mb-6">
      <CardContent className="p-4 sm:p-6">
        <div className="flex flex-col gap-3 sm:gap-4">
          {/* Search */}
          <div className="w-full">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar questionários..."
                value={filters.search}
                onChange={(e) => onSearchChange(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          {/* Filters */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Select
              value={filters.type}
              onValueChange={(value: 'all' | 'medical' | 'wellness') => onFilterChange('type', value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Tipo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os tipos</SelectItem>
                <SelectItem value="medical">Médico</SelectItem>
                <SelectItem value="wellness">Bem-estar</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={filters.status}
              onValueChange={(value: 'all' | 'active' | 'inactive') => onFilterChange('status', value)}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="active">Ativos</SelectItem>
                <SelectItem value="inactive">Inativos</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={`${filters.sortBy}-${filters.sortOrder}`}
              onValueChange={(value) => {
                const [sortBy, sortOrder] = value.split('-') as [
                  'created_at' | 'name' | 'responses',
                  'asc' | 'desc'
                ]
                onFilterChange('sortBy', sortBy)
                onFilterChange('sortOrder', sortOrder)
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Ordenar por" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="created_at-desc">Mais recentes</SelectItem>
                <SelectItem value="created_at-asc">Mais antigos</SelectItem>
                <SelectItem value="name-asc">Nome A-Z</SelectItem>
                <SelectItem value="name-desc">Nome Z-A</SelectItem>
                <SelectItem value="responses-desc">Mais respostas</SelectItem>
                <SelectItem value="responses-asc">Menos respostas</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardContent>
    </Card>
  )
})

QuestionariosFilters.displayName = 'QuestionariosFilters'
