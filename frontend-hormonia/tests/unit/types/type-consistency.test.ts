/**
 * Type consistency tests for Phase 1 frontend corrections.
 *
 * Tests:
 * - Patient.flow_state type exists
 * - Quiz.response_value Union type handling
 * - Admin types compile correctly
 * - Type guards work correctly
 *
 * Type Safety Fix: Ensure frontend types match backend exactly
 */

import { describe, it, expect, beforeEach } from 'vitest'
import type {
  Patient,
  PatientFlowState,
  PatientCreateRequest,
  PatientUpdateRequest,
  QuizResponseValue,
  QuizQuestionResponse,
  AdminUser,
  UserRole,
  Permission,
  Role,
} from '@/types/admin'

describe('Patient Type Consistency', () => {
  describe('PatientFlowState', () => {
    it('should have all required flow states', () => {
      const validStates: PatientFlowState[] = [
        'onboarding',
        'active',
        'paused',
        'completed',
        'cancelled',
      ]

      // Type-level check - should compile
      validStates.forEach((state) => {
        expect(state).toBeDefined()
      })
    })

    it('should match backend enum values', () => {
      // Backend FlowState values
      const backendValues = ['onboarding', 'active', 'paused', 'completed', 'cancelled']

      // Type assertion that frontend matches backend
      const frontendState: PatientFlowState = 'onboarding'
      expect(backendValues).toContain(frontendState)
    })
  })

  describe('Patient Interface', () => {
    it('should have flow_state field', () => {
      const patient: Patient = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        doctor_id: '123e4567-e89b-12d3-a456-426614174001',
        phone: '+5511999999999',
        name: 'Test Patient',
        email: 'patient@test.com',
        birth_date: '1990-01-01',
        treatment_type: 'Chemotherapy',
        treatment_start_date: '2024-01-01',
        flow_state: 'active', // CRITICAL: This field must exist
        current_day: 5,
        cpf: '12345678901',
        diagnosis: 'Stage II',
        treatment_phase: 'Active treatment',
        doctor_notes: 'Patient responding well',
        patient_data: {},
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-01T00:00:00-03:00',
      }

      expect(patient.flow_state).toBeDefined()
      expect(patient.flow_state).toBe('active')
    })

    it('should accept all flow_state values', () => {
      const flowStates: PatientFlowState[] = [
        'onboarding',
        'active',
        'paused',
        'completed',
        'cancelled',
      ]

      flowStates.forEach((state) => {
        const patient: Partial<Patient> = {
          flow_state: state,
        }
        expect(patient.flow_state).toBe(state)
      })
    })

    it('should have doctor_id as string (UUID)', () => {
      const patient: Patient = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        doctor_id: '123e4567-e89b-12d3-a456-426614174001',
        phone: '+5511999999999',
        name: 'Test Patient',
        email: null,
        birth_date: null,
        treatment_type: null,
        treatment_start_date: null,
        flow_state: 'onboarding',
        current_day: 0,
        cpf: null,
        diagnosis: null,
        treatment_phase: null,
        doctor_notes: null,
        patient_data: null,
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-01T00:00:00-03:00',
      }

      expect(typeof patient.doctor_id).toBe('string')
      expect(patient.doctor_id).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
      )
    })

    it('should allow null values for optional fields', () => {
      const patient: Patient = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        doctor_id: '123e4567-e89b-12d3-a456-426614174001',
        phone: '+5511999999999',
        name: 'Minimal Patient',
        email: null,
        birth_date: null,
        treatment_type: null,
        treatment_start_date: null,
        flow_state: 'onboarding',
        current_day: 0,
        cpf: null,
        diagnosis: null,
        treatment_phase: null,
        doctor_notes: null,
        patient_data: null,
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-01T00:00:00-03:00',
      }

      expect(patient.email).toBeNull()
      expect(patient.cpf).toBeNull()
      expect(patient.diagnosis).toBeNull()
    })
  })

  describe('Patient Create/Update Requests', () => {
    it('should accept flow_state in update request', () => {
      const updateRequest: PatientUpdateRequest = {
        flow_state: 'active',
      }

      expect(updateRequest.flow_state).toBe('active')
    })

    it('should not require flow_state in create request', () => {
      const createRequest: PatientCreateRequest = {
        phone: '+5511999999999',
        name: 'New Patient',
      }

      // flow_state is optional in create (defaults to onboarding on backend)
      expect(createRequest).toBeDefined()
    })
  })
})

describe('Quiz Response Value Type', () => {
  describe('QuizResponseValue Union Type', () => {
    it('should accept string values', () => {
      const value: QuizResponseValue = 'Yes'
      expect(typeof value).toBe('string')
    })

    it('should accept number values', () => {
      const intValue: QuizResponseValue = 42
      const floatValue: QuizResponseValue = 3.14

      expect(typeof intValue).toBe('number')
      expect(typeof floatValue).toBe('number')
    })

    it('should accept boolean values', () => {
      const value: QuizResponseValue = true
      expect(typeof value).toBe('boolean')
    })

    it('should accept array values', () => {
      const stringArray: QuizResponseValue = ['option1', 'option2', 'option3']
      const numberArray: QuizResponseValue = [1, 2, 3]
      const mixedArray: QuizResponseValue = ['text', 1, true]

      expect(Array.isArray(stringArray)).toBe(true)
      expect(Array.isArray(numberArray)).toBe(true)
      expect(Array.isArray(mixedArray)).toBe(true)
    })

    it('should accept object/dict values', () => {
      const value: QuizResponseValue = {
        scale: 5,
        comments: 'Good experience',
      }

      expect(typeof value).toBe('object')
      expect(value).toHaveProperty('scale')
    })

    it('should accept complex nested structures', () => {
      const complexValue: QuizResponseValue = {
        answers: ['a', 'b', 'c'],
        score: 85,
        passed: true,
        metadata: {
          duration: 120,
          attempts: 1,
        },
      }

      expect(complexValue).toHaveProperty('answers')
      expect(complexValue).toHaveProperty('metadata')
    })
  })

  describe('QuizQuestionResponse', () => {
    it('should use QuizResponseValue for response_value', () => {
      const response: QuizQuestionResponse = {
        question_id: 'q1',
        question_text: 'How do you feel?',
        response_value: 'Good', // String
        response_type: 'text',
        answered_at: '2024-01-01T12:00:00-03:00',
      }

      expect(response.response_value).toBe('Good')
    })

    it('should accept different response_value types', () => {
      const textResponse: QuizQuestionResponse = {
        question_id: 'q1',
        question_text: 'Text question',
        response_value: 'Answer text',
        response_type: 'text',
        answered_at: '2024-01-01T12:00:00-03:00',
      }

      const numberResponse: QuizQuestionResponse = {
        question_id: 'q2',
        question_text: 'Scale question',
        response_value: 7,
        response_type: 'scale',
        answered_at: '2024-01-01T12:00:00-03:00',
      }

      const multiChoiceResponse: QuizQuestionResponse = {
        question_id: 'q3',
        question_text: 'Multi-choice question',
        response_value: ['option1', 'option2'],
        response_type: 'multi_choice',
        answered_at: '2024-01-01T12:00:00-03:00',
      }

      expect(textResponse.response_value).toBe('Answer text')
      expect(numberResponse.response_value).toBe(7)
      expect(Array.isArray(multiChoiceResponse.response_value)).toBe(true)
    })
  })
})

describe('Admin RBAC Types', () => {
  describe('AdminUser Interface', () => {
    it('should have role field with extended types', () => {
      const adminUser: AdminUser = {
        id: '123',
        email: 'admin@test.com',
        full_name: 'Admin User',
        role: 'admin',
        is_active: true,
        permissions: ['users:read', 'users:write'],
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-01T00:00:00-03:00',
        last_login: '2024-01-01T12:00:00-03:00',
        login_count: 10,
        two_factor_enabled: false,
        failed_login_attempts: 0,
        locked_until: null,
      }

      expect(adminUser.role).toBe('admin')
      expect(adminUser.permissions).toBeInstanceOf(Array)
    })

    it('should accept all role types', () => {
      const roles = [
        'doctor',
        'admin',
        'nurse',
        'patient',
        'researcher',
        'coordinator',
        'super_admin',
      ]

      roles.forEach((role) => {
        const user: Partial<AdminUser> = {
          role: role as AdminUser['role'],
        }
        expect(user.role).toBe(role)
      })
    })
  })

  describe('Permission Interface', () => {
    it('should have resource and action fields', () => {
      const permission: Permission = {
        id: 'perm1',
        name: 'Read Patients',
        resource: 'patients',
        action: 'read',
        description: 'Permission to read patient data',
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-01T00:00:00-03:00',
      }

      expect(permission.resource).toBe('patients')
      expect(permission.action).toBe('read')
    })

    it('should accept all resource types', () => {
      const resources = [
        'patients',
        'users',
        'messages',
        'quiz',
        'reports',
        'analytics',
        'settings',
        'flows',
        'templates',
        'webhooks',
        'alerts',
        'admin',
        'system',
        'all',
      ]

      resources.forEach((resource) => {
        const permission: Partial<Permission> = {
          resource: resource as Permission['resource'],
        }
        expect(permission.resource).toBe(resource)
      })
    })

    it('should accept all action types', () => {
      const actions = ['create', 'read', 'update', 'delete', 'list', 'execute', 'manage', 'all']

      actions.forEach((action) => {
        const permission: Partial<Permission> = {
          action: action as Permission['action'],
        }
        expect(permission.action).toBe(action)
      })
    })
  })

  describe('Role Interface', () => {
    it('should have permissions array', () => {
      const role: Role = {
        id: 'role1',
        name: 'Doctor',
        description: 'Doctor role with patient access',
        permissions: [
          {
            id: 'p1',
            name: 'Read Patients',
            resource: 'patients',
            action: 'read',
            description: 'Read patient data',
            created_at: '2024-01-01T00:00:00-03:00',
            updated_at: '2024-01-01T00:00:00-03:00',
          },
        ],
        is_system: true,
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-01T00:00:00-03:00',
      }

      expect(role.permissions).toBeInstanceOf(Array)
      expect(role.permissions[0]).toHaveProperty('resource')
      expect(role.permissions[0]).toHaveProperty('action')
    })
  })
})

