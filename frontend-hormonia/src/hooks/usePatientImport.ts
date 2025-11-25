/**
 * Patient Import Hook
 *
 * Custom React hook for managing patient import functionality:
 * - File validation
 * - Import execution with progress tracking
 * - Template download
 * - Import history
 */

import { useState, useCallback } from 'react';
import { apiClient } from '@/lib/api-client';
import type {
  ImportOptions,
  ValidationResult,
  ImportResult,
  ImportHistoryEntry,
  ImportHistoryFilters,
} from '@/types/import';

interface UsePatientImportReturn {
  // State
  uploading: boolean;
  validating: boolean;
  importing: boolean;
  progress: number;
  validationResult: ValidationResult | null;
  importResult: ImportResult | null;
  error: string | null;

  // Actions
  validateFile: (file: File) => Promise<ValidationResult | null>;
  importFile: (file: File, options?: ImportOptions) => Promise<ImportResult | null>;
  downloadTemplate: (format?: 'csv' | 'xlsx') => Promise<void>;
  getImportHistory: (filters?: ImportHistoryFilters) => Promise<ImportHistoryEntry[]>;
  reset: () => void;
}

/**
 * Hook for managing patient import operations
 */
export function usePatientImport(): UsePatientImportReturn {

  // State
  const [uploading, setUploading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  /**
   * Validate import file
   */
  const validateFile = useCallback(
    async (file: File): Promise<ValidationResult | null> => {
      // Reset state
      setError(null);
      setValidationResult(null);
      setValidating(true);
      setProgress(0);

      try {
        // Validate file size (max 10MB)
        const maxSize = 10 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
          throw new Error('Arquivo muito grande. O tamanho máximo é 10MB.');
        }

        // Validate file type
        const allowedExtensions = ['.csv', '.xlsx', '.xls'];
        const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
        if (!allowedExtensions.includes(fileExtension)) {
          throw new Error('Formato de arquivo inválido. Use CSV ou Excel (.xlsx, .xls).');
        }

        setProgress(30);

        // Call API to validate
        const result = await apiClient.patients.validateImport(file);

        setProgress(100);

        // Transform API response to ValidationResult
        const validationResult: ValidationResult = {
          valid: result.valid,
          totalRows: result.totalRows,
          validRows: result.validRows,
          errorRows: result.errorRows,
          warningRows: result.warningRows,
          errors: result.errors.map(err => ({
            row: err.row,
            column: err.column,
            message: err.message,
            severity: err.severity,
            code: undefined,
          })),
          warnings: result.warnings.map(warn => ({
            row: warn.row,
            column: warn.column,
            message: warn.message,
            code: undefined,
          })),
          preview: result.preview,
          format: result.format,
          fileSize: result.fileSize,
        };

        setValidationResult(validationResult);
        return validationResult;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erro ao validar arquivo';
        setError(errorMessage);
        return null;
      } finally {
        setValidating(false);
      }
    },
    [apiClient]
  );

  /**
   * Import patients from file
   */
  const importFile = useCallback(
    async (file: File, options: ImportOptions = {}): Promise<ImportResult | null> => {
      // Reset state
      setError(null);
      setImportResult(null);
      setImporting(true);
      setProgress(0);

      try {
        // Validate file first if not already validated
        if (!validationResult) {
          const validation = await validateFile(file);
          if (!validation || !validation.valid) {
            throw new Error('Arquivo contém erros. Corrija os erros antes de importar.');
          }
        }

        setProgress(20);

        // Call API to import
        const result = await apiClient.patients.importPatients(file, {
          skipDuplicates: options.skipDuplicates,
          updateExisting: options.updateExisting,
          validateOnly: options.validateOnly,
        });

        setProgress(100);

        // Transform API response to ImportResult
        const importResult: ImportResult = {
          total: result.total,
          successful: result.successful,
          failed: result.failed,
          skipped: result.skipped || 0,
          updated: result.updated || 0,
          errors: result.errors.map(err => ({
            row: err.row,
            patientName: err.patientName,
            message: err.message,
            code: err.code,
          })),
          sessionId: result.sessionId,
        };

        setImportResult(importResult);
        return importResult;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erro ao importar pacientes';
        setError(errorMessage);
        return null;
      } finally {
        setImporting(false);
      }
    },
    [apiClient, validationResult, validateFile]
  );

  /**
   * Download import template
   */
  const downloadTemplate = useCallback(
    async (format: 'csv' | 'xlsx' = 'csv'): Promise<void> => {
      try {
        setUploading(true);
        const blob = await apiClient.patients.downloadTemplate(format);

        // Create download link
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `modelo-importacao-pacientes.${format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erro ao baixar modelo';
        setError(errorMessage);
        throw err;
      } finally {
        setUploading(false);
      }
    },
    [apiClient]
  );

  /**
   * Get import history
   */
  const getImportHistory = useCallback(
    async (filters?: ImportHistoryFilters): Promise<ImportHistoryEntry[]> => {
      try {
        const result = await apiClient.patients.getImportHistory({
          userId: filters?.userId,
          status: filters?.status,
          startDate: filters?.startDate,
          endDate: filters?.endDate,
          page: filters?.page,
          size: filters?.size,
        });

        // Transform API response to ImportHistoryEntry[]
        return result.items.map(item => ({
          id: item.id,
          userId: item.userId,
          userName: item.userName,
          filename: item.filename,
          format: item.format,
          status: item.status,
          totalRows: item.totalRows,
          successfulRows: item.successfulRows,
          failedRows: item.failedRows,
          skippedRows: item.skippedRows,
          options: {}, // API doesn't return options in history
          startedAt: item.startedAt,
          completedAt: item.completedAt,
          duration: item.duration,
        }));
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erro ao buscar histórico';
        setError(errorMessage);
        return [];
      }
    },
    [apiClient]
  );

  /**
   * Reset all state
   */
  const reset = useCallback(() => {
    setUploading(false);
    setValidating(false);
    setImporting(false);
    setProgress(0);
    setValidationResult(null);
    setImportResult(null);
    setError(null);
  }, []);

  return {
    // State
    uploading,
    validating,
    importing,
    progress,
    validationResult,
    importResult,
    error,

    // Actions
    validateFile,
    importFile,
    downloadTemplate,
    getImportHistory,
    reset,
  };
}

/**
 * Hook to check if user has import permissions
 */
export function useCanImportPatients(): boolean {
  // TODO: Implement RBAC check
  // For now, assume user can import if they can access this hook
  // Should check for 'admin' or 'doctor' role
  return true;
}
