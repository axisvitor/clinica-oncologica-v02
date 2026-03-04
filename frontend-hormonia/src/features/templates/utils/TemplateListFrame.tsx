import React from 'react'
import { AlertTriangle, RefreshCw, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { TemplateCardSkeleton } from './TemplateCardSkeleton'

type TemplateListFrameProps = {
  error: string | null
  loading: boolean
  isEmpty: boolean
  emptyIcon: LucideIcon
  emptyMessage: string
  emptyActionLabel?: string
  onEmptyAction?: () => void
  onRefresh: () => void
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  children: React.ReactNode
  footer?: React.ReactNode
}

export function TemplateListFrame({
  error,
  loading,
  isEmpty,
  emptyIcon: EmptyIcon,
  emptyMessage,
  emptyActionLabel,
  onEmptyAction,
  onRefresh,
  page,
  totalPages,
  onPageChange,
  children,
  footer,
}: TemplateListFrameProps) {
  if (error) {
    return (
      <Card>
        <CardContent className="text-center py-12">
          <AlertTriangle className="h-12 w-12 mx-auto text-red-500 mb-4" />
          <p className="text-red-600 mb-4">{error}</p>
          <Button onClick={onRefresh} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Tentar Novamente
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <TemplateCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (isEmpty) {
    return (
      <Card>
        <CardContent className="text-center py-12">
          <EmptyIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">{emptyMessage}</p>
          {onEmptyAction && emptyActionLabel && (
            <Button onClick={onEmptyAction} className="mt-4">
              {emptyActionLabel}
            </Button>
          )}
        </CardContent>
      </Card>
    )
  }

  return (
    <>
      {children}

      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          <Button
            variant="outline"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page === 1}
          >
            Anterior
          </Button>
          <span className="flex items-center px-4">
            Página {page} de {totalPages}
          </span>
          <Button
            variant="outline"
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
          >
            Próxima
          </Button>
        </div>
      )}

      {footer}
    </>
  )
}