describe('Type Guards and Validation', () => {
  describe('UUID Validation', () => {
    it('should validate UUID format', () => {
      const validUUID = '123e4567-e89b-12d3-a456-426614174000'
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

      expect(validUUID).toMatch(uuidRegex)
    })

    it('should reject invalid UUIDs', () => {
      const invalidUUIDs = [
        'not-a-uuid',
        '12345',
        'g23e4567-e89b-12d3-a456-426614174000', // invalid char
        '123e4567-e89b-12d3-a456', // too short
      ]

      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

      invalidUUIDs.forEach((invalid) => {
        expect(invalid).not.toMatch(uuidRegex)
      })
    })
  })

  describe('Flow State Validation', () => {
    const isValidFlowState = (state: string): state is PatientFlowState => {
      const validStates: PatientFlowState[] = [
        'onboarding',
        'active',
        'paused',
        'completed',
        'cancelled',
      ]
      return validStates.includes(state as PatientFlowState)
    }

    it('should validate correct flow states', () => {
      expect(isValidFlowState('active')).toBe(true)
      expect(isValidFlowState('onboarding')).toBe(true)
    })

    it('should reject invalid flow states', () => {
      expect(isValidFlowState('invalid')).toBe(false)
      expect(isValidFlowState('ACTIVE')).toBe(false) // Case sensitive
    })
  })

  describe('Quiz Response Type Guards', () => {
    const isStringResponse = (value: QuizResponseValue): value is string => {
      return typeof value === 'string'
    }

    const isNumberResponse = (value: QuizResponseValue): value is number => {
      return typeof value === 'number'
    }

    const isArrayResponse = (value: QuizResponseValue): value is Array<any> => {
      return Array.isArray(value)
    }

    it('should correctly identify string responses', () => {
      const value: QuizResponseValue = 'text answer'
      expect(isStringResponse(value)).toBe(true)
      expect(isNumberResponse(value)).toBe(false)
    })

    it('should correctly identify number responses', () => {
      const value: QuizResponseValue = 42
      expect(isNumberResponse(value)).toBe(true)
      expect(isStringResponse(value)).toBe(false)
    })

    it('should correctly identify array responses', () => {
      const value: QuizResponseValue = ['a', 'b', 'c']
      expect(isArrayResponse(value)).toBe(true)
      expect(isStringResponse(value)).toBe(false)
    })
  })
})

describe('API Response Type Compatibility', () => {
  describe('Patient API Response', () => {
    it('should match backend response structure', () => {
      // Simulated backend response
      const backendResponse = {
        id: '123e4567-e89b-12d3-a456-426614174000',
        doctor_id: '123e4567-e89b-12d3-a456-426614174001',
        phone: '+5511999999999',
        name: 'Test Patient',
        email: 'patient@test.com',
        birth_date: '1990-01-01',
        treatment_type: 'Chemotherapy',
        treatment_start_date: '2024-01-01',
        flow_state: 'active', // Backend includes this
        current_day: 5,
        cpf: '12345678901',
        diagnosis: 'Stage II',
        treatment_phase: 'Active',
        doctor_notes: 'Notes',
        patient_data: {},
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-01T00:00:00-03:00',
      }

      // Frontend should be able to consume this
      const patient: Patient = backendResponse

      expect(patient.flow_state).toBe('active')
      expect(patient.doctor_id).toBeDefined()
    })
  })

  describe('Quiz Response API Compatibility', () => {
    it('should handle backend quiz response structure', () => {
      const backendQuizResponse = {
        question_id: 'q1',
        question_text: 'How are you?',
        response_value: 'Good', // Backend sends Union type
        response_type: 'text',
        answered_at: '2024-01-01T12:00:00-03:00',
      }

      const quizResponse: QuizQuestionResponse = backendQuizResponse as QuizQuestionResponse

      expect(quizResponse.response_value).toBe('Good')
    })
  })
})
