/**
 * Patient Import Page
 *
 * Provides UI for importing patients from CSV/Excel files:
 * - File upload with drag-and-drop
 * - Real-time validation
 * - Import progress tracking
 * - Import history
 * - Template download
 *
 * RBAC: Admin and Doctor roles only
 */

import React, { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Upload,
  Download,
  FileSpreadsheet,
  History,
  AlertCircle,
  CheckCircle,
  XCircle,
  FileText,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ImportStatusModal } from '@/features/patients/ImportStatusModal';
import { usePatientImport } from '@/hooks/usePatientImport';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api-client';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import type { ImportOptions } from '@/types/import';

export function PatientImport() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Import hook
  const {
    validating,
    importing,
    progress,
    validationResult,
    importResult,
    error,
    validateFile,
    importFile,
    downloadTemplate,
    reset,
  } = usePatientImport();

  // Local state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [importOptions, setImportOptions] = useState<ImportOptions>({
    skipDuplicates: true,
    updateExisting: false,
    validateOnly: false,
  });
  const [dragActive, setDragActive] = useState(false);

  // Import history query
  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['patient-import-history'],
    queryFn: () => apiClient.patients.getImportHistory({ page: 1, size: 10 }),
  });

  /**
   * Handle file selection
   */
  const handleFileSelect = useCallback((file: File) => {
    setSelectedFile(file);
    reset();
  }, [reset]);

  /**
   * Handle file input change
   */
  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) {
        handleFileSelect(file);
      }
    },
    [handleFileSelect]
  );

  /**
   * Handle drag and drop
   */
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);

      const file = e.dataTransfer.files?.[0];
      if (file) {
        handleFileSelect(file);
      }
    },
    [handleFileSelect]
  );

  /**
   * Validate selected file
   */
  const handleValidate = useCallback(async () => {
    if (!selectedFile) {
      toast({
        title: 'Nenhum arquivo selecionado',
        description: 'Por favor, selecione um arquivo CSV ou Excel.',
        variant: 'destructive',
      });
      return;
    }

    setShowModal(true);
    const result = await validateFile(selectedFile);

    if (result && !result.valid) {
      toast({
        title: 'Arquivo com erros',
        description: `Foram encontrados ${result.errorRows} erro(s). Corrija antes de importar.`,
        variant: 'destructive',
      });
    } else if (result && result.valid) {
      toast({
        title: 'Validação concluída',
        description: `${result.validRows} paciente(s) pronto(s) para importação.`,
      });
    }
  }, [selectedFile, validateFile, toast]);

  /**
   * Import patients
   */
  const handleImport = useCallback(async () => {
    if (!selectedFile) return;

    const result = await importFile(selectedFile, importOptions);

    if (result) {
      if (result.successful > 0 && result.failed === 0) {
        toast({
          title: 'Importação concluída',
          description: `${result.successful} paciente(s) importado(s) com sucesso!`,
        });
        // Refresh patient list
        queryClient.invalidateQueries({ queryKey: ['patients'] });
        queryClient.invalidateQueries({ queryKey: ['patient-import-history'] });
      } else if (result.successful > 0 && result.failed > 0) {
        toast({
          title: 'Importação parcial',
          description: `${result.successful} importado(s), ${result.failed} falharam.`,
          variant: 'destructive',
        });
        queryClient.invalidateQueries({ queryKey: ['patient-import-history'] });
      } else {
        toast({
          title: 'Falha na importação',
          description: 'Nenhum paciente foi importado. Verifique os erros.',
          variant: 'destructive',
        });
      }
    }
  }, [selectedFile, importFile, importOptions, toast, queryClient]);

  /**
   * Download template
   */
  const handleDownloadTemplate = useCallback(
    async (format: 'csv' | 'xlsx') => {
      try {
        await downloadTemplate(format);
        toast({
          title: 'Modelo baixado',
          description: `Modelo de importação baixado no formato ${format.toUpperCase()}.`,
        });
      } catch (err) {
        toast({
          title: 'Erro ao baixar modelo',
          description: 'Não foi possível baixar o modelo. Tente novamente.',
          variant: 'destructive',
        });
      }
    },
    [downloadTemplate, toast]
  );

  /**
   * Get status badge for history entry
   */
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-500">Concluído</Badge>;
      case 'failed':
        return <Badge variant="destructive">Falha</Badge>;
      case 'processing':
        return <Badge className="bg-blue-500">Processando</Badge>;
      default:
        return <Badge variant="secondary">Pendente</Badge>;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Importação de Pacientes</h1>
          <p className="text-muted-foreground">
            Importe pacientes em lote através de arquivos CSV ou Excel
          </p>
        </div>
      </div>

      {/* File Upload Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Carregar Arquivo
          </CardTitle>
          <CardDescription>
            Selecione um arquivo CSV ou Excel (.xlsx) com os dados dos pacientes
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Drag and drop area */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${dragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'
              }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <FileSpreadsheet className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-lg font-medium mb-2">
              Arraste e solte seu arquivo aqui
            </p>
            <p className="text-sm text-muted-foreground mb-4">
              ou clique no botão abaixo para selecionar
            </p>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileChange}
              className="hidden"
              id="file-upload"
            />
            <Button
              onClick={() => document.getElementById('file-upload')?.click()}
              variant="outline"
            >
              <Upload className="h-4 w-4 mr-2" />
              Selecionar arquivo
            </Button>
          </div>

          {/* Selected file info */}
          {selectedFile && (
            <Alert>
              <FileText className="h-4 w-4" />
              <AlertDescription className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(selectedFile.size / 1024).toFixed(2)} KB
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedFile(null)}
                >
                  <XCircle className="h-4 w-4" />
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Import options */}
          <div className="space-y-3 pt-4 border-t">
            <h3 className="text-sm font-medium">Opções de importação</h3>
            <div className="flex items-center justify-between">
              <Label htmlFor="skip-duplicates" className="cursor-pointer">
                Ignorar duplicados (CPF/email existente)
              </Label>
              <Switch
                id="skip-duplicates"
                checked={importOptions.skipDuplicates}
                onCheckedChange={(checked) =>
                  setImportOptions((prev) => ({ ...prev, skipDuplicates: checked }))
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="update-existing" className="cursor-pointer">
                Atualizar pacientes existentes
              </Label>
              <Switch
                id="update-existing"
                checked={importOptions.updateExisting}
                onCheckedChange={(checked) =>
                  setImportOptions((prev) => ({ ...prev, updateExisting: checked }))
                }
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-4">
            <Button
              onClick={handleValidate}
              disabled={!selectedFile || validating}
              className="flex-1"
            >
              {validating ? (
                <>
                  <LoadingSpinner className="h-4 w-4 mr-2" />
                  Validando...
                </>
              ) : (
                <>
                  <CheckCircle className="h-4 w-4 mr-2" />
                  Validar arquivo
                </>
              )}
            </Button>
            <Button
              onClick={handleImport}
              disabled={!selectedFile || !validationResult?.valid || importing}
              className="flex-1"
              variant="default"
            >
              {importing ? (
                <>
                  <LoadingSpinner className="h-4 w-4 mr-2" />
                  Importando...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Importar pacientes
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Templates Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Modelos de Importação
          </CardTitle>
          <CardDescription>
            Baixe um modelo para facilitar a importação dos seus dados
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => handleDownloadTemplate('csv')}
            className="flex-1"
          >
            <FileText className="h-4 w-4 mr-2" />
            Baixar modelo CSV
          </Button>
          <Button
            variant="outline"
            onClick={() => handleDownloadTemplate('xlsx')}
            className="flex-1"
          >
            <FileSpreadsheet className="h-4 w-4 mr-2" />
            Baixar modelo Excel
          </Button>
        </CardContent>
      </Card>

      {/* Import History Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Histórico de Importações
          </CardTitle>
          <CardDescription>
            Últimas 10 importações realizadas
          </CardDescription>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <div className="flex justify-center py-8">
              <LoadingSpinner />
            </div>
          ) : historyData && historyData.items.length > 0 ? (
            <div className="space-y-2">
              {historyData.items.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-center justify-between p-3 border rounded-lg hover:bg-secondary/50 transition-colors"
                >
                  <div className="flex-1">
                    <p className="font-medium">{entry.filename}</p>
                    <p className="text-sm text-muted-foreground">
                      {entry.userName} •{' '}
                      {formatDistanceToNow(new Date(entry.startedAt), {
                        addSuffix: true,
                        locale: ptBR,
                      })}
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right text-sm">
                      <p className="text-green-600 font-medium">
                        {entry.successfulRows} importado(s)
                      </p>
                      {entry.failedRows > 0 && (
                        <p className="text-red-600">{entry.failedRows} falha(s)</p>
                      )}
                    </div>
                    {getStatusBadge(entry.status)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <History className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>Nenhuma importação realizada ainda</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Status Modal */}
      <ImportStatusModal
        open={showModal}
        onClose={() => {
          setShowModal(false);
          if (importResult) {
            setSelectedFile(null);
            reset();
          }
        }}
        validating={validating}
        importing={importing}
        progress={progress}
        validationResult={validationResult}
        importResult={importResult}
        error={error}
        onProceed={handleImport}
      />
    </div>
  );
}
