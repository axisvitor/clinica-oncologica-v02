import React from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogTrigger } from '@/components/ui/dialog'

/**
 * Props for QuestionariosHeader component
 */
interface QuestionariosHeaderProps {
  /** Whether the create dialog is open */
  isCreateDialogOpen: boolean
  /** Handler for create dialog state changes */
  onCreateDialogChange: (open: boolean) => void
}

/**
 * Header component for Questionarios page with title and create button
 *
 * @component
 * @example
 * ```tsx
 * <QuestionariosHeader
 *   isCreateDialogOpen={false}
 *   onCreateDialogChange={setIsCreateDialogOpen}
 * />
 * ```
 */
export const QuestionariosHeader = React.memo<QuestionariosHeaderProps>(({
  isCreateDialogOpen,
  onCreateDialogChange
}) => {
  return (
    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-4 mb-6 sm:mb-8">
      <div className="flex-1">
        <h1 className="text-2xl sm:text-3xl font-bold">Questionários</h1>
        <p className="text-sm sm:text-base text-muted-foreground mt-1">
          Gerencie questionários médicos e de bem-estar para seus pacientes
        </p>
      </div>
      <Dialog open={isCreateDialogOpen} onOpenChange={onCreateDialogChange}>
        <DialogTrigger asChild>
          <Button className="w-full sm:w-auto">
            <Plus className="h-4 w-4 mr-2" />
            <span className="hidden sm:inline">Novo Questionário</span>
            <span className="sm:hidden">Novo</span>
          </Button>
        </DialogTrigger>
      </Dialog>
    </div>
  )
})

QuestionariosHeader.displayName = 'QuestionariosHeader'
