/**
 * Normalizers Test Suite
 * Tests for API data normalization functions
 */

import {
  normalizeUser,
  denormalizeUser,
  normalizePatient,
  denormalizePatient,
  normalizePatientList,
  normalizeDate,
  normalizeBoolean,
  normalizeArray,
  normalizeEnum,
  isBackendUser,
  isBackendPatient,
  normalizePaginatedResponse,
  type BackendUser,
  type BackendPatient,
  type PatientStatus,
} from '../normalizers'

describe('User Normalization', () => {
  describe('normalizeUser', () => {
    it('should map full_name to name', () => {
      const backendUser: BackendUser = {
        id: '123',
        email: 'doctor@example.com',
        full_name: 'Dr. Maria Silva',
        role: 'doctor',
        is_active: true,
        created_at: '2025-01-01T00:00:00-03:00',
      }

      const frontendUser = normalizeUser(backendUser)

      expect(frontendUser.name).toBe('Dr. Maria Silva')
      expect(frontendUser.full_name).toBe('Dr. Maria Silva')
    })

    it('should use name field when full_name is null', () => {
      const backendUser: BackendUser = {
        id: '123',
        email: 'doctor@example.com',
        name: 'Dr. Maria',
        full_name: null,
        role: 'doctor',
        is_active: true,
        created_at: '2025-01-01T00:00:00-03:00',
      }

      const frontendUser = normalizeUser(backendUser)

      expect(frontendUser.name).toBe('Dr. Maria')
      expect(frontendUser.full_name).toBe('Dr. Maria')
    })

    it('should fallback to email when no name provided', () => {
      const backendUser: BackendUser = {
        id: '123',
        email: 'doctor@example.com',
        role: 'doctor',
        is_active: true,
        created_at: '2025-01-01T00:00:00-03:00',
      }

      const frontendUser = normalizeUser(backendUser)

      expect(frontendUser.name).toBe('doctor@example.com')
      expect(frontendUser.full_name).toBe('doctor@example.com')
    })

    it('should ensure permissions array exists', () => {
      const backendUser: BackendUser = {
        id: '123',
        email: 'doctor@example.com',
        full_name: 'Dr. Maria',
        role: 'doctor',
        is_active: true,
        created_at: '2025-01-01T00:00:00-03:00',
      }

      const frontendUser = normalizeUser(backendUser)

      expect(frontendUser.permissions).toEqual([])
    })

    it('should preserve existing permissions', () => {
      const backendUser: BackendUser = {
        id: '123',
        email: 'doctor@example.com',
        full_name: 'Dr. Maria',
        role: 'doctor',
        permissions: ['read:patients', 'write:patients'],
        is_active: true,
        created_at: '2025-01-01T00:00:00-03:00',
      }

      const frontendUser = normalizeUser(backendUser)

      expect(frontendUser.permissions).toEqual(['read:patients', 'write:patients'])
    })

    it('should drop firebase-auth residue from normalized users', () => {
      const backendUser = {
        id: '123',
        email: 'doctor@example.com',
        full_name: 'Dr. Maria',
        role: 'doctor',
        is_active: true,
        created_at: '2025-01-01T00:00:00-03:00',
        firebase_uid: 'legacy-firebase-uid',
      } as BackendUser & { firebase_uid?: string }

      const frontendUser = normalizeUser(backendUser)

      expect(frontendUser).not.toHaveProperty('firebase_uid')
    })
  })

  describe('denormalizeUser', () => {
    it('should map name to full_name', () => {
      const frontendUser = {
        name: 'Dr. Maria Silva',
      }

      const backendUser = denormalizeUser(frontendUser)

      expect(backendUser.full_name).toBe('Dr. Maria Silva')
      expect(backendUser.name).toBeUndefined()
    })

    it('should prefer full_name over name', () => {
      const frontendUser = {
        name: 'Dr. Maria',
        full_name: 'Dr. Maria Silva',
      }

      const backendUser = denormalizeUser(frontendUser)

      expect(backendUser.full_name).toBe('Dr. Maria Silva')
    })
  })

  describe('isBackendUser', () => {
    it('should return true for valid backend user', () => {
      const user = {
        id: '123',
        email: 'test@example.com',
        role: 'doctor',
        is_active: true,
      }

      expect(isBackendUser(user)).toBe(true)
    })

    it('should return false for invalid user', () => {
      expect(isBackendUser(null)).toBe(false)
      expect(isBackendUser({})).toBe(false)
      expect(isBackendUser({ id: '123' })).toBe(false)
    })
  })
})

