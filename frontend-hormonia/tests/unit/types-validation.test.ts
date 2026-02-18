/**
 * Type validation tests for core application types
 * Ensures all type definitions are consistent and complete
 */

import type {
  User,
  Patient,
  PaginatedResponse,
  SuccessResponse,
  ErrorResponse,
  ApiSuccessResponse,
  ApiErrorResponse,
  WebSocketMessage
} from '../../src/lib/types/api'

import type {
  WebSocketEventType,
  WebSocketConnectionState,
  PatientEventData,
  MessageEventData,
  FlowEventData
} from '../../src/lib/types/websocket'

import type {
  User as AppUser,
  Patient as AppPatient
} from '../../src/types/index'

// Test type compatibility and completeness
describe('Type Definitions Validation', () => {

  it('should have complete User interface with token property', () => {
    const user: User = {
      id: '1',
      email: 'test@example.com',
      name: 'Test User',
      role: 'doctor',
      token: 'jwt-token-123', // Should exist
      created_at: '2024-01-01T00:00:00-03:00',
      updated_at: '2024-01-01T00:00:00-03:00'
    }

    expect(user.token).toBeDefined()
    expect(typeof user.token).toBe('string')
  })

  it('should have complete Patient interface with current_day property', () => {
    const patient: Patient = {
      id: '1',
      name: 'Test Patient',
      phone: '+5511999999999',
      whatsapp_number: '+5511999999999',
      treatment_type: 'oncology',
      enrollment_date: '2024-01-01T00:00:00-03:00',
      status: 'active',
      current_day: 15, // Should exist
      created_at: '2024-01-01T00:00:00-03:00',
      updated_at: '2024-01-01T00:00:00-03:00'
    }

    expect(patient.current_day).toBeDefined()
    expect(typeof patient.current_day).toBe('number')
  })

  it('should have consistent PaginatedResponse interface', () => {
    const response: PaginatedResponse<Patient> = {
      data: [],
      total: 0,
      page: 1,
      limit: 10,
      has_more: false
    }

    expect(response['data']).toBeDefined()
    expect(Array.isArray(response['data'])).toBe(true)
  })

  it('should have consistent SuccessResponse interface', () => {
    const response: SuccessResponse = {
      success: true,
      message: 'Operation successful',
      data: { id: '1' }
    }

    expect(response.success).toBe(true)
  })

  it('should have consistent ErrorResponse interface', () => {
    const response: ErrorResponse = {
      error: 'VALIDATION_ERROR',
      message: 'Invalid input data',
      status_code: 400,
      details: { field: 'email' }
    }

    expect(response.error).toBeDefined()
    expect(response.status_code).toBe(400)
  })

  it('should have ApiSuccessResponse with timestamp', () => {
    const response: ApiSuccessResponse<{ id: string }> = {
      success: true,
      message: 'Success',
      data: { id: '1' },
      timestamp: '2024-01-01T00:00:00-03:00'
    }

    expect(response.timestamp).toBeDefined()
  })

  it('should have ApiErrorResponse with timestamp', () => {
    const response: ApiErrorResponse = {
      success: false,
      error: 'API_ERROR',
      message: 'API error occurred',
      timestamp: '2024-01-01T00:00:00-03:00'
    }

    expect(response.success).toBe(false)
    expect(response.timestamp).toBeDefined()
  })

  it('should have WebSocketMessage interface', () => {
    const message: WebSocketMessage<PatientEventData> = {
      type: 'patient_updated',
      data: {
        patient_id: '1',
        patient_name: 'Test Patient',
        changes: { status: 'active' }
      },
      timestamp: '2024-01-01T00:00:00-03:00',
      id: 'msg-1'
    }

    expect(message.type).toBeDefined()
    expect(message.data).toBeDefined()
  })

  it('should have WebSocket event types', () => {
    const eventType: WebSocketEventType = 'patient_updated'
    expect(typeof eventType).toBe('string')
  })

  it('should have WebSocket connection state', () => {
    const state: WebSocketConnectionState = {
      isConnected: true,
      isConnecting: false,
      isAuthenticated: true,
      reconnectAttempts: 0,
      lastError: null,
      connectionId: 'conn-123'
    }

    expect(state.isConnected).toBeDefined()
    expect(state.connectionId).toBeDefined()
  })

  it('should have Patient event data', () => {
    const eventData: PatientEventData = {
      patient_id: '1',
      patient_name: 'Test Patient',
      changes: { status: 'active' }
    }

    expect(eventData.patient_id).toBeDefined()
  })

  it('should have Message event data', () => {
    const eventData: MessageEventData = {
      message_id: '1',
      patient_id: '1',
      direction: 'outbound',
      type: 'text',
      content: 'Hello',
      status: 'sent'
    }

    expect(eventData.message_id).toBeDefined()
    expect(eventData.direction).toBe('outbound')
  })

  it('should have Flow event data', () => {
    const eventData: FlowEventData = {
      patient_id: '1',
      flow_type: 'onboarding',
      current_day: 5,
      is_paused: false,
      enrollment_date: '2024-01-01T00:00:00-03:00'
    }

    expect(eventData.patient_id).toBeDefined()
    expect(eventData.current_day).toBe(5)
  })

  it('should have compatible application User type', () => {
    const appUser: AppUser = {
      id: '1',
      email: 'test@example.com',
      name: 'Test User',
      role: 'doctor',
      token: 'jwt-token-123', // Should exist
      createdAt: '2024-01-01T00:00:00-03:00',
      updatedAt: '2024-01-01T00:00:00-03:00'
    }

    expect(appUser.token).toBeDefined()
  })

  it('should have compatible application Patient type', () => {
    const appPatient: AppPatient = {
      id: '1',
      name: 'Test Patient',
      email: 'patient@example.com',
      phone: '+5511999999999',
      dateOfBirth: '1990-01-01',
      status: 'active',
      current_day: 15, // Should exist
      createdAt: '2024-01-01T00:00:00-03:00',
      updatedAt: '2024-01-01T00:00:00-03:00'
    }

    expect(appPatient.current_day).toBeDefined()
    expect(typeof appPatient.current_day).toBe('number')
  })
})
