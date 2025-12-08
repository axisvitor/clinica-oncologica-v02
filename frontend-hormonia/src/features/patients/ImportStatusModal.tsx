/**
 * Import Status Modal Component
 *
 * Modal dialog that displays:
 * - Upload progress
 * - Validation results with row-level errors
 * - Import progress (X of Y patients)
 * - Success/error summary
 * - Detailed error list
 */

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  Download,
  FileText,
} from 'lucide-react';
import type { ValidationResult, ImportResult } from '@/types/import';

interface ImportStatusModalProps {
  open: boolean;
  onClose: () => void;
  validating: boolean;
  importing: boolean;
  progress: number;
  validationResult: ValidationResult | null;
  importResult: ImportResult | null;
  error: string | null;
  onProceed?: () => void;
  onDownloadErrors?: () => void;
}

export function ImportStatusModal({
  open,
  onClose,
  validating,
  importing,
  progress,
  validationResult,
  importResult,
  error,
  onProceed,
  onDownloadErrors,
}: ImportStatusModalProps) {
  // Determine modal state
  const isProcessing = validating || importing;
  const hasValidationErrors = validationResult && !validationResult.valid;
  const hasImportErrors = importResult && importResult.failed > 0;
  const isSuccess = importResult && importResult.successful > 0;

  return (
    <Dialog open={open} onOpenChange={(open) => !open && !isProcessing && onClose()}>
      <DialogContent className="w-[95vw] max-w-2xl max-h-[80vh] flex flex-col px-4 sm:px-6">
        <DialogHeader>
          <DialogTitle>
            {validating && 'Validando arquivo...'}
            {importing && 'Importando pacientes...'}
            {validationResult && !importing && 'Resultado da validação'}
            {importResult && 'Resultado da importação'}
            {error && 'Erro na importação'}
          </DialogTitle>
          <DialogDescription>
            {validating && 'Verificando o arquivo antes da importação'}
            {importing && 'Processando os dados dos pacientes'}
            {validationResult && !importing && 'Revise os erros antes de prosseguir'}
            {importResult && 'Importação concluída'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col space-y-4">
          {/* Progress bar */}
          {isProcessing && (
            <div className="space-y-2">
              <Progress value={progress} className="w-full" />
              <p className="text-sm text-muted-foreground text-center">
                {progress}% concluído
              </p>
            </div>
          )}

          {/* Error message */}
          {error && (
            <Alert variant="destructive">
              <XCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Validation results */}
          {validationResult && !importing && (
            <div className="space-y-4 flex-1 overflow-hidden flex flex-col">
              {/* Summary */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-secondary p-3 rounded-lg">
                  <p className="text-sm font-medium">Total de linhas</p>
                  <p className="text-2xl font-bold">{validationResult.totalRows}</p>
                </div>
                <div className="bg-secondary p-3 rounded-lg">
                  <p className="text-sm font-medium">Linhas válidas</p>
                  <p className="text-2xl font-bold text-green-600">
                    {validationResult.validRows}
                  </p>
                </div>
                <div className="bg-secondary p-3 rounded-lg">
                  <p className="text-sm font-medium">Erros</p>
                  <p className="text-2xl font-bold text-red-600">
                    {validationResult.errorRows}
                  </p>
                </div>
                <div className="bg-secondary p-3 rounded-lg">
                  <p className="text-sm font-medium">Avisos</p>
                  <p className="text-2xl font-bold text-yellow-600">
                    {validationResult.warningRows}
                  </p>
                </div>
              </div>

              {/* Errors and warnings */}
              {(validationResult.errors.length > 0 || validationResult.warnings.length > 0) && (
                <ScrollArea className="flex-1 border rounded-lg p-4">
                  <div className="space-y-2">
                    {/* Errors */}
                    {validationResult.errors.map((error, index) => (
                      <div key={`error-${index}`} className="flex items-start gap-2 p-2 bg-red-50 rounded">
                        <XCircle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="text-sm font-medium">
                            Linha {error.row}
                            {error.column && ` - Coluna: ${error.column}`}
                          </p>
                          <p className="text-sm text-red-700">{error.message}</p>
                        </div>
                      </div>
                    ))}

                    {/* Warnings */}
                    {validationResult.warnings.map((warning, index) => (
                      <div key={`warning-${index}`} className="flex items-start gap-2 p-2 bg-yellow-50 rounded">
                        <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="text-sm font-medium">
                            Linha {warning.row}
                            {warning.column && ` - Coluna: ${warning.column}`}
                          </p>
                          <p className="text-sm text-yellow-700">{warning.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}

              {/* Preview */}
              {validationResult.valid && validationResult.preview.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium">Prévia dos primeiros pacientes:</h4>
                  <ScrollArea className="h-32 border rounded-lg p-2">
                    {validationResult.preview.map((patient, index) => (
                      <div key={index} className="text-sm p-2 hover:bg-secondary rounded">
                        <span className="font-medium">{patient.name}</span>
                        {patient.email && <span className="text-muted-foreground ml-2">({patient.email})</span>}
                      </div>
                    ))}
                  </ScrollArea>
                </div>
              )}
            </div>
          )}

          {/* Import results */}
          {importResult && (
            <div className="space-y-4 flex-1 overflow-hidden flex flex-col">
              {/* Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-secondary p-3 rounded-lg">
                  <p className="text-sm font-medium">Total processado</p>
                  <p className="text-2xl font-bold">{importResult.total}</p>
                </div>
                <div className="bg-green-50 p-3 rounded-lg">
                  <p className="text-sm font-medium">Importados</p>
                  <p className="text-2xl font-bold text-green-600">
                    {importResult.successful}
                  </p>
                </div>
                <div className="bg-red-50 p-3 rounded-lg">
                  <p className="text-sm font-medium">Falhas</p>
                  <p className="text-2xl font-bold text-red-600">
                    {importResult.failed}
                  </p>
                </div>
                <div className="bg-blue-50 p-3 rounded-lg">
                  <p className="text-sm font-medium">Ignorados</p>
                  <p className="text-2xl font-bold text-blue-600">
                    {importResult.skipped}
                  </p>
                </div>
              </div>

              {/* Success message */}
              {isSuccess && importResult.failed === 0 && (
                <Alert className="bg-green-50 border-green-200">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <AlertDescription className="text-green-700">
                    Importação concluída com sucesso! {importResult.successful} paciente(s) importado(s).
                  </AlertDescription>
                </Alert>
              )}

              {/* Partial success */}
              {isSuccess && importResult.failed > 0 && (
                <Alert className="bg-yellow-50 border-yellow-200">
                  <AlertTriangle className="h-4 w-4 text-yellow-600" />
                  <AlertDescription className="text-yellow-700">
                    Importação parcial: {importResult.successful} importado(s), {importResult.failed} falharam.
                  </AlertDescription>
                </Alert>
              )}

              {/* Errors */}
              {importResult.errors.length > 0 && (
                <ScrollArea className="flex-1 border rounded-lg p-4">
                  <div className="space-y-2">
                    {importResult.errors.map((error, index) => (
                      <div key={index} className="flex items-start gap-2 p-2 bg-red-50 rounded">
                        <XCircle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="text-sm font-medium">
                            Linha {error.row}
                            {error.patientName && ` - ${error.patientName}`}
                          </p>
                          <p className="text-sm text-red-700">{error.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row justify-between gap-2 sm:gap-0 pt-4 border-t">
          <div>
            {hasImportErrors && onDownloadErrors && (
              <Button variant="outline" onClick={onDownloadErrors} size="sm" className="w-full sm:w-auto">
                <Download className="h-4 w-4 mr-2" />
                Baixar erros
              </Button>
            )}
          </div>
          <div className="flex flex-col-reverse sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={isProcessing}
              className="w-full sm:w-auto"
            >
              {importResult ? 'Fechar' : 'Cancelar'}
            </Button>
            {validationResult && validationResult.valid && !importResult && onProceed && (
              <Button onClick={onProceed} disabled={isProcessing} className="w-full sm:w-auto">
                {importing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Importando...
                  </>
                ) : (
                  'Prosseguir com importação'
                )}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
