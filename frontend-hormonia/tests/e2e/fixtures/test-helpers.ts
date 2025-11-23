/**
 * E2E Test Helpers and Utilities
 * Shared functions for P1/P2 API testing
 */

import { APIRequestContext } from '@playwright/test';

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

export interface LoginResult {
  sessionId: string;
  csrfToken: string;
  userId: string;
  userRole: string;
  userEmail: string;
}

export interface CreatePatientData {
  name: string;
  email: string;
  phone: string;
  birth_date: string;
  cpf?: string;
  flow_state?: 'pending' | 'active' | 'completed' | 'cancelled';
}

export interface CreateAppointmentData {
  patient_id: string;
  scheduled_date: string;
  scheduled_time: string;
  appointment_type: 'consultation' | 'followup' | 'procedure' | 'emergency';
  status?: 'scheduled' | 'completed' | 'cancelled' | 'no_show';
  notes?: string;
  duration_minutes?: number;
}

export interface CreateTreatmentData {
  patient_id: string;
  treatment_type: 'chemotherapy' | 'radiation' | 'surgery' | 'immunotherapy' | 'targeted_therapy';
  protocol_name?: string;
  start_date: string;
  end_date?: string;
  status?: 'planned' | 'active' | 'completed' | 'discontinued';
  notes?: string;
  goals?: string;
}

export interface CreateMedicationData {
  patient_id: string;
  medication_name: string;
  dosage: string;
  frequency?: string;
  route?: 'oral' | 'iv' | 'subcutaneous' | 'topical';
  start_date?: string;
  end_date?: string;
  active?: boolean;
  instructions?: string;
}

/**
 * Get CSRF token from API
 */
export async function getCsrfToken(request: APIRequestContext): Promise<string> {
  const response = await request.get(`${API_BASE_URL}/api/v2/auth/csrf-token`);

  if (response.status() !== 200) {
    throw new Error(`Failed to get CSRF token: ${response.status()}`);
  }

  const data = await response.json();
  return data.csrf_token;
}

/**
 * Login user and return session credentials
 */
export async function loginUser(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<LoginResult> {
  const csrfToken = await getCsrfToken(request);

  const response = await request.post(`${API_BASE_URL}/api/v2/auth/login`, {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken
    },
    data: { email, password }
  });

  if (response.status() !== 200) {
    throw new Error(`Login failed: ${response.status()} ${await response.text()}`);
  }

  const data = await response.json();

  return {
    sessionId: data.session_id,
    csrfToken,
    userId: data.user.id,
    userRole: data.user.role,
    userEmail: data.user.email
  };
}

/**
 * Create a test patient
 */
export async function createPatient(
  request: APIRequestContext,
  auth: LoginResult,
  patientData: CreatePatientData
): Promise<any> {
  const response = await request.post(`${API_BASE_URL}/api/v2/patients`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': auth.sessionId,
      'X-CSRF-Token': auth.csrfToken
    },
    data: patientData
  });

  if (![200, 201].includes(response.status())) {
    throw new Error(`Failed to create patient: ${response.status()} ${await response.text()}`);
  }

  return await response.json();
}

/**
 * Create a test appointment
 */
export async function createAppointment(
  request: APIRequestContext,
  auth: LoginResult,
  appointmentData: CreateAppointmentData
): Promise<any> {
  const response = await request.post(`${API_BASE_URL}/api/v2/appointments`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': auth.sessionId,
      'X-CSRF-Token': auth.csrfToken
    },
    data: appointmentData
  });

  if (![200, 201].includes(response.status())) {
    throw new Error(`Failed to create appointment: ${response.status()} ${await response.text()}`);
  }

  return await response.json();
}

/**
 * Create a test treatment
 */
export async function createTreatment(
  request: APIRequestContext,
  auth: LoginResult,
  treatmentData: CreateTreatmentData
): Promise<any> {
  const response = await request.post(`${API_BASE_URL}/api/v2/treatments`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': auth.sessionId,
      'X-CSRF-Token': auth.csrfToken
    },
    data: treatmentData
  });

  if (![200, 201].includes(response.status())) {
    throw new Error(`Failed to create treatment: ${response.status()} ${await response.text()}`);
  }

  return await response.json();
}

/**
 * Create a test medication
 */
