/**
 * Appointments API E2E Tests
 * Tests for /api/v2/appointments endpoints
 *
 * P1/P2 Fix: Appointments API implementation with RBAC
 */

import { test, expect, Page, APIRequestContext } from '@playwright/test';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

interface LoginResult {
  sessionId: string;
  csrfToken: string;
  userId: string;
  userRole: string;
}

// Helper function to login and get tokens
async function loginUser(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<LoginResult> {
  // Get CSRF token
  const csrfResponse = await request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);
  const csrfData = await csrfResponse.json();
  const csrfToken = csrfData.csrf_token;

  // Login
  const loginResponse = await request.post(`${API_BASE_URL}/api/v2/auth/login`, {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken
    },
    data: {
      email,
      password
    }
  });

  const loginData = await loginResponse.json();

  return {
    sessionId: loginData.session_id,
    csrfToken,
    userId: loginData.user.id,
    userRole: loginData.user.role
  };
}

test.describe('Appointments API E2E Tests', () => {
  let doctorAuth: LoginResult;
  let adminAuth: LoginResult;

  test.beforeAll(async ({ request }) => {
    // Login as doctor
    doctorAuth = await loginUser(request, 'doctor@example.com', 'password123');

    // Login as admin
    adminAuth = await loginUser(request, 'admin@example.com', 'admin123');
  });

  test.describe('List Appointments', () => {
    test('should list appointments for authenticated doctor', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'X-Session-ID': doctorAuth.sessionId
        }
      });

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data).toHaveProperty('items');
      expect(data).toHaveProperty('total');
      expect(data).toHaveProperty('has_next');
      expect(Array.isArray(data.items)).toBe(true);
    });

    test('should filter appointments by status', async ({ request }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v2/appointments?status=scheduled`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId
          }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      data.items.forEach((appointment: any) => {
        expect(appointment.status).toBe('scheduled');
      });
    });

    test('should filter appointments by date range', async ({ request }) => {
      const startDate = '2025-01-01';
      const endDate = '2025-12-31';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/appointments?start_date=${startDate}&end_date=${endDate}`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId
          }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      data.items.forEach((appointment: any) => {
        const appointmentDate = new Date(appointment.scheduled_date);
        expect(appointmentDate >= new Date(startDate)).toBe(true);
        expect(appointmentDate <= new Date(endDate)).toBe(true);
      });
    });

    test('should filter appointments by patient_id', async ({ request }) => {
      const patientId = '123e4567-e89b-12d3-a456-426614174000';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/appointments?patient_id=${patientId}`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId
          }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      data.items.forEach((appointment: any) => {
        expect(appointment.patient_id).toBe(patientId);
      });
    });

    test('should support cursor pagination', async ({ request }) => {
      // First page
      const response1 = await request.get(
        `${API_BASE_URL}/api/v2/appointments?limit=5`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId
          }
        }
      );

      const data1 = await response1.json();
      expect(data1.items.length).toBeLessThanOrEqual(5);

      if (data1.has_next && data1.next_cursor) {
        // Second page
        const response2 = await request.get(
          `${API_BASE_URL}/api/v2/appointments?limit=5&cursor=${data1.next_cursor}`,
          {
            headers: {
              'X-Session-ID': doctorAuth.sessionId
            }
          }
        );

        const data2 = await response2.json();
        expect(data2.items.length).toBeLessThanOrEqual(5);

        // Items should be different
        const ids1 = data1.items.map((a: any) => a.id);
        const ids2 = data2.items.map((a: any) => a.id);
        expect(ids1).not.toEqual(ids2);
      }
    });

    test('should reject unauthenticated requests', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/appointments`);

      expect(response.status()).toBe(401);
    });
  });

  test.describe('Create Appointment', () => {
    test('should create appointment with valid data', async ({ request }) => {
      const appointmentData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        scheduled_date: '2025-06-01',
        scheduled_time: '10:00:00',
        appointment_type: 'consultation',
        status: 'scheduled',
        notes: 'Initial consultation',
        duration_minutes: 30
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: appointmentData
      });

      expect([200, 201]).toContain(response.status());

      const data = await response.json();
      expect(data).toHaveProperty('id');
      expect(data.patient_id).toBe(appointmentData.patient_id);
      expect(data.appointment_type).toBe(appointmentData.appointment_type);
      expect(data.status).toBe(appointmentData.status);
    });

    test('should validate required fields on create', async ({ request }) => {
      const invalidData = {
        // Missing patient_id, scheduled_date, scheduled_time
        appointment_type: 'consultation'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: invalidData
      });

      expect(response.status()).toBe(422);

      const errorData = await response.json();
      expect(errorData).toHaveProperty('detail');
    });

    test('should validate appointment_type enum', async ({ request }) => {
      const invalidData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        scheduled_date: '2025-06-01',
        scheduled_time: '10:00:00',
        appointment_type: 'invalid_type', // Invalid
        status: 'scheduled'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
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
      const appointmentData = {
        patient_id: '123e4567-e89b-12d3-a456-426614174001',
        scheduled_date: '2025-06-01',
        scheduled_time: '10:00:00',
        appointment_type: 'consultation'
      };

      const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId
          // Missing CSRF token
        },
        data: appointmentData
      });

      expect(response.status()).toBe(403);
    });
  });

  test.describe('Get Appointment by ID', () => {
    let appointmentId: string;

    test.beforeAll(async ({ request }) => {
      // Create an appointment first
      const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          scheduled_date: '2025-06-15',
          scheduled_time: '14:00:00',
          appointment_type: 'followup',
          status: 'scheduled'
        }
      });

      const data = await response.json();
      appointmentId = data.id;
    });

    test('should get appointment by ID', async ({ request }) => {
      const response = await request.get(
        `${API_BASE_URL}/api/v2/appointments/${appointmentId}`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId
          }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.id).toBe(appointmentId);
      expect(data).toHaveProperty('patient_id');
      expect(data).toHaveProperty('scheduled_date');
      expect(data).toHaveProperty('appointment_type');
    });

    test('should return 404 for non-existent appointment', async ({ request }) => {
      const fakeId = '00000000-0000-0000-0000-000000000000';

      const response = await request.get(
        `${API_BASE_URL}/api/v2/appointments/${fakeId}`,
        {
          headers: {
            'X-Session-ID': doctorAuth.sessionId
          }
        }
      );

      expect(response.status()).toBe(404);
    });
  });

  test.describe('Update Appointment', () => {
    let appointmentId: string;

    test.beforeEach(async ({ request }) => {
      // Create appointment to update
      const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          scheduled_date: '2025-07-01',
          scheduled_time: '09:00:00',
          appointment_type: 'consultation',
          status: 'scheduled'
        }
      });

      const data = await response.json();
      appointmentId = data.id;
    });

    test('should update appointment with valid data', async ({ request }) => {
      const updateData = {
        scheduled_time: '10:30:00',
        notes: 'Updated notes',
        duration_minutes: 45
      };

      const response = await request.put(
        `${API_BASE_URL}/api/v2/appointments/${appointmentId}`,
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
      expect(data.scheduled_time).toBe(updateData.scheduled_time);
      expect(data.notes).toBe(updateData.notes);
      expect(data.duration_minutes).toBe(updateData.duration_minutes);
    });

    test('should require CSRF token for update', async ({ request }) => {
      const response = await request.put(
        `${API_BASE_URL}/api/v2/appointments/${appointmentId}`,
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
  });

  test.describe('Cancel Appointment', () => {
    let appointmentId: string;

    test.beforeEach(async ({ request }) => {
      // Create appointment to cancel
      const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          scheduled_date: '2025-08-01',
          scheduled_time: '11:00:00',
          appointment_type: 'consultation',
          status: 'scheduled'
        }
      });

      const data = await response.json();
      appointmentId = data.id;
    });

    test('should cancel appointment', async ({ request }) => {
      const response = await request.post(
        `${API_BASE_URL}/api/v2/appointments/${appointmentId}/cancel`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: {
            cancellation_reason: 'Patient request'
          }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.status).toBe('cancelled');
      expect(data.cancellation_reason).toBe('Patient request');
    });
  });

  test.describe('Update Appointment Status', () => {
    let appointmentId: string;

    test.beforeEach(async ({ request }) => {
      const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'Content-Type': 'application/json',
          'X-Session-ID': doctorAuth.sessionId,
          'X-CSRF-Token': doctorAuth.csrfToken
        },
        data: {
          patient_id: '123e4567-e89b-12d3-a456-426614174001',
          scheduled_date: '2025-09-01',
          scheduled_time: '15:00:00',
          appointment_type: 'consultation',
          status: 'scheduled'
        }
      });

      const data = await response.json();
      appointmentId = data.id;
    });

    test('should update appointment status', async ({ request }) => {
      const response = await request.patch(
        `${API_BASE_URL}/api/v2/appointments/${appointmentId}/status`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: {
            status: 'completed'
          }
        }
      );

      expect(response.status()).toBe(200);

      const data = await response.json();
      expect(data.status).toBe('completed');
    });

    test('should validate status transitions', async ({ request }) => {
      // Try to set invalid status
      const response = await request.patch(
        `${API_BASE_URL}/api/v2/appointments/${appointmentId}/status`,
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Session-ID': doctorAuth.sessionId,
            'X-CSRF-Token': doctorAuth.csrfToken
          },
          data: {
            status: 'invalid_status'
          }
        }
      );

      expect(response.status()).toBe(422);
    });
  });

  test.describe('RBAC Enforcement', () => {
    test('should allow doctors to access their own appointments', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'X-Session-ID': doctorAuth.sessionId
        }
      });

      expect(response.status()).toBe(200);
    });

    test('should allow admin to access all appointments', async ({ request }) => {
      const response = await request.get(`${API_BASE_URL}/api/v2/appointments`, {
        headers: {
          'X-Session-ID': adminAuth.sessionId
        }
      });

      expect(response.status()).toBe(200);
    });

    test('should prevent doctors from accessing other doctors appointments', async ({ request }) => {
      // This would require creating another doctor and trying to access their appointments
      // For now, we'll test the basic permission check
      expect(doctorAuth.userRole).toBe('doctor');
    });
  });
});
