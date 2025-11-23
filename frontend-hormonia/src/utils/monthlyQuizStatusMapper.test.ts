/**
 * Test file for monthlyQuizStatusMapper utility
 * Tests the status mapping functionality between backend and UI
 */

import {
  mapBackendStatus,
  mapUIToBackendStatus,
  isValidUIStatus,
  getStatusLabel,
  isBackendStatus,
  isUIStatus
} from './monthlyQuizStatusMapper'

describe('monthlyQuizStatusMapper', () => {
  describe('mapBackendStatus', () => {
    it('should map backend statuses correctly', () => {
      expect(mapBackendStatus('active')).toBe('active')
      expect(mapBackendStatus('expired')).toBe('expired')
      expect(mapBackendStatus('used')).toBe('completed')
      expect(mapBackendStatus('cancelled')).toBe('expired')
    })

    it('should handle case insensitive input', () => {
      expect(mapBackendStatus('ACTIVE')).toBe('active')
      expect(mapBackendStatus('Used')).toBe('completed')
      expect(mapBackendStatus('CANCELLED')).toBe('expired')
    })

    it('should handle whitespace', () => {
      expect(mapBackendStatus(' active ')).toBe('active')
      expect(mapBackendStatus('  used  ')).toBe('completed')
    })

    it('should handle unknown statuses', () => {
      expect(mapBackendStatus('unknown')).toBe('pending')
      expect(mapBackendStatus('')).toBe('pending')
      expect(mapBackendStatus('invalid-status')).toBe('pending')
    })

    it('should handle invalid inputs', () => {
      expect(mapBackendStatus(null as any)).toBe('pending')
      expect(mapBackendStatus(undefined as any)).toBe('pending')
      expect(mapBackendStatus(123 as any)).toBe('pending')
    })

    it('should preserve UI statuses', () => {
      expect(mapBackendStatus('pending')).toBe('pending')
      expect(mapBackendStatus('sent')).toBe('sent')
      expect(mapBackendStatus('accessed')).toBe('accessed')
      expect(mapBackendStatus('not_sent')).toBe('not_sent')
      expect(mapBackendStatus('completed')).toBe('completed')
    })
  })

  describe('mapUIToBackendStatus', () => {
    it('should map UI statuses to backend correctly', () => {
      expect(mapUIToBackendStatus('active')).toBe('active')
      expect(mapUIToBackendStatus('expired')).toBe('expired')
      expect(mapUIToBackendStatus('completed')).toBe('used')
      expect(mapUIToBackendStatus('pending')).toBe('active')
    })

    it('should handle invalid inputs', () => {
      expect(mapUIToBackendStatus('')).toBe('active')
      expect(mapUIToBackendStatus(null as any)).toBe('active')
      expect(mapUIToBackendStatus(undefined as any)).toBe('active')
    })
  })

  describe('isValidUIStatus', () => {
    it('should validate UI statuses correctly', () => {
      expect(isValidUIStatus('active')).toBe(true)
      expect(isValidUIStatus('expired')).toBe(true)
      expect(isValidUIStatus('completed')).toBe(true)
      expect(isValidUIStatus('pending')).toBe(true)
      expect(isValidUIStatus('not_sent')).toBe(true)
      expect(isValidUIStatus('sent')).toBe(true)
      expect(isValidUIStatus('accessed')).toBe(true)
    })

    it('should reject invalid statuses', () => {
      expect(isValidUIStatus('invalid')).toBe(false)
      expect(isValidUIStatus('unknown')).toBe(false)
      expect(isValidUIStatus('')).toBe(false)
    })
  })

  describe('getStatusLabel', () => {
    it('should return correct Portuguese labels', () => {
      expect(getStatusLabel('active')).toBe('Ativo')
      expect(getStatusLabel('expired')).toBe('Expirado')
      expect(getStatusLabel('used')).toBe('Completado') // maps to completed
      expect(getStatusLabel('cancelled')).toBe('Expirado') // maps to expired
      expect(getStatusLabel('pending')).toBe('Pendente')
      expect(getStatusLabel('not_sent')).toBe('Não Enviado')
      expect(getStatusLabel('sent')).toBe('Enviado')
      expect(getStatusLabel('accessed')).toBe('Acessado')
    })

    it('should handle unknown statuses', () => {
      expect(getStatusLabel('unknown')).toBe('Desconhecido')
      expect(getStatusLabel('')).toBe('Desconhecido')
    })
  })

  describe('isBackendStatus', () => {
    it('should validate backend statuses correctly', () => {
      expect(isBackendStatus('active')).toBe(true)
      expect(isBackendStatus('expired')).toBe(true)
      expect(isBackendStatus('used')).toBe(true)
      expect(isBackendStatus('cancelled')).toBe(true)
    })

    it('should handle case sensitivity', () => {
      expect(isBackendStatus('ACTIVE')).toBe(true)
      expect(isBackendStatus('Used')).toBe(true)
    })

    it('should reject invalid values', () => {
      expect(isBackendStatus('invalid')).toBe(false)
      expect(isBackendStatus(123)).toBe(false)
      expect(isBackendStatus(null)).toBe(false)
      expect(isBackendStatus(undefined)).toBe(false)
    })
  })

  describe('isUIStatus', () => {
    it('should validate UI statuses correctly', () => {
      expect(isUIStatus('active')).toBe(true)
      expect(isUIStatus('completed')).toBe(true)
      expect(isUIStatus('pending')).toBe(true)
    })

    it('should reject invalid values', () => {
      expect(isUIStatus('invalid')).toBe(false)
      expect(isUIStatus(123)).toBe(false)
      expect(isUIStatus(null)).toBe(false)
    })
  })

  describe('Integration scenarios', () => {
    it('should handle complete backend to UI workflow', () => {
      const backendStatuses = ['active', 'expired', 'used', 'cancelled']
      const expectedUIStatuses = ['active', 'expired', 'completed', 'expired']

      backendStatuses.forEach((backendStatus, index) => {
        const uiStatus = mapBackendStatus(backendStatus)
        expect(uiStatus).toBe(expectedUIStatuses[index])
        expect(isValidUIStatus(uiStatus)).toBe(true)

        const label = getStatusLabel(backendStatus)
        expect(typeof label).toBe('string')
        expect(label.length).toBeGreaterThan(0)
      })
    })

    it('should handle round-trip conversion', () => {
      const uiStatuses = ['active', 'expired', 'completed', 'pending']

      uiStatuses.forEach(uiStatus => {
        const backendStatus = mapUIToBackendStatus(uiStatus)
        const backToUI = mapBackendStatus(backendStatus)

        // Some mappings are not perfectly reversible due to business logic
        // (e.g., completed -> used -> completed, but pending -> active -> active)
        expect(typeof backToUI).toBe('string')
        expect(isValidUIStatus(backToUI)).toBe(true)
      })
    })
  })
})