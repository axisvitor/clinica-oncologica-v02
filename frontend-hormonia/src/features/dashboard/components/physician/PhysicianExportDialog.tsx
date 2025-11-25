import React from 'react'
import { FileText, Download } from 'lucide-react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface PhysicianExportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onExport: (format: 'pdf' | 'excel') => void
  isPending: boolean
}

export function PhysicianExportDialog({
  open,
  onOpenChange,
  onExport,
  isPending
}: PhysicianExportDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Exportar Relatório
          </DialogTitle>
          <DialogDescription>
            Escolha o formato do relatório para exportação
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            O relatório incluirá todos os pacientes filtrados, insights e recomendações de IA.
          </p>
          <div className="flex gap-3">
            <Button
              className="flex-1"
              variant="outline"
              onClick={() => onExport('pdf')}
              disabled={isPending}
            >
              <FileText className="h-4 w-4 mr-2" />
              PDF
            </Button>
            <Button
              className="flex-1"
              variant="outline"
              onClick={() => onExport('excel')}
              disabled={isPending}
            >
              <Download className="h-4 w-4 mr-2" />
              Excel
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
