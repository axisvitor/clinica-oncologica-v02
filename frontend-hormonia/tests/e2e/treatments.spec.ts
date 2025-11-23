/**
 * Treatments API E2E Tests
 * Tests for /api/v2/treatments endpoints
 *
 * P1/P2 Fix: Treatments API implementation with RBAC
 */

import { test, expect, APIRequestContext } from '@playwright/test';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

interface LoginResult {
  sessionId: string;
  csrfToken: string;
  userId: string;
  userRole: string;
}

async function loginUser(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<LoginResult> {
  const csrfResponse = await request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);
  const csrfData = await csrfResponse.json();

  const loginResponse = await request.post(`${API_BASE_URL}/api/v2/auth/login`, {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfData.csrf_token
    },
    data: { email, password }
  });

  const loginData = await loginResponse.json();

  return {
    sessionId: loginData.session_id,
    csrfToken: csrfData.csrf_token,
    userId: loginData.user.id,
    userRole: loginData.user.role
  };
}

test.describe('Treatments API E2E Tests', () => {
  let doctorAuth: LoginResult;
  let adminAuth: LoginResult;

  test.beforeAll(async ({ request }) => {
    doctorAuth = await loginUser(request, 'doctor@example.com', 'password123');
    adminAuth = await loginUser(request, 'admin@example.com', 'admin123');
  });

  test.describe('List Treatments', () => {
    test('should list treatments for authenticated doctor', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/treatments`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('items');
      expect(data).toHaveProperty('total');
      expect(Array.isArray(data.items)).toBe(true);
    });

    test('should filter treatments by status', async ({ request }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v2/treatments?status=active`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      data.items.forEach((treatment: any) => {
        expect(treatment.status).toBe('active');
      });
    });

    test('should filter treatments by treatment_type', async ({ request }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v2/treatments?treatment_type=chemotherapy`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      data.items.forEach((treatment: any) => {
        expect(treatment.treatment_type).toBe('chemotherapy');
      });
    });

    test('should support pagination with limit and offset', async ({ request }) => {
      const response1 = await request.get(
        `${API_BASE_URL}/api/v2/treatments?limit=3`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      const data1 = await response1.json();
      expect(data1.items.length).toBeLessThanOrEqual(3);

      if (data1.has_next) {
        const response2 = await request.get(
          `${API_BASE_URL}/api/v2/treatments?limit=3&offset=3`,
          {
            headers: { 'X-Session-ID': doctorAuth.sessionId }
          }
        );

        const data2 = await response2.json();
        expect(data2.items.length).toBeLessThanOrEqual(3);

        // Items should be different
        const ids1 = data1.items.map((t: any) => t.id);
        const ids2 = data2.items.map((t: any) => t.id);
        expect(ids1).not.toEqual(ids2);
      }
    });

    test('should reject unauthenticated requests', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/treatments`);
      expect(response.status()).toBe(401);
    });
  });

  test.describe('Get Treatments by Patient ID', () => {
    test('should get treatments for specific patient', async ({ request }) => {
      const patientId = '123e4567-e89b-12d3-a456-426614174001';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/treatments/patient/${patientId}`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);

      data.forEach((treatment: any) => {
        expect(treatment.patient_id).toBe(patientId);
      });
    });

    test('should return empty array for patient with no treatments', async ({ request }) => {
      const patientId = '00000000-0000-0000-0000-000000000001';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/treatments/patient/${patientId}`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);
      expect(data.length).toBe(0);
    });

    test('should validate UUID format for patient_id', async ({ request }) => {
      const invalidId = 'invalid-uuid';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/treatments/patient/${invalidId}`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(422);
    });
  });

  test.describe('Create Treatment', () => {
    test('should create treatment with valid data', async ({ request }) => {
      const treatmentData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        treatment_type: 'chemotherapy',
        protocol_name: 'FOLFOX',
        start_date: '2025-06-01',
        status: 'active',
        notes: 'Initial treatment cycle',
        goals: 'Tumor reduction'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: treatmentData
      });

      expect([200, 201]).toContain(response.status());

      const data = await response.json();
      expect(data).toHaveProperty('id');
      expect(data.patient_id).toBe(treatmentData.patient_id);
      expect(data.treatment_type).toBe(treatmentData.treatment_type);
      expect(data.protocol_name).toBe(treatmentData.protocol_name);
    });

    test('should validate required fields on create', async ({ request }) => {
      const invalidData = {
        // Missing patient_id, treatment_type
        protocol_name: 'FOLFOX'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);
    });

    test('should validate treatment_type enum', async ({ request }) => {
      const invalidData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        treatment_type: 'invalid_type',
        start_date: '2025-06-01'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);
    });

    test('should require CSRF token for create', async ({ request }) => {
      const treatmentData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        treatment_type: 'chemotherapy',
        start_date: '2025-06-01'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId
          // Missing CSRF token
        },
        data: treatmentData
      });

      expect(response.status()).toBe(403);
    });
  });

  test.describe('Update Treatment', () => {
    let treatmentId: string;

    test.beforeEach(async ({ request }) => {
      // Create treatment to update
      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          treatment_type: 'radiation',
          start_date: '2025-07-01',
          status: 'active'
        }
      });

      const data = await response.json();
      treatmentId = data.id;
    });

    test('should update treatment with valid data', async ({ request }) => {
      const updateData = {
        status: 'completed',
        end_date: '2025-08-01',
        notes: 'Treatment completed successfully',
        outcome: 'Positive response'
      };

      const response = await request.put(
        `${API_BASE_URL}/api/v2/treatments/${treatmentId}`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: updateData
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.status).toBe(updateData.status);
      expect(data.end_date).toBe(updateData.end_date);
      expect(data.notes).toBe(updateData.notes);
    });

    test('should require CSRF token for update', async ({ request }) => {
      const response = await request.put(
        `${API_BASE_URL}/api/v2/treatments/${treatmentId}`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId
            // Missing CSRF
          },
          data: { notes: 'Updated' }
        }
      );

      expect(response.status()).toBe(403);
    });

    test('should return 404 for non-existent treatment', async ({ request }) => {
      const fakeId = '00000000-0000-0000-0000-000000000000';

      const response = await request.put(
        `${API_BASE_URL}/api/v2/treatments/${fakeId}`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: { notes: 'Updated' }
        }
      );

      expect(response.status()).toBe(404);
    });
  });

  test.describe('Delete Treatment', () => {
    let treatmentId: string;

    test.beforeEach(async ({ request }) => {
      // Create treatment to delete
      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          treatment_type: 'surgery',
          start_date: '2025-09-01',
          status: 'planned'
        }
      });

      const data = await response.json();
      treatmentId = data.id;
    });

    test('should allow admin to delete treatment', async ({ request }) => {
      const response = await request.delete(
        `${API_BASE_URL}/api/v2/treatments/${treatmentId}`,
        {
          headers: {
            'X-Session-ID': adminAuth.sessionId,
            'X-CSRF-Token': adminAuth.csrfToken
          }
        }
      );

      expect([200, 204]).toContain(response.status());
    });

    test('should prevent non-admin from deleting treatment', async ({ request }) => {
      const response = await request.delete(
        `${API_BASE_URL}/api/v2/treatments/${treatmentId}`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          }
        }
      );

      expect(response.status()).toBe(403);
    });

    test('should require CSRF token for delete', async ({ request }) => {
      const response = await request.delete(
        `${API_BASE_URL}/api/v2/treatments/${treatmentId}`,
        {
          headers: {
            'X-Session-ID': adminAuth.sessionId
            // Missing CSRF
          }
        }
      );

      expect(response.status()).toBe(403);
    });

    test('should return 404 for deleting non-existent treatment', async ({ request }) => {
      const fakeId = '00000000-0000-0000-0000-000000000000';

      const response = await request.delete(
        `${API_BASE_URL}/api/v2/treatments/${fakeId}`,
        {
          headers: {
            'X-Session-ID': adminAuth.sessionId,
            'X-CSRF-Token': adminAuth.csrfToken
          }
        }
      );

      expect(response.status()).toBe(404);
    });
  });

  test.describe('RBAC Enforcement', () => {
    test('should allow doctors to view their patients treatments', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/treatments`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      expect(response.status()).toBe(200);
    });

    test('should allow admin to view all treatments', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/treatments`, {
        headers: { 'X-Session-ID': adminAuth.sessionId }
      });

      expect(response.status()).toBe(200);
    });

    test('should prevent doctors from deleting treatments', async ({ request }) => {
      // Create a treatment
      const createResponse = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          treatment_type: 'immunotherapy',
          start_date: '2025-10-01'
        }
      });

      const treatmentData = await createResponse.json();

      // Try to delete as doctor
      const deleteResponse = await request.delete(
        `${API_BASE_URL}/api/v2/treatments/${treatmentData.id}`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          }
        }
      );

      expect(deleteResponse.status()).toBe(403);
    });

    test('should allow admin to delete treatments', async ({ request }) => {
      // Create a treatment
      const createResponse = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': adminAuth.sessionId,
          'X-CSRF-Token': adminAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          treatment_type: 'targeted_therapy',
          start_date: '2025-11-01'
        }
      });

      const treatmentData = await createResponse.json();

      // Delete as admin
      const deleteResponse = await request.delete(
        `${API_BASE_URL}/api/v2/treatments/${treatmentData.id}`,
        {
          headers: {
            'X-Session-ID': adminAuth.sessionId,
            'X-CSRF-Token': adminAuth.csrfToken
          }
        }
      );

      expect([200, 204]).toContain(deleteResponse.status());
    });
  });

  test.describe('Data Validation', () => {
    test('should validate date format for start_date', async ({ request }) => {
      const invalidData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        treatment_type: 'chemotherapy',
        start_date: 'invalid-date'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);
    });

    test('should validate end_date is after start_date', async ({ request }) => {
      const invalidData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        treatment_type: 'chemotherapy',
        start_date: '2025-12-01',
        end_date: '2025-11-01' // Before start_date
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);
    });

    test('should accept valid treatment data with all fields', async ({ request }) => {
      const completeData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        treatment_type: 'chemotherapy',
        protocol_name: 'AC-T',
        start_date: '2025-06-01',
        end_date: '2025-12-01',
        status: 'active',
        notes: 'Patient tolerating well',
        goals: 'Complete tumor regression',
        side_effects: 'Mild nausea',
        outcome: 'Ongoing'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: completeData
      });

      expect([200, 201]).toContain(response.status());

      const data = await response.json();
      expect(data.protocol_name).toBe(completeData.protocol_name);
      expect(data.goals).toBe(completeData.goals);
      expect(data.side_effects).toBe(completeData.side_effects);
    });
  });
});