describe('Patient Normalization', () => {
  describe('normalizePatient', () => {
    it('should map flow_state to status', () => {
      const backendPatient: BackendPatient = {
        id: '456',
        name: 'João Silva',
        doctor_id: '789',
        flow_state: 'active',
      }

      const frontendPatient = normalizePatient(backendPatient)

      expect(frontendPatient.status).toBe('active')
      expect(frontendPatient.flow_state).toBe('active')
    })

    it('should use status field when flow_state is null', () => {
      const backendPatient: BackendPatient = {
        id: '456',
        name: 'João Silva',
        doctor_id: '789',
        status: 'paused',
      }

      const frontendPatient = normalizePatient(backendPatient)

      expect(frontendPatient.status).toBe('paused')
      expect(frontendPatient.flow_state).toBe('paused')
    })

    it('should default to active when no status provided', () => {
      const backendPatient: BackendPatient = {
        id: '456',
        name: 'João Silva',
        doctor_id: '789',
      }

      const frontendPatient = normalizePatient(backendPatient)

      expect(frontendPatient.status).toBe('active')
      expect(frontendPatient.flow_state).toBe('active')
    })

    it('should convert null fields to undefined', () => {
      const backendPatient: BackendPatient = {
        id: '456',
        name: 'João Silva',
        doctor_id: '789',
        email: null,
        phone: null,
        cpf: null,
      }

      const frontendPatient = normalizePatient(backendPatient)

      expect(frontendPatient.email).toBeUndefined()
      expect(frontendPatient.phone).toBeUndefined()
      expect(frontendPatient.cpf).toBeUndefined()
    })

    it('should preserve all patient fields', () => {
      const backendPatient: BackendPatient = {
        id: '456',
        name: 'João Silva',
        email: 'joao@example.com',
        phone: '(11) 98765-4321',
        cpf: '123.456.789-00',
        doctor_id: '789',
        flow_state: 'active',
        current_day: 15,
      }

      const frontendPatient = normalizePatient(backendPatient)

      expect(frontendPatient.id).toBe('456')
      expect(frontendPatient.name).toBe('João Silva')
      expect(frontendPatient.email).toBe('joao@example.com')
      expect(frontendPatient.phone).toBe('(11) 98765-4321')
      expect(frontendPatient.cpf).toBe('123.456.789-00')
      expect(frontendPatient.doctor_id).toBe('789')
      expect(frontendPatient.current_day).toBe(15)
    })
  })

  describe('denormalizePatient', () => {
    it('should map status to flow_state', () => {
      const frontendPatient = {
        status: 'paused' as PatientStatus,
      }

      const backendPatient = denormalizePatient(frontendPatient)

      expect(backendPatient.flow_state).toBe('paused')
      expect(backendPatient.status).toBeUndefined()
    })

    it('should prefer flow_state over status', () => {
      const frontendPatient = {
        status: 'paused' as PatientStatus,
        flow_state: 'active',
      }

      const backendPatient = denormalizePatient(frontendPatient)

      expect(backendPatient.flow_state).toBe('active')
    })
  })

  describe('normalizePatientList', () => {
    it('should normalize array of patients', () => {
      const backendPatients: BackendPatient[] = [
        { id: '1', name: 'Patient 1', doctor_id: '100', flow_state: 'active' },
        { id: '2', name: 'Patient 2', doctor_id: '100', flow_state: 'paused' },
      ]

      const frontendPatients = normalizePatientList(backendPatients)

      expect(frontendPatients).toHaveLength(2)
      expect(frontendPatients[0].status).toBe('active')
      expect(frontendPatients[1].status).toBe('paused')
    })

    it('should handle empty array', () => {
      const frontendPatients = normalizePatientList([])

      expect(frontendPatients).toEqual([])
    })
  })

  describe('isBackendPatient', () => {
    it('should return true for valid backend patient', () => {
      const patient = {
        id: '123',
        name: 'Patient',
        doctor_id: '456',
      }

      expect(isBackendPatient(patient)).toBe(true)
    })

    it('should return false for invalid patient', () => {
      expect(isBackendPatient(null)).toBe(false)
      expect(isBackendPatient({})).toBe(false)
      expect(isBackendPatient({ id: '123' })).toBe(false)
    })
  })
})

