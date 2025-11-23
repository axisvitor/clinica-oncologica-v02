/**
 * Medications API Client - Unit Tests
 *
 * Comprehensive test suite for the Medications API client module.
 * Tests all 6 methods and edge cases.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MedicationsApi } from '@/lib/api-client/medications';
import type { ApiClientCore } from '@/lib/api-client/core';

// Mock ApiClientCore
const createMockClient = (): ApiClientCore => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
  put: vi.fn(),
  request: vi.fn(),
  setAuthToken: vi.fn(),
  getAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  setBaseURL: vi.fn(),
  getBaseURL: vi.fn(),
  isInitialized: vi.fn(),
  fetchCsrfToken: vi.fn(),
  getCsrfToken: vi.fn(),
  setSessionToken: vi.fn(),
} as unknown as ApiClientCore);

describe('MedicationsApi', () => {
  let client: ApiClientCore;
  let medicationsApi: MedicationsApi;

  beforeEach(() => {
    client = createMockClient();
    medicationsApi = new MedicationsApi(client);
  });

  describe('list', () => {
    it('should fetch medications with default parameters', async () => {
      const mockResponse = {
        data: [
          {
            id: 'med-1',
            patient_id: 'patient-1',
            name: 'Anastrozol',
            dosage: '1mg',
            frequency: '1x ao dia',
            is_active: true,
            created_at: '2025-11-07T10:00:00Z',
            updated_at: '2025-11-07T10:00:00Z',
          },
        ],
        total: 1,
        has_more: false,
      };

      vi.mocked(client.get).mockResolvedValue(mockResponse);

      const result = await medicationsApi.list();

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications', {});
      expect(result.items).toHaveLength(1);
      expect(result.items[0].name).toBe('Anastrozol');
    });

    it('should apply filters correctly', async () => {
      const mockResponse = {
        data: [],
        total: 0,
        has_more: false,
      };

      vi.mocked(client.get).mockResolvedValue(mockResponse);

      await medicationsApi.list({
        patient_id: 'patient-123',
        is_active: true,
        route: 'oral',
        search: 'anastrozol',
      });

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications', {
        patient_id: 'patient-123',
        is_active: true,
        route: 'oral',
        search: 'anastrozol',
      });
    });

    it('should handle pagination parameters', async () => {
      const mockResponse = {
        data: [],
        total: 100,
        has_more: true,
        next_cursor: 'cursor-abc',
      };

      vi.mocked(client.get).mockResolvedValue(mockResponse);

      await medicationsApi.list({
        limit: 50,
        cursor: 'cursor-xyz',
      });

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications', {
        limit: 50,
        cursor: 'cursor-xyz',
      });
    });
  });

  describe('get', () => {
    it('should fetch a single medication by ID', async () => {
      const mockMedication = {
        id: 'med-1',
        patient_id: 'patient-1',
        name: 'Anastrozol',
        dosage: '1mg',
        frequency: '1x ao dia',
        is_active: true,
      };

      vi.mocked(client.get).mockResolvedValue(mockMedication);

      const result = await medicationsApi.get('med-1');

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications/med-1', undefined);
      expect(result.name).toBe('Anastrozol');
    });

    it('should include fields and relationships when requested', async () => {
      const mockMedication = {
        id: 'med-1',
        name: 'Anastrozol',
        patient: { id: 'patient-1', name: 'John Doe' },
      };

      vi.mocked(client.get).mockResolvedValue(mockMedication);

      await medicationsApi.get('med-1', {
        fields: 'id,name,dosage',
        include: 'patient,prescribed_by',
      });

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications/med-1', {
        fields: 'id,name,dosage',
        include: 'patient,prescribed_by',
      });
    });
  });

  describe('getByPatient', () => {
    it('should fetch medications for a specific patient', async () => {
      const mockResponse = {
        data: [
          { id: 'med-1', name: 'Anastrozol' },
          { id: 'med-2', name: 'Tamoxifen' },
        ],
        total: 2,
        has_more: false,
      };

      vi.mocked(client.get).mockResolvedValue(mockResponse);

      const result = await medicationsApi.getByPatient('patient-123');

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications', {
        patient_id: 'patient-123',
      });
      expect(result).toHaveLength(2);
    });

    it('should apply additional filters for patient medications', async () => {
      const mockResponse = {
        data: [],
        total: 0,
        has_more: false,
      };

      vi.mocked(client.get).mockResolvedValue(mockResponse);

      await medicationsApi.getByPatient('patient-123', {
        is_active: true,
        route: 'oral',
      });

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications', {
        patient_id: 'patient-123',
        is_active: true,
        route: 'oral',
      });
    });
  });

  describe('create', () => {
    it('should create a new medication', async () => {
      const createData = {
        patient_id: 'patient-123',
        name: 'Anastrozol',
        dosage: '1mg',
        frequency: '1x ao dia',
        route: 'oral' as const,
        prescription_date: '2025-11-07',
        start_date: '2025-11-08',
      };

      const mockResponse = {
        id: 'med-new',
        ...createData,
        created_at: '2025-11-07T10:00:00Z',
        updated_at: '2025-11-07T10:00:00Z',
      };

      vi.mocked(client.post).mockResolvedValue(mockResponse);

      const result = await medicationsApi.create(createData);

      expect(client.post).toHaveBeenCalledWith('/api/v2/medications', createData);
      expect(result.id).toBe('med-new');
      expect(result.name).toBe('Anastrozol');
    });
  });

  describe('update', () => {
    it('should update a medication', async () => {
      const updateData = {
        dosage: '2mg',
        frequency: '2x ao dia',
      };

      const mockResponse = {
        id: 'med-1',
        name: 'Anastrozol',
        ...updateData,
      };

      vi.mocked(client.patch).mockResolvedValue(mockResponse);

      const result = await medicationsApi.update('med-1', updateData);

      expect(client.patch).toHaveBeenCalledWith('/api/v2/medications/med-1', updateData);
      expect(result.dosage).toBe('2mg');
    });
  });

  describe('delete', () => {
    it('should delete a medication', async () => {
      vi.mocked(client.delete).mockResolvedValue(undefined);

      await medicationsApi.delete('med-1');

      expect(client.delete).toHaveBeenCalledWith('/api/v2/medications/med-1');
    });
  });

  describe('discontinue', () => {
    it('should discontinue a medication with reason', async () => {
      const mockResponse = {
        id: 'med-1',
        is_active: false,
        discontinued_date: '2025-11-07',
        discontinuation_reason: 'Treatment completed',
      };

      vi.mocked(client.patch).mockResolvedValue(mockResponse);

      const result = await medicationsApi.discontinue('med-1', 'Treatment completed');

      expect(client.patch).toHaveBeenCalledWith(
        '/api/v2/medications/med-1/discontinue',
        undefined,
        { reason: 'Treatment completed' }
      );
      expect(result.is_active).toBe(false);
    });
  });

  describe('refill', () => {
    it('should record a medication refill', async () => {
      const mockResponse = {
        id: 'med-1',
        refills_allowed: 12,
        refills_remaining: 11,
      };

      vi.mocked(client.patch).mockResolvedValue(mockResponse);

      const result = await medicationsApi.refill('med-1');

      expect(client.patch).toHaveBeenCalledWith('/api/v2/medications/med-1/refill');
      expect(result.refills_remaining).toBe(11);
    });
  });

  describe('getActive', () => {
    it('should fetch only active medications', async () => {
      const mockResponse = {
        data: [{ id: 'med-1', is_active: true }],
        total: 1,
      };

      vi.mocked(client.get).mockResolvedValue(mockResponse);

      const result = await medicationsApi.getActive();

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications/active', undefined);
      expect(result).toHaveLength(1);
    });
  });

  describe('search', () => {
    it('should search medications by name', async () => {
      const mockResults = [
        { id: 'med-1', name: 'Anastrozol' },
        { id: 'med-2', name: 'Anastrozole Generic' },
      ];

      vi.mocked(client.get).mockResolvedValue(mockResults);

      const result = await medicationsApi.search('anastrozol');

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications/search', {
        q: 'anastrozol',
        limit: 20,
      });
      expect(result).toHaveLength(2);
    });

    it('should respect custom limit (max 50)', async () => {
      vi.mocked(client.get).mockResolvedValue([]);

      await medicationsApi.search('test', 100);

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications/search', {
        q: 'test',
        limit: 50, // Should be capped at 50
      });
    });
  });

  describe('getStats', () => {
    it('should fetch medication statistics', async () => {
      const mockStats = {
        total_medications: 100,
        active_medications: 85,
        discontinued_medications: 15,
        by_route: {
          oral: 60,
          intravenous: 25,
          topical: 15,
        },
      };

      vi.mocked(client.get).mockResolvedValue(mockStats);

      const result = await medicationsApi.getStats();

      expect(client.get).toHaveBeenCalledWith('/api/v2/medications/stats');
      expect(result.total_medications).toBe(100);
      expect(result.by_route.oral).toBe(60);
    });
  });

  describe('createSchedule', () => {
    it('should create a medication schedule from medication data', () => {
      const medication = {
        id: 'med-1',
        patient_id: 'patient-1',
        name: 'Anastrozol',
        dosage: '1mg',
        frequency: '1x ao dia',
        start_date: '2025-11-08',
        end_date: '2026-11-08',
        instructions: 'Tomar pela manhã',
        is_active: true,
        created_at: '2025-11-07T10:00:00Z',
        updated_at: '2025-11-07T10:00:00Z',
        refills_allowed: 12,
        refills_remaining: 12,
        prescription_date: '2025-11-07',
      };

      const schedule = medicationsApi.createSchedule(medication);

      expect(schedule).toEqual({
        frequency: '1x ao dia',
        start_date: '2025-11-08',
        end_date: '2026-11-08',
        instructions: 'Tomar pela manhã',
      });
    });
  });
});