export async function createMedication(
  request: APIRequestContext,
  auth: LoginResult,
  medicationData: CreateMedicationData
): Promise<any> {
  const response = await request.post(`${API_BASE_URL}/api/v2/medications`, {
    headers: {
      'Content-Type': 'application/json',
      'X-Session-ID': auth.sessionId,
      'X-CSRF-Token': auth.csrfToken
    },
    data: medicationData
  });

  if (![200, 201].includes(response.status())) {
    throw new Error(`Failed to create medication: ${response.status()} ${await response.text()}`);
  }

  return await response.json();
}

/**
 * Delete a resource (admin only)
 */
export async function deleteResource(
  request: APIRequestContext,
  auth: LoginResult,
  endpoint: string,
  resourceId: string
): Promise<boolean> {
  const response = await request.delete(`${API_BASE_URL}${endpoint}/${resourceId}`, {
    headers: {
      'X-Session-ID': auth.sessionId,
      'X-CSRF-Token': auth.csrfToken
    }
  });

  return [200, 204].includes(response.status());
}

/**
 * Generate random test email
 */
export function generateTestEmail(prefix: string = 'test'): string {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 10000);
  return `${prefix}.${timestamp}.${random}@test.example.com`;
}

/**
 * Generate random Brazilian phone number (E.164)
 */
export function generateBrazilianPhone(): string {
  const ddd = Math.floor(Math.random() * 90) + 10; // 10-99
  const number = Math.floor(Math.random() * 900000000) + 100000000; // 9 digits
  return `+55${ddd}${number}`;
}

/**
 * Generate random CPF (Brazilian tax ID)
 */
export function generateCPF(): string {
  const numbers = Array(9).fill(0).map(() => Math.floor(Math.random() * 10));

  // Calculate first verification digit
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += numbers[i] * (10 - i);
  }
  let digit1 = 11 - (sum % 11);
  if (digit1 >= 10) digit1 = 0;

  // Calculate second verification digit
  sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += numbers[i] * (11 - i);
  }
  sum += digit1 * 2;
  let digit2 = 11 - (sum % 11);
  if (digit2 >= 10) digit2 = 0;

  return [...numbers, digit1, digit2].join('');
}

/**
 * Format date for API (YYYY-MM-DD)
 */
export function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Get future date (days from now)
 */
export function getFutureDate(daysFromNow: number): string {
  const date = new Date();
  date.setDate(date.getDate() + daysFromNow);
  return formatDate(date);
}

/**
 * Get past date (days ago)
 */
export function getPastDate(daysAgo: number): string {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return formatDate(date);
}

/**
 * Wait for a condition to be true
 */
export async function waitForCondition(
  condition: () => Promise<boolean>,
  timeoutMs: number = 5000,
  intervalMs: number = 100
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    if (await condition()) {
      return true;
    }
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  return false;
}

/**
 * Retry an operation with exponential backoff
 */
export async function retryOperation<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error as Error;

      if (attempt < maxRetries - 1) {
        const delay = baseDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError || new Error('Operation failed after retries');
}

/**
 * Test credentials for different user roles
 */
export const TEST_USERS = {
  doctor: {
    email: 'doctor@example.com',
    password: 'password123'
  },
  admin: {
    email: 'admin@example.com',
    password: 'admin123'
  },
  nurse: {
    email: 'nurse@example.com',
    password: 'nurse123'
  }
};

/**
 * Validate UUID format
 */
export function isValidUUID(uuid: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(uuid);
}

/**
 * Validate E.164 phone format
 */
export function isValidE164Phone(phone: string): boolean {
  const e164Regex = /^\+[1-9]\d{1,14}$/;
  return e164Regex.test(phone);
}

/**
 * Validate email format
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validate CPF format
 */
export function isValidCPF(cpf: string): boolean {
  const cleanCPF = cpf.replace(/\D/g, '');
  return cleanCPF.length === 11;
}

/**
 * Assert response has expected shape
 */
export function assertResponseShape(data: any, expectedFields: string[]): void {
  expectedFields.forEach(field => {
    if (!(field in data)) {
      throw new Error(`Missing expected field: ${field}`);
    }
  });
}

/**
 * Extract pagination info from list response
 */
export interface PaginationInfo {
  total: number;
  hasNext: boolean;
  nextCursor?: string;
  itemCount: number;
}

export function extractPaginationInfo(response: any): PaginationInfo {
  return {
    total: response.total || 0,
    hasNext: response.has_next || false,
    nextCursor: response.next_cursor,
    itemCount: response.items?.length || 0
  };
}
