import React from 'react'
import { ChevronLeft, ChevronRight, MoreHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface PaginationProps {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  className?: string
  isLoading?: boolean
  hasMore?: boolean
  total?: number
  pageSize?: number
}

export function Pagination({ 
  currentPage, 
  totalPages, 
  onPageChange, 
  className 
}: PaginationProps) {
  const generatePageNumbers = () => {
    const pages: (number | string)[] = []
    const showEllipsis = totalPages > 7

    if (!showEllipsis) {
      // Show all pages if 7 or fewer
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      // Always show first page
      pages.push(1)

      if (currentPage <= 4) {
        // Show pages 2-5 and ellipsis
        for (let i = 2; i <= 5; i++) {
          pages.push(i)
        }
        pages.push('ellipsis')
      } else if (currentPage >= totalPages - 3) {
        // Show ellipsis and last 4 pages
        pages.push('ellipsis')
        for (let i = totalPages - 4; i <= totalPages - 1; i++) {
          pages.push(i)
        }
      } else {
        // Show ellipsis, current page area, ellipsis
        pages.push('ellipsis')
        for (let i = currentPage - 1; i <= currentPage + 1; i++) {
          pages.push(i)
        }
        pages.push('ellipsis')
      }

      // Always show last page (if not already shown)
      if (totalPages > 1) {
        pages.push(totalPages)
      }
    }

    return pages
  }

  if (totalPages <= 1) {
    return null
  }

  const pages = generatePageNumbers()

  return (
    <nav aria-label="Paginacao" className={cn('flex items-center justify-center space-x-1', className)}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        aria-label="Pagina anterior"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Anterior
      </Button>

      {pages.map((page, index) => {
        if (page === 'ellipsis') {
          return (
            <div key={`ellipsis-${index}`} className="px-2" aria-hidden="true">
              <MoreHorizontal className="h-4 w-4 text-gray-400" />
            </div>
          )
        }

        const pageNumber = page as number
        const isCurrentPage = pageNumber === currentPage

        return (
          <Button
            key={pageNumber}
            variant={isCurrentPage ? 'default' : 'outline'}
            size="sm"
            onClick={() => onPageChange(pageNumber)}
            aria-label={`Pagina ${pageNumber}`}
            aria-current={isCurrentPage ? 'page' : undefined}
            className={cn(
              'min-w-[40px]',
              isCurrentPage && 'bg-primary text-primary-foreground hover:bg-primary/90'
            )}
          >
            {pageNumber}
          </Button>
        )
      })}

      <Button
        variant="outline"
        size="sm"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        aria-label="Proxima pagina"
      >
        Proxima
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </Button>
    </nav>
  )
}
