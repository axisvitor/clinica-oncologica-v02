import React from 'react'
import { Plus, FileText, AlertCircle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { LoadingOverlay } from '@/components/ui/loading-spinner'
import { QuestionarioCard } from './QuestionarioCard'
import { QuizTemplate } from '@/types/api'
import { QuestionariosFiltersConfig } from './QuestionariosFilters'

/**
 * Props for QuestionariosGrid component
 */
interface QuestionariosGridProps {
  /** Quiz templates data */
  templatesData?: {
    items: QuizTemplate[]
    total: number
    page: number
  }
  /** Loading state */
  isLoading: boolean
  /** Error state */
  error: Error | null
  /** Current filter values */
  filters: QuestionariosFiltersConfig
  /** Page size for pagination */
  pageSize: number
  /** Current page number */
  currentPage: number
  /** Handler for page changes */
  onPageChange: (page: number) => void
  /** Handler for delete action */
  onDelete: (id: string) => void
  /** Handler for edit action */
  onEdit: (template: QuizTemplate) => void
  /** Handler for create action */
  onCreate: () => void
  /** Handler for retry action */
  onRetry: () => void
}

/**
 * Grid component for displaying questionnaire templates
 * Handles loading states, error states, empty states, and pagination
 *
 * @component
 * @example
 * ```tsx
 * <QuestionariosGrid
 *   templatesData={data}
 *   isLoading={false}
 *   error={null}
 *   filters={filters}
 *   pageSize={12}
 *   currentPage={1}
 *   onPageChange={setCurrentPage}
 *   onDelete={handleDelete}
 *   onEdit={handleEdit}
 *   onCreate={handleCreate}
 *   onRetry={handleRetry}
 * />
 * ```
 */
export const QuestionariosGrid = React.memo<QuestionariosGridProps>(({
  templatesData,
  isLoading,
  error,
  filters,
  pageSize,
  currentPage,
  onPageChange,
  onDelete,
  onEdit,
  onCreate,
  onRetry
}) => {
  return (
    <LoadingOverlay isLoading={isLoading}>
      {error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Erro ao carregar questionários: {error?.message || 'Erro desconhecido'}
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="ml-4"
            >
              Tentar novamente
            </Button>
          </AlertDescription>
        </Alert>
      ) : (
        !templatesData?.items || templatesData.items.length === 0 ? (
          <Card className="p-6 text-center">
            <CardContent className="p-0">
              <FileText className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">
                {filters.search || filters.type !== 'all' || filters.status !== 'all'
                  ? 'Nenhum questionário encontrado com os filtros aplicados'
                  : 'Nenhum questionário criado ainda'
                }
              </h3>
              <p className="text-muted-foreground mb-6">
                {filters.search || filters.type !== 'all' || filters.status !== 'all'
                  ? 'Tente ajustar os filtros de busca.'
                  : 'Crie seu primeiro questionário para começar a coletar respostas dos pacientes.'
                }
              </p>
              {(!filters.search && filters.type === 'all' && filters.status === 'all') && (
                <Button onClick={onCreate}>
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Primeiro Questionário
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Templates Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
              {templatesData.items.map((template) => (
                <QuestionarioCard
                  key={template.id}
                  template={template}
                  onDelete={onDelete}
                  onEdit={onEdit}
                />
              ))}
            </div>

            {/* Pagination */}
            {templatesData && templatesData.total > pageSize && (
              <div className="flex justify-center mt-6 sm:mt-8">
                <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-0 sm:space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onPageChange(Math.max(1, currentPage - 1))}
                    disabled={currentPage === 1}
                    className="w-full sm:w-auto"
                  >
                    Anterior
                  </Button>
                  <span className="text-sm text-muted-foreground whitespace-nowrap px-2">
                    Página {currentPage} de {Math.ceil(templatesData.total / pageSize)}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onPageChange(currentPage + 1)}
                    disabled={currentPage >= Math.ceil(templatesData.total / pageSize)}
                    className="w-full sm:w-auto"
                  >
                    Próxima
                  </Button>
                </div>
              </div>
            )}
          </>
        )
      )}
    </LoadingOverlay>
  )
})

QuestionariosGrid.displayName = 'QuestionariosGrid'
