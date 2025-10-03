import { supabase } from './supabase'
import type { Patient, PaginatedResponse } from './types/api'

// Export the PaginatedResponse type for external use
export type { PaginatedResponse } from './types/api'

const API_BASE_URL = import.meta.env['VITE_API_BASE_URL'] || 'https://backend-production-e0bd.up.railway.app'

// Helper function to handle API responses
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.text()
    throw new Error(error || `HTTP error! status: ${response.status}`)
  }
  return response.json()
}

// Helper function to get auth token
async function getAuthToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token || null
}

// Helper function to create headers
async function createHeaders(): Promise<HeadersInit> {
  const token = await getAuthToken()
  return {
    'Content-Type': 'application/json',
    ...(token && { ['Authorization']: `Bearer ${token}` })
  }
}

export const api = {
  // Patients API
  async getPatients(params?: any): Promise<PaginatedResponse<Patient>> {
    const queryString = params ? '?' + new URLSearchParams(params).toString() : ''
    const response = await fetch(`${API_BASE_URL}/api/v1/patients${queryString}`, {
      headers: await createHeaders()
    })
    return handleResponse<PaginatedResponse<Patient>>(response)
  },

  async getPatient(id: string): Promise<Patient> {
    const response = await fetch(`${API_BASE_URL}/api/v1/patients/${id}`, {
      headers: await createHeaders()
    })
    return handleResponse<Patient>(response)
  },

  async createPatient(data: Partial<Patient>): Promise<Patient> {
    const response = await fetch(`${API_BASE_URL}/api/v1/patients`, {
      method: 'POST',
      headers: await createHeaders(),
      body: JSON.stringify(data)
    })
    return handleResponse<Patient>(response)
  },

  async updatePatient(id: string, data: Partial<Patient>): Promise<Patient> {
    const response = await fetch(`${API_BASE_URL}/api/v1/patients/${id}`, {
      method: 'PUT',
      headers: await createHeaders(),
      body: JSON.stringify(data)
    })
    return handleResponse<Patient>(response)
  },

  async deletePatient(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/patients/${id}`, {
      method: 'DELETE',
      headers: await createHeaders()
    })
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
  },

  // Auth API
  async login(email: string, password: string) {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    })
    return handleResponse(response)
  },

  async logout() {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
      method: 'POST',
      headers: await createHeaders()
    })
    return handleResponse(response)
  },

  async me() {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: await createHeaders()
    })
    return handleResponse(response)
  },

  async refresh() {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: await createHeaders()
    })
    return handleResponse(response)
  },

  // Quiz API
  async getQuizzes() {
    const response = await fetch(`${API_BASE_URL}/api/v1/quiz/templates`, {
      headers: await createHeaders()
    })
    return handleResponse(response)
  },

  async createQuizSession(patientId: string, templateId: string) {
    const response = await fetch(`${API_BASE_URL}/api/v1/quiz/sessions`, {
      method: 'POST',
      headers: await createHeaders(),
      body: JSON.stringify({ patient_id: patientId, template_id: templateId })
    })
    return handleResponse(response)
  },

  async submitQuizResponse(sessionId: string, responses: any) {
    const response = await fetch(`${API_BASE_URL}/api/v1/quiz/sessions/${sessionId}/responses`, {
      method: 'POST',
      headers: await createHeaders(),
      body: JSON.stringify(responses)
    })
    return handleResponse(response)
  },

  // Reports API
  async generateReport(patientId: string, type: string) {
    const response = await fetch(`${API_BASE_URL}/api/v1/reports/generate`, {
      method: 'POST',
      headers: await createHeaders(),
      body: JSON.stringify({ patient_id: patientId, report_type: type })
    })
    return handleResponse(response)
  },

  async getReports(patientId?: string) {
    const queryString = patientId ? `?patient_id=${patientId}` : ''
    const response = await fetch(`${API_BASE_URL}/api/v1/reports${queryString}`, {
      headers: await createHeaders()
    })
    return handleResponse(response)
  }
}

export default api