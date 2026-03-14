/**
<<<<<<< HEAD
 * Type validation tests for core application types.
 * Ensures the canonical type ownership surfaces stay stable after the S04
 * compatibility cleanup removed the legacy compat barrel.
 */

import type { User, Patient } from '../../src/types/api'
import type {
  PaginatedResponse,
  ApiResponse as TransportApiResponse,
  ApiErrorResponse as TransportApiErrorResponse,
} from '../../src/lib/api-client/types'
import type {
  ApiResponse as SharedApiResponse,
  ApiErrorResponse as SharedApiErrorResponse,
} from '../../src/types/shared'
=======
 * Type validation tests for core application types
 * Ensures the canonical type ownership surfaces stay stable while the
 * legacy compat barrel remains isolated for S04 cleanup.
 */

import { readFileSync } from 'node:fs'
import path from 'node:path'

import type { User, Patient } from '../../src/types/api'
import type {
  PaginatedResponse,
  ApiResponse,
  ApiErrorResponse,
} from '../../src/lib/api-client/types'
import type { SuccessResponse, ErrorResponse, ApiSuccessResponse } from '../../src/lib/types/api'
>>>>>>> gsd/M003/S03
import type {
  WebSocketMessage,
  WebSocketEventType,
  WebSocketConnectionState,
  PatientEventData,
  MessageEventData,
  FlowEventData,
} from '../../src/types/websocket'

import type { User as AppUser, Patient as AppPatient } from '../../src/types/index'
<<<<<<< HEAD

// Test type compatibility and completeness
describe('Type Definitions Validation', () => {
  it('uses canonical shared and transport type owners after compat cleanup', () => {
    const sharedResponse: SharedApiResponse<{ id: string }> = {
      success: true,
      data: { id: 'shared' },
      message: 'Shared response',
      timestamp: '2024-01-01T00:00:00-03:00',
    }

    const transportResponse: TransportApiResponse<{ id: string }> = {
      success: true,
      data: { id: 'transport' },
      message: 'Transport response',
      timestamp: '2024-01-01T00:00:00-03:00',
    }

    expect(sharedResponse.data?.id).toBe('shared')
    expect(transportResponse.data.id).toBe('transport')
  })
=======

const readRepoFile = (relativePath: string) =>
  readFileSync(path.resolve(process.cwd(), relativePath), 'utf8')

// Test type compatibility and completeness
describe('Type Definitions Validation', () => {
  it('documents the legacy compat barrel as isolated S04 cleanup work', () => {
    const compatSource = readRepoFile('src/lib/types/api.ts')

    expect(compatSource).toContain('compatibility-only for S04 cleanup/tombstoning')
    expect(compatSource).toContain('Do not add new production imports here')
  })

>>>>>>> gsd/M003/S03

  it('should have complete User interface with token property', () => {
    const user: User = {
      id: '1',
      email: 'test@example.com',
      name: 'Test User',
      full_name: 'Test User',
      role: 'doctor',
      permissions: [],
      is_active: true,
<<<<<<< HEAD
      token: 'jwt-token-123',
=======
      token: 'jwt-token-123', // Should exist
>>>>>>> gsd/M003/S03
      created_at: '2024-01-01T00:00:00-03:00',
      updated_at: '2024-01-01T00:00:00-03:00',
    }

    expect(user.token).toBeDefined()
    expect(typeof user.token).toBe('string')
  })

  it('should have complete Patient interface with current_day property', () => {
    const patient: Patient = {
      id: '1',
      name: 'Test Patient',
      phone: '+5511999999999',
      treatment_type: 'oncology',
      treatment_start_date: '2024-01-01T00:00:00-03:00',
      status: 'active',
      flow_state: 'active',
<<<<<<< HEAD
      current_day: 15,
=======
      current_day: 15, // Should exist
>>>>>>> gsd/M003/S03
      created_at: '2024-01-01T00:00:00-03:00',
      updated_at: '2024-01-01T00:00:00-03:00',
    }

    expect(patient.current_day).toBeDefined()
    expect(typeof patient.current_day).toBe('number')
  })

  it('should have consistent PaginatedResponse interface', () => {
    const response: PaginatedResponse<Patient> = {
      data: [],
      items: [],
      total: 0,
      page: 1,
      size: 10,
      has_more: false,
    }

    expect(response.data).toBeDefined()
    expect(Array.isArray(response.data)).toBe(true)
  })

  it('should have consistent ApiResponse interface on the transport barrel', () => {
<<<<<<< HEAD
    const response: TransportApiResponse<{ id: string }> = {
=======
    const response: ApiResponse<{ id: string }> = {
      success: true,
      data: { id: '1' },
      message: 'Operation successful',
      timestamp: '2024-01-01T00:00:00-03:00',
    }

    expect(response.success).toBe(true)
    expect(response.data.id).toBe('1')
  })

  it('should have consistent SuccessResponse interface', () => {
    const response: SuccessResponse = {
>>>>>>> gsd/M003/S03
      success: true,
      data: { id: '1' },
      message: 'Operation successful',
      timestamp: '2024-01-01T00:00:00-03:00',
    }

    expect(response.success).toBe(true)
    expect(response.data.id).toBe('1')
  })

  it('should have consistent shared ApiResponse interface', () => {
    const response: SharedApiResponse<{ id: string }> = {
      success: true,
      message: 'Operation successful',
      data: { id: '1' },
    }

    expect(response.success).toBe(true)
    expect(response.data?.id).toBe('1')
  })

  it('should have consistent shared ApiErrorResponse interface', () => {
    const response: SharedApiErrorResponse = {
      error: 'VALIDATION_ERROR',
      message: 'Invalid input data',
      status_code: 400,
      details: { field: 'email' },
    }

    expect(response.error).toBeDefined()
    expect(response.status_code).toBe(400)
  })

  it('should have shared ApiResponse with timestamp', () => {
    const response: SharedApiResponse<{ id: string }> = {
      success: true,
      message: 'Success',
      data: { id: '1' },
      timestamp: '2024-01-01T00:00:00-03:00',
    }

    expect(response.timestamp).toBeDefined()
  })

  it('should have ApiErrorResponse on the transport barrel', () => {
<<<<<<< HEAD
    const response: TransportApiErrorResponse = {
=======
    const response: ApiErrorResponse = {
>>>>>>> gsd/M003/S03
      error: {
        code: 'API_ERROR',
        message: 'API error occurred',
      },
      timestamp: '2024-01-01T00:00:00-03:00',
    }

    expect(response.error.code).toBe('API_ERROR')
    expect(response.timestamp).toBeDefined()
  })

  it('should have WebSocketMessage interface', () => {
    const message: WebSocketMessage = {
      type: 'patient_updated',
      data: {
        patient_id: '1',
        patient_name: 'Test Patient',
        changes: { status: 'active' },
      } satisfies PatientEventData,
      timestamp: '2024-01-01T00:00:00-03:00',
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
      connectionId: 'conn-123',
    }

    expect(state.isConnected).toBeDefined()
    expect(state.connectionId).toBeDefined()
  })

  it('should have Patient event data', () => {
    const eventData: PatientEventData = {
      patient_id: '1',
      patient_name: 'Test Patient',
      changes: { status: 'active' },
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
      status: 'sent',
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
      enrollment_date: '2024-01-01T00:00:00-03:00',
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
      token: 'jwt-token-123',
      createdAt: '2024-01-01T00:00:00-03:00',
      updatedAt: '2024-01-01T00:00:00-03:00',
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
      current_day: 15,
      createdAt: '2024-01-01T00:00:00-03:00',
      updatedAt: '2024-01-01T00:00:00-03:00',
      flow_state: 'active',
    }

    expect(appPatient.current_day).toBeDefined()
    expect(typeof appPatient.current_day).toBe('number')
  })
})
