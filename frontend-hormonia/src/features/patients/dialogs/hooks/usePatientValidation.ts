/**
 * Patient Validation Hook
 * Custom validation logic for patient forms
 */

import { useState, useCallback } from 'react'
import { validateCPF } from '@/lib/utils/cpf'
import { isValidBrazilianPhone } from '@/lib/utils/phone'

interface ValidationErrors {
  cpf?: string
  phone?: string
  email?: string
}

interface UsePatientValidationReturn {
  errors: ValidationErrors
  validateCPFField: (cpf: string) => boolean
  validatePhoneField: (phone: string) => boolean
  validateEmailField: (email: string) => boolean
  clearErrors: () => void
}

/**
 * Hook para validações customizadas de campos de paciente
 */
export function usePatientValidation(): UsePatientValidationReturn {
  const [errors, setErrors] = useState<ValidationErrors>({})

  const validateCPFField = useCallback((cpf: string): boolean => {
    if (!cpf) {
      setErrors(prev => ({ ...prev, cpf: undefined }))
      return true
    }

    const isValid = validateCPF(cpf)
    setErrors(prev => ({
      ...prev,
      cpf: isValid ? undefined : 'CPF inválido'
    }))
    return isValid
  }, [])

  const validatePhoneField = useCallback((phone: string): boolean => {
    if (!phone) {
      setErrors(prev => ({ ...prev, phone: undefined }))
      return true
    }

    const isValid = isValidBrazilianPhone(phone)
    setErrors(prev => ({
      ...prev,
      phone: isValid ? undefined : 'Telefone inválido'
    }))
    return isValid
  }, [])

  const validateEmailField = useCallback((email: string): boolean => {
    if (!email) {
      setErrors(prev => ({ ...prev, email: undefined }))
      return true
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    const isValid = emailRegex.test(email)
    setErrors(prev => ({
      ...prev,
      email: isValid ? undefined : 'Email inválido'
    }))
    return isValid
  }, [])

  const clearErrors = useCallback(() => {
    setErrors({})
  }, [])

  return {
    errors,
    validateCPFField,
    validatePhoneField,
    validateEmailField,
    clearErrors
  }
}
