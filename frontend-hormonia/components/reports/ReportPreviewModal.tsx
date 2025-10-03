import React from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface ReportPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  report: {
    id: string
    title: string
    content: string
    type: string
  } | null
}

export function ReportPreviewModal({ isOpen, onClose, report }: ReportPreviewModalProps) {
  if (!report) return null

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>{report.title}</DialogTitle>
        </DialogHeader>
        <div className="mt-4">
          <div className="bg-gray-50 p-4 rounded-lg">
            <h3 className="font-semibold mb-2">Tipo: {report.type}</h3>
            <div className="whitespace-pre-wrap">{report.content}</div>
          </div>
          <div className="mt-6 flex justify-end space-x-2">
            <Button variant="outline" onClick={onClose}>
              Fechar
            </Button>
            <Button onClick={() => window.print()}>
              Imprimir
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}