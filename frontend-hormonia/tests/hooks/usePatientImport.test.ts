/**
 * usePatientImport Hook Tests
 *
 * Tests for the patient import hook functionality
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { usePatientImport } from '@/hooks/usePatientImport';
import { apiClient } from '@/lib/api-client';

// Mock API client
jest.mock('@/lib/api-client', () => ({
  apiClient: {
    patients: {
      validateImport: jest.fn(),
      importPatients: jest.fn(),
      downloadTemplate: jest.fn(),
      getImportHistory: jest.fn(),
    },
  },
}));

describe('usePatientImport', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('validateFile', () => {
    it('should validate a valid CSV file', async () => {
      const mockValidationResult = {
        valid: true,
        totalRows: 10,
        validRows: 10,
        errorRows: 0,
        warningRows: 0,
        errors: [],
        warnings: [],
        preview: [
          { row: 1, name: 'Test Patient', email: 'test@example.com' },
        ],
        format: 'csv' as const,
        fileSize: 1024,
      };

      (apiClient.patients.validateImport as jest.Mock).mockResolvedValue(
        mockValidationResult
      );

      const { result } = renderHook(() => usePatientImport());

      const file = new File(['name,email\nTest,test@example.com'], 'test.csv', {
        type: 'text/csv',
      });

      let validationResult;
      await act(async () => {
        validationResult = await result.current.validateFile(file);
      });

      expect(result.current.validating).toBe(false);
      expect(validationResult).toEqual(mockValidationResult);
      expect(apiClient.patients.validateImport).toHaveBeenCalledWith(file);
    });

    it('should reject files larger than 10MB', async () => {
      const { result } = renderHook(() => usePatientImport());

      // Create a mock file that appears to be > 10MB
      const largeFile = new File(['x'.repeat(11 * 1024 * 1024)], 'large.csv', {
        type: 'text/csv',
      });

      let validationResult;
      await act(async () => {
        validationResult = await result.current.validateFile(largeFile);
      });

      expect(validationResult).toBeNull();
      expect(result.current.error).toContain('muito grande');
      expect(apiClient.patients.validateImport).not.toHaveBeenCalled();
    });

    it('should reject invalid file types', async () => {
      const { result } = renderHook(() => usePatientImport());

      const invalidFile = new File(['data'], 'test.txt', {
        type: 'text/plain',
      });

      let validationResult;
      await act(async () => {
        validationResult = await result.current.validateFile(invalidFile);
      });

      expect(validationResult).toBeNull();
      expect(result.current.error).toContain('Formato de arquivo inválido');
      expect(apiClient.patients.validateImport).not.toHaveBeenCalled();
    });

    it('should handle API errors during validation', async () => {
      (apiClient.patients.validateImport as jest.Mock).mockRejectedValue(
        new Error('API Error')
      );

      const { result } = renderHook(() => usePatientImport());

      const file = new File(['name\nTest'], 'test.csv', { type: 'text/csv' });

      let validationResult;
      await act(async () => {
        validationResult = await result.current.validateFile(file);
      });

      expect(validationResult).toBeNull();
      expect(result.current.error).toContain('API Error');
    });
  });

  describe('importFile', () => {
    it('should import patients successfully', async () => {
      const mockImportResult = {
        total: 10,
        successful: 10,
        failed: 0,
        skipped: 0,
        updated: 0,
        errors: [],
      };

      (apiClient.patients.importPatients as jest.Mock).mockResolvedValue(
        mockImportResult
      );

      const { result } = renderHook(() => usePatientImport());

      const file = new File(['name\nTest'], 'test.csv', { type: 'text/csv' });

      let importResult;
      await act(async () => {
        importResult = await result.current.importFile(file, {
          skipDuplicates: true,
        });
      });

      expect(result.current.importing).toBe(false);
      expect(importResult).toEqual(mockImportResult);
      expect(apiClient.patients.importPatients).toHaveBeenCalledWith(file, {
        skipDuplicates: true,
        updateExisting: undefined,
        validateOnly: undefined,
      });
    });

    it('should handle import with errors', async () => {
      const mockImportResult = {
        total: 10,
        successful: 8,
        failed: 2,
        skipped: 0,
        updated: 0,
        errors: [
          { row: 5, message: 'Invalid CPF', patientName: 'Test Patient' },
          { row: 7, message: 'Duplicate email', patientName: 'Another Patient' },
        ],
      };

      (apiClient.patients.importPatients as jest.Mock).mockResolvedValue(
        mockImportResult
      );

      const { result } = renderHook(() => usePatientImport());

      const file = new File(['name\nTest'], 'test.csv', { type: 'text/csv' });

      let importResult;
      await act(async () => {
        importResult = await result.current.importFile(file);
      });

      expect(importResult).toEqual(mockImportResult);
      expect(importResult?.errors.length).toBe(2);
    });
  });

  describe('downloadTemplate', () => {
    it('should download CSV template', async () => {
      const mockBlob = new Blob(['template'], { type: 'text/csv' });
      (apiClient.patients.downloadTemplate as jest.Mock).mockResolvedValue(
        mockBlob
      );

      // Mock URL.createObjectURL and document methods
      global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
      global.URL.revokeObjectURL = jest.fn();
      const mockLink = {
        click: jest.fn(),
        href: '',
        download: '',
      };
      document.createElement = jest.fn(() => mockLink as any);
      document.body.appendChild = jest.fn();
      document.body.removeChild = jest.fn();

      const { result } = renderHook(() => usePatientImport());

      await act(async () => {
        await result.current.downloadTemplate('csv');
      });

      expect(apiClient.patients.downloadTemplate).toHaveBeenCalledWith('csv');
      expect(mockLink.download).toBe('modelo-importacao-pacientes.csv');
      expect(mockLink.click).toHaveBeenCalled();
    });
  });

  describe('getImportHistory', () => {
    it('should fetch import history', async () => {
      const mockHistory = {
        items: [
          {
            id: '1',
            userId: 'user1',
            userName: 'Test User',
            filename: 'patients.csv',
            format: 'csv' as const,
            status: 'completed' as const,
            totalRows: 10,
            successfulRows: 10,
            failedRows: 0,
            skippedRows: 0,
            startedAt: '2025-01-01T00:00:00Z',
          },
        ],
        total: 1,
        page: 1,
        size: 10,
        pages: 1,
      };

      (apiClient.patients.getImportHistory as jest.Mock).mockResolvedValue(
        mockHistory
      );

      const { result } = renderHook(() => usePatientImport());

      let history;
      await act(async () => {
        history = await result.current.getImportHistory({ page: 1, size: 10 });
      });

      expect(history).toHaveLength(1);
      expect(apiClient.patients.getImportHistory).toHaveBeenCalledWith({
        userId: undefined,
        status: undefined,
        startDate: undefined,
        endDate: undefined,
        page: 1,
        size: 10,
      });
    });
  });

  describe('reset', () => {
    it('should reset all state', async () => {
      const { result } = renderHook(() => usePatientImport());

      const file = new File(['name\nTest'], 'test.csv', { type: 'text/csv' });

      // Perform some operations to change state
      await act(async () => {
        await result.current.validateFile(file);
      });

      // Reset
      act(() => {
        result.current.reset();
      });

      expect(result.current.validating).toBe(false);
      expect(result.current.importing).toBe(false);
      expect(result.current.progress).toBe(0);
      expect(result.current.validationResult).toBeNull();
      expect(result.current.importResult).toBeNull();
      expect(result.current.error).toBeNull();
    });
  });
});