describe('Helper Functions', () => {
  describe('normalizeDate', () => {
    it('should convert date string to ISO format', () => {
      const date = normalizeDate('2025-01-15')

      expect(date).toMatch(/2025-01-15T\d{2}:\d{2}:\d{2}\.\d{3}Z/)
    })

    it('should return undefined for null', () => {
      expect(normalizeDate(null)).toBeUndefined()
      expect(normalizeDate(undefined)).toBeUndefined()
    })

    it('should return undefined for invalid date', () => {
      expect(normalizeDate('invalid-date')).toBeUndefined()
    })
  })

  describe('normalizeBoolean', () => {
    it('should normalize various boolean representations', () => {
      expect(normalizeBoolean(true)).toBe(true)
      expect(normalizeBoolean(false)).toBe(false)
      expect(normalizeBoolean('true')).toBe(true)
      expect(normalizeBoolean('false')).toBe(false)
      expect(normalizeBoolean(1)).toBe(true)
      expect(normalizeBoolean(0)).toBe(false)
    })

    it('should use default value for null/undefined', () => {
      expect(normalizeBoolean(null)).toBe(false)
      expect(normalizeBoolean(undefined)).toBe(false)
      expect(normalizeBoolean(null, true)).toBe(true)
    })
  })

  describe('normalizeArray', () => {
    it('should ensure array output', () => {
      expect(normalizeArray(['a', 'b'])).toEqual(['a', 'b'])
      expect(normalizeArray('single')).toEqual(['single'])
      expect(normalizeArray(null)).toEqual([])
      expect(normalizeArray(undefined)).toEqual([])
    })

    it('should use custom default', () => {
      expect(normalizeArray(null, ['default'])).toEqual(['default'])
    })
  })

  describe('normalizeEnum', () => {
    const allowed = ['active', 'inactive', 'paused'] as const

    it('should validate enum values', () => {
      expect(normalizeEnum('active', allowed, 'active')).toBe('active')
      expect(normalizeEnum('paused', allowed, 'active')).toBe('paused')
    })

    it('should use default for invalid values', () => {
      expect(normalizeEnum('invalid', allowed, 'active')).toBe('active')
      expect(normalizeEnum(null, allowed, 'active')).toBe('active')
      expect(normalizeEnum(undefined, allowed, 'active')).toBe('active')
    })
  })
})

describe('Paginated Response Normalization', () => {
  it('should normalize paginated data', () => {
    const response = {
      data: [
        { id: '1', name: 'Patient 1', doctor_id: '100', flow_state: 'active' },
        { id: '2', name: 'Patient 2', doctor_id: '100', flow_state: 'paused' },
      ] as BackendPatient[],
      total: 2,
      has_more: false,
      next_cursor: null,
    }

    const normalized = normalizePaginatedResponse(response, normalizePatient)

    expect(normalized.data).toHaveLength(2)
    expect(normalized.data![0].status).toBe('active')
    expect(normalized.data![1].status).toBe('paused')
    expect(normalized.items).toHaveLength(2)
    expect(normalized.total).toBe(2)
  })

  it('should handle items field for backward compatibility', () => {
    const response = {
      items: [
        { id: '1', name: 'Patient 1', doctor_id: '100', flow_state: 'active' },
      ] as BackendPatient[],
      total: 1,
    }

    const normalized = normalizePaginatedResponse(response, normalizePatient)

    expect(normalized.data).toHaveLength(1)
    expect(normalized.items).toHaveLength(1)
  })

  it('should handle empty response', () => {
    const response = {
      data: [] as BackendPatient[],
      total: 0,
    }

    const normalized = normalizePaginatedResponse(response, normalizePatient)

    expect(normalized.data).toEqual([])
    expect(normalized.items).toEqual([])
  })
})

describe('Integration Tests', () => {
  it('should round-trip user normalization', () => {
    const original: BackendUser = {
      id: '123',
      email: 'test@example.com',
      full_name: 'Test User',
      role: 'doctor',
      is_active: true,
      created_at: '2025-01-01T00:00:00-03:00',
    }

    const frontend = normalizeUser(original)
    const backend = denormalizeUser(frontend)

    expect(backend.full_name).toBe(original.full_name)
    expect(backend.email).toBe(original.email)
    expect(backend.role).toBe(original.role)
  })

  it('should round-trip patient normalization', () => {
    const original: BackendPatient = {
      id: '456',
      name: 'Patient',
      doctor_id: '789',
      flow_state: 'active',
    }

    const frontend = normalizePatient(original)
    const backend = denormalizePatient(frontend)

    expect(backend.flow_state).toBe(original.flow_state)
    expect(backend.name).toBe(original.name)
    expect(backend.doctor_id).toBe(original.doctor_id)
  })
})
