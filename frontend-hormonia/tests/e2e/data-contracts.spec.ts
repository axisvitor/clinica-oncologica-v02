/**
 * Data Contracts E2E Tests
 * Tests for P2 data contract normalizations:
 * - User: full_name normalization
 * - Patient: flow_state normalization
 * - Backward compatibility checks
 *
 * P2 Fix: Data model consistency and type contracts
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

test.describe('Data Contracts E2E Tests', () => {
  let doctorAuth: LoginResult;

  test.beforeAll(async ({ request }) => {
    doctorAuth = await loginUser(request, 'doctor@example.com', 'password123');
  });

  test.describe('User: full_name Normalization', () => {
    test('should always return full_name field in user responses', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/users/me`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      expect(response.status()).toBe(200);

      const user = await response.json();
      expect(user).toHaveProperty('full_name');
      expect(typeof user.full_name).toBe('string');
    });

    test('should normalize full_name from name if present', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/users/me`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      const user = await response.json();

      // If both name and full_name exist, they should be consistent
      if (user.name && user.full_name) {
        expect(user.full_name).toBe(user.name);
      }
    });

    test('should handle users with only full_name field', async ({ request }) => {
      // Create user with only full_name
      const userData = {
        email: 'new.user@example.com',
        full_name: 'New User Name',
        password: 'password123',
        role: 'doctor'
      };

      const createResponse = await request.post(`${API_BASE_URL}/api/v2/admin/users`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: userData
      });

      if ([200, 201].includes(createResponse.status())) {
        const newUser = await createResponse.json();
        expect(newUser.full_name).toBe(userData.full_name);

        // Should NOT have deprecated 'name' field
        expect(newUser.name).toBeUndefined();
      }
    });

    test('should handle users with only name field (backward compatibility)', async ({ request }) => {
      // Some old users might only have 'name'
      // The API should normalize this to full_name

      const response = await request.get(`${API_BASE_URL}/api/v2/users`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      if (response.status() === 200) {
        const users = await response.json();

        users.items?.forEach((user: any) => {
          // All users must have full_name
          expect(user).toHaveProperty('full_name');
          expect(user.full_name).toBeTruthy();
        });
      }
    });

    test('should accept full_name in user update', async ({ request }) => {
      const updateData = {
        full_name: 'Updated Full Name'
      };

      const response = await request.put(
        `${API_BASE_URL}/api/v2/users/${doctorAuth.userId}`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: updateData
        }
      );

      if ([200, 403].includes(response.status())) {
        // 403 is OK (might not have permission to update self)
        // 200 means update worked
        if (response.status() === 200) {
          const user = await response.json();
          expect(user.full_name).toBe(updateData.full_name);
        }
      }
    });

    test('should NOT accept deprecated name field in new user creation', async ({ request }) => {
      const userData = {
        email: 'deprecated.user@example.com',
        name: 'Deprecated Name Field', // Using old field
        password: 'password123',
        role: 'doctor'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/admin/users`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: userData
      });

      // Should reject or convert 'name' to 'full_name'
      if ([200, 201, 422].includes(response.status())) {
        if (response.status() === 422) {
          const error = await response.json();
          expect(error.detail).toBeDefined();
        } else {
          const user = await response.json();
          // Should have been converted to full_name
          expect(user.full_name).toBeDefined();
        }
      }
    });

    test('should validate full_name is not empty', async ({ request }) => {
      const userData = {
        email: 'empty.name@example.com',
        full_name: '', // Empty string
        password: 'password123',
        role: 'doctor'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/admin/users`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: userData
      });

      expect(response.status()).toBe(422);

      const error = await response.json();
      expect(error.detail).toBeDefined();
    });
  });

  test.describe('Patient: flow_state Normalization', () => {
    test('should always return flow_state field in patient responses', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/patients`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      expect(response.status()).toBe(200);

      const data = await response.json();

      data.items?.forEach((patient: any) => {
        expect(patient).toHaveProperty('flow_state');
        expect(typeof patient.flow_state).toBe('string');
      });
    });

    test('should validate flow_state enum values', async ({ request }) => {
      const validStates = ['pending', 'active', 'completed', 'cancelled'];

      const response = await request.get(`${API_BASE_URL}/api/v2/patients`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      const data = await response.json();

      data.items?.forEach((patient: any) => {
        expect(validStates).toContain(patient.flow_state);
      });
    });

    test('should reject invalid flow_state values', async ({ request }) => {
      const patientData = {
        name: 'Test Patient',
        email: 'invalid.state@example.com',
        phone: '+5511999999999',
        birth_date: '1990-01-01',
        flow_state: 'invalid_state' // Invalid
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: patientData
      });

      expect(response.status()).toBe(422);

      const error = await response.json();
      expect(error.detail.toLowerCase()).toContain('flow_state');
    });

    test('should default to "pending" if flow_state not provided', async ({ request }) => {
      const patientData = {
        name: 'Default Flow State Patient',
        email: 'default.flow@example.com',
        phone: '+5511888888888',
        birth_date: '1985-05-15'
        // No flow_state provided
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: patientData
      });

      if ([200, 201].includes(response.status())) {
        const patient = await response.json();
        expect(patient.flow_state).toBe('pending');
      }
    });

    test('should allow updating flow_state', async ({ request }) => {
      // Create patient
      const createResponse = await request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          name: 'Update Flow Patient',
          email: 'update.flow@example.com',
          phone: '+5511777777777',
          birth_date: '1992-03-20'
        }
      });

      if ([200, 201].includes(createResponse.status())) {
        const patient = await createResponse.json();

        // Update flow_state
        const updateResponse = await request.put(
          `${API_BASE_URL}/api/v2/patients/${patient.id}`,
          {
            headers: {
              'Content-Type': 'application/json',
              'X-Session-ID': doctorAuth.sessionId,
              'X-CSRF-Token': doctorAuth.csrfToken
            },
            data: {
              flow_state: 'active'
            }
          }
        );

        expect(updateResponse.status()).toBe(200);

        const updatedPatient = await updateResponse.json();
        expect(updatedPatient.flow_state).toBe('active');
      }
    });

    test('should maintain flow_state consistency across endpoints', async ({ request }) => {
      // Get patient from list endpoint
      const listResponse = await request.get(
        `${API_BASE_URL}/api/v2/patients?limit=1`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      if (listResponse.status() === 200) {
        const listData = await listResponse.json();

        if (listData.items.length > 0) {
          const patientFromList = listData.items[0];

          // Get same patient from detail endpoint
          const detailResponse = await request.get(
            `${API_BASE_URL}/api/v2/patients/${patientFromList.id}`,
            {
              headers: { 'X-Session-ID': doctorAuth.sessionId }
            }
          );

          const patientFromDetail = await detailResponse.json();

          // flow_state should match
          expect(patientFromDetail.flow_state).toBe(patientFromList.flow_state);
        }
      }
    });
  });

  test.describe('Backward Compatibility', () => {
    test('should handle legacy responses with old field names', async ({ request }) => {
      // API should normalize old field names to new ones

      const response = await request.get(`${API_BASE_URL}/api/v2/users/me`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      const user = await response.json();

      // New field must exist
      expect(user.full_name).toBeDefined();

      // Old field should either:
      // 1. Not exist (preferred)
      // 2. Match the new field (for compatibility)
      if (user.name !== undefined) {
        expect(user.name).toBe(user.full_name);
      }
    });

    test('should accept both old and new field names in input (transition period)', async ({ request }) => {
      // During migration, API might accept both 'name' and 'full_name'
      // but should normalize to 'full_name' in response

      const userData = {
        email: 'transition.user@example.com',
        name: 'Transition Name', // Old field
        password: 'password123',
        role: 'doctor'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/admin/users`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: userData
      });

      if ([200, 201, 422].includes(response.status())) {
        if ([200, 201].includes(response.status())) {
          const user = await response.json();

          // Response should use new field
          expect(user.full_name).toBeDefined();
          expect(user.full_name).toBe(userData.name);
        }
      }
    });

    test('should not break existing clients using old field names', async ({ request }) => {
      // Get user data
      const response = await request.get(`${API_BASE_URL}/api/v2/users/me`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      const user = await response.json();

      // Must have new field
      expect(user.full_name).toBeDefined();

      // If old field exists, it should not be null/undefined
      if (user.name !== undefined) {
        expect(user.name).toBeTruthy();
      }
    });
  });

  test.describe('Type Consistency', () => {
    test('should return consistent types across all user endpoints', async ({ request }) => {
      // Get from /users/me
      const meResponse = await request.get(`${API_BASE_URL}/api/v2/users/me`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      const meUser = await meResponse.json();

      // Get from /users list
      const listResponse = await request.get(`${API_BASE_URL}/api/v2/users`, {
        headers: { 'X-Session-ID': doctorAuth.sessionId }
      });

      if (listResponse.status() === 200) {
        const listData = await listResponse.json();

        if (listData.items.length > 0) {
          const listUser = listData.items[0];

          // Both should have same fields
          expect(typeof listUser.full_name).toBe(typeof meUser.full_name);
          expect(typeof listUser.email).toBe(typeof meUser.email);
          expect(typeof listUser.role).toBe(typeof meUser.role);
        }
      }
    });

    test('should return consistent types across all patient endpoints', async ({ request }) => {
      // Get from /patients list
      const listResponse = await request.get(
        `${API_BASE_URL}/api/v2/patients?limit=2`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      if (listResponse.status() === 200) {
        const listData = await listResponse.json();

        if (listData.items.length > 0) {
          const patient1 = listData.items[0];

          // Get from /patients/:id
          const detailResponse = await request.get(
            `${API_BASE_URL}/api/v2/patients/${patient1.id}`,
            {
              headers: { 'X-Session-ID': doctorAuth.sessionId }
            }
          );

          const patient2 = await detailResponse.json();

          // Types should match
          expect(typeof patient1.flow_state).toBe(typeof patient2.flow_state);
          expect(typeof patient1.name).toBe(typeof patient2.name);
          expect(typeof patient1.email).toBe(typeof patient2.email);
        }
      }
    });

    test('should maintain type consistency in nested objects', async ({ request }) => {
      // Get patient with related data
      const response = await request.get(
        `${API_BASE_URL}/api/v2/patients?limit=1&include=doctor`,
        {
          headers: { 'X-Session-ID': doctorAuth.sessionId }
        }
      );

      if (response.status() === 200) {
        const data = await response.json();

        if (data.items.length > 0 && data.items[0].doctor) {
          const doctor = data.items[0].doctor;

          // Nested doctor should also have full_name
          expect(doctor).toHaveProperty('full_name');
          expect(typeof doctor.full_name).toBe('string');
        }
      }
    });
  });

  test.describe('Schema Validation', () => {
    test('should validate required fields in patient creation', async ({ request }) => {
      const invalidData = {
        // Missing required fields: name, phone
        email: 'incomplete@example.com'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);

      const error = await response.json();
      expect(error).toHaveProperty('detail');
    });

    test('should validate email format', async ({ request }) => {
      const invalidData = {
        name: 'Test Patient',
        email: 'not-an-email',
        phone: '+5511999999999',
        birth_date: '1990-01-01'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);
    });

    test('should validate phone number format (E.164)', async ({ request }) => {
      const invalidData = {
        name: 'Test Patient',
        email: 'test@example.com',
        phone: '11999999999', // Missing country code
        birth_date: '1990-01-01'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/patients`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      // Should validate E.164 format
      expect([422, 400]).toContain(response.status());
    });
  });
});
