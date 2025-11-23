/**
 * Medications API E2E Tests
 * Tests for /api/v2/medications endpoints
 *
 * P1/P2 Fix: Medications API implementation with RBAC
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

test.describe('Medications API E2E Tests', () => {
  let doctorAuth: LoginResult;
  let adminAuth: LoginResult;

  test.beforeAll(async ({ request }) => {
    doctorAuth = await loginUser(request, 'doctor@example.com', 'password123');
    adminAuth = await loginUser(request, 'admin@example.com', 'admin123');
  });

  test.describe('List Medications', () => {
    test('should list medications for authenticated doctor', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/medications`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('items');
      expect(data).toHaveProperty('total');
      expect(Array.isArray(data.items)).toBe(true);
    });

    test('should filter medications by active status', async ({ request }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v2/medications?active=true`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      data.items.forEach((medication: any) => {
        expect(medication.active).toBe(true);
      });
    });

    test('should filter medications by medication_name', async ({ request }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v2/medications?search=paracetamol`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      if (data.items.length > 0) {
        data.items.forEach((medication: any) => {
          expect(medication.medication_name.toLowerCase()).toContain('paracetamol');
        });
      }
    });

    test('should support cursor pagination', async ({ request }) => {
      const response1 = await request.get(
        `${API_BASE_URL}/api/v2/medications?limit=5`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      const data1 = await response1.json();
      expect(data1.items.length).toBeLessThanOrEqual(5);

      if (data1.has_next && data1.next_cursor) {
        const response2 = await request.get(
          `${API_BASE_URL}/api/v2/medications?limit=5&cursor=${data1.next_cursor}`,
          {
            headers: { 'X-Session-ID': doctorAuth.sessionId }
          }
        );

        const data2 = await response2.json();
        expect(data2.items.length).toBeLessThanOrEqual(5);

        const ids1 = data1.items.map((m: any) => m.id);
        const ids2 = data2.items.map((m: any) => m.id);
        expect(ids1).not.toEqual(ids2);
      }
    });

    test('should reject unauthenticated requests', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/medications`);
      expect(response.status()).toBe(401);
    });
  });

  test.describe('Get Medications by Patient ID', () => {
    test('should get medications for specific patient', async ({ request }) => {
      const patientId = '123e4567-e89b-12d3-a456-426614174001';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/medications/patient/${patientId}`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(Array.isArray(data)).toBe(true);

      data.forEach((medication: any) => {
        expect(medication.patient_id).toBe(patientId);
      });
    });

    test('should return empty array for patient with no medications', async ({ request }) => {
      const patientId = '00000000-0000-0000-0000-000000000001';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/medications/patient/${patientId}`,
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
      const invalidId = 'not-a-uuid';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/medications/patient/${invalidId}`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      expect(response.status()).toBe(422);
    });
  });

  test.describe('Create Medication', () => {
    test('should create medication with valid data', async ({ request }) => {
      const medicationData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        medication_name: 'Ondansetron',
        dosage: '8mg',
        frequency: 'Every 8 hours',
        route: 'oral',
        start_date: '2025-06-01',
        active: true,
        instructions: 'Take with food',
        indication: 'Nausea prevention'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: medicationData
      });

      expect([200, 201]).toContain(response.status());

      const data = await response.json();
      expect(data).toHaveProperty('id');
      expect(data.medication_name).toBe(medicationData.medication_name);
      expect(data.dosage).toBe(medicationData.dosage);
      expect(data.frequency).toBe(medicationData.frequency);
    });

    test('should validate required fields on create', async ({ request }) => {
      const invalidData = {
        // Missing patient_id, medication_name, dosage
        frequency: 'Daily'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);
    });

    test('should validate route enum', async ({ request }) => {
      const invalidData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        medication_name: 'Test Medication',
        dosage: '10mg',
        route: 'invalid_route' // Invalid
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
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
      const medicationData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        medication_name: 'Test Med',
        dosage: '5mg'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId
          // Missing CSRF token
        },
        data: medicationData
      });

      expect(response.status()).toBe(403);
    });

    test('should accept valid routes: oral, iv, subcutaneous, topical', async ({ request }) => {
      const validRoutes = ['oral', 'iv', 'subcutaneous', 'topical'];

      for (const route of validRoutes) {
        const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: {
            patient_id: '123e4567-e89b-12d3-a456-426614174001',
            medication_name: `Test Med ${route}`,
            dosage: '10mg',
            route
          }
        });

        expect([200, 201]).toContain(response.status());

        const data = await response.json();
        expect(data.route).toBe(route);
      }
    });
  });

  test.describe('Update Medication', () => {
    let medicationId: string;

    test.beforeEach(async ({ request }) => {
      // Create medication to update
      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          medication_name: 'Metoclopramide',
          dosage: '10mg',
          frequency: 'TID',
          route: 'oral',
          start_date: '2025-07-01',
          active: true
        }
      });

      const data = await response.json();
      medicationId = data.id;
    });

    test('should update medication with valid data', async ({ request }) => {
      const updateData = {
        dosage: '20mg',
        frequency: 'BID',
        instructions: 'Take 30 minutes before meals',
        notes: 'Dosage increased due to inadequate response'
      };

      const response = await request.put(
        `${API_BASE_URL}/api/v2/medications/${medicationId}`,
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
      expect(data.dosage).toBe(updateData.dosage);
      expect(data.frequency).toBe(updateData.frequency);
      expect(data.instructions).toBe(updateData.instructions);
    });

    test('should deactivate medication', async ({ request }) => {
      const response = await request.put(
        `${API_BASE_URL}/api/v2/medications/${medicationId}`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: {
            active: false,
            end_date: '2025-08-01',
            discontinuation_reason: 'Treatment completed'
          }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.active).toBe(false);
      expect(data.end_date).toBe('2025-08-01');
      expect(data.discontinuation_reason).toBe('Treatment completed');
    });

    test('should require CSRF token for update', async ({ request }) => {
      const response = await request.put(
        `${API_BASE_URL}/api/v2/medications/${medicationId}`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId
            // Missing CSRF
          },
          data: { dosage: '15mg' }
        }
      );

      expect(response.status()).toBe(403);
    });

    test('should return 404 for non-existent medication', async ({ request }) => {
      const fakeId = '00000000-0000-0000-0000-000000000000';

      const response = await request.put(
        `${API_BASE_URL}/api/v2/medications/${fakeId}`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: { dosage: '15mg' }
        }
      );

      expect(response.status()).toBe(404);
    });
  });

  test.describe('Delete Medication', () => {
    let medicationId: string;

    test.beforeEach(async ({ request }) => {
      // Create medication to delete
      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          medication_name: 'Temporary Med',
          dosage: '5mg',
          route: 'oral',
          start_date: '2025-09-01'
        }
      });

      const data = await response.json();
      medicationId = data.id;
    });

    test('should allow admin to delete medication', async ({ request }) => {
      const response = await request.delete(
        `${API_BASE_URL}/api/v2/medications/${medicationId}`,
        {
          headers: {
            'X-Session-ID': adminAuth.sessionId,
            'X-CSRF-Token': adminAuth.csrfToken
          }
        }
      );

      expect([200, 204]).toContain(response.status());
    });

    test('should prevent non-admin from deleting medication', async ({ request }) => {
      const response = await request.delete(
        `${API_BASE_URL}/api/v2/medications/${medicationId}`,
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
        `${API_BASE_URL}/api/v2/medications/${medicationId}`,
        {
          headers: {
            'X-Session-ID': adminAuth.sessionId
            // Missing CSRF
          }
        }
      );

      expect(response.status()).toBe(403);
    });

    test('should return 404 for deleting non-existent medication', async ({ request }) => {
      const fakeId = '00000000-0000-0000-0000-000000000000';

      const response = await request.delete(
        `${API_BASE_URL}/api/v2/medications/${fakeId}`,
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
    test('should allow doctors to view their patients medications', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/medications`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      expect(response.status()).toBe(200);
    });

    test('should allow admin to view all medications', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/medications`, {
        headers: { 'X-Session-ID': adminAuth.sessionId }
      });

      expect(response.status()).toBe(200);
    });

    test('should prevent doctors from deleting medications', async ({ request }) => {
      // Create a medication
      const createResponse = await request.post(`${API_BASE_URL}/api/v2/medications`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          medication_name: 'Temp Medication',
          dosage: '100mg',
          route: 'oral'
        }
      });

      const medicationData = await createResponse.json();

      // Try to delete as doctor
      const deleteResponse = await request.delete(
        `${API_BASE_URL}/api/v2/medications/${medicationData.id}`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          }
        }
      );

      expect(deleteResponse.status()).toBe(403);
    });
  });

  test.describe('Data Validation', () => {
    test('should validate date format for start_date', async ({ request }) => {
      const invalidData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        medication_name: 'Test Med',
        dosage: '10mg',
        start_date: 'not-a-date'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
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
        medication_name: 'Test Med',
        dosage: '10mg',
        start_date: '2025-12-01',
        end_date: '2025-11-01' // Before start_date
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);
    });

    test('should accept complete medication data', async ({ request }) => {
      const completeData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        medication_name: 'Dexamethasone',
        dosage: '4mg',
        frequency: 'QID',
        route: 'oral',
        start_date: '2025-06-01',
        end_date: '2025-06-07',
        active: true,
        instructions: 'Take with food to prevent stomach upset',
        indication: 'Anti-inflammatory for brain swelling',
        side_effects: 'Increased appetite, insomnia',
        notes: 'Taper dose over 7 days'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: completeData
      });

      expect([200, 201]).toContain(response.status());

      const data = await response.json();
      expect(data.medication_name).toBe(completeData.medication_name);
      expect(data.indication).toBe(completeData.indication);
      expect(data.side_effects).toBe(completeData.side_effects);
    });
  });

  test.describe('Performance Tests', () => {
    test('should handle concurrent medication creates', async ({ request }) => {
      const medicationPromises = Array(5).fill(null).map((_, index) =>
        request.post(`${API_BASE_URL}/api/v2/medications`, {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: {
            patient_id: '123e4567-e89b-12d3-a456-426614174001',
            medication_name: `Concurrent Med ${index}`,
            dosage: '10mg',
            route: 'oral'
          }
        })
      );

      const responses = await Promise.all(medicationPromises);

      responses.forEach(response => {
        expect([200, 201]).toContain(response.status());
      });
    });

    test('should respond quickly to list requests', async ({ request }) => {
      const startTime = Date.now();

      const response = await request.get(`${API_BASE_URL}/api/v2/medications?limit=10`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      const duration = Date.now() - startTime;

      expect(response.status()).toBe(200);
      expect(duration).toBeLessThan(1000); // < 1 second
    });
  });
});
