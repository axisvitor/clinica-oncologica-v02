/**
 * Environment Variable Validation Utilities
 *
 * This module provides comprehensive validation for environment variables
 * to ensure proper configuration and security compliance.
 *
 * Features:
 * - Required environment variable validation
 * - Type checking and format validation
 * - Security compliance checks
 * - Development vs production configuration validation
 * - Detailed error reporting
 */

import { RuntimeConfig } from './runtime-config'
import { createLogger } from './logger'

const logger = createLogger('EnvValidator')

export interface ValidationRule<T = string> {
  required: boolean
  type?: 'string' | 'number' | 'boolean' | 'url' | 'email'
  format?: RegExp
  minLength?: number
  maxLength?: number
  allowedValues?: T[]
  validator?: (value: T) => boolean | string
  description: string
  security?: {
    sensitive: boolean
    shouldNotBeHardcoded?: boolean
  }
}

export interface ValidationResult {
  isValid: boolean
  errors: ValidationError[]
  warnings: ValidationWarning[]
  summary: {
    total: number
    validated: number
    errors: number
    warnings: number
    missing: number
  }
}

export interface ValidationError {
  field: string
  message: string
  severity: 'error' | 'critical'
  suggestion?: string
}

export interface ValidationWarning {
  field: string
  message: string
  suggestion?: string
}

// Environment variable validation rules
const ENV_VALIDATION_RULES: Record<keyof RuntimeConfig, ValidationRule> = {
  // Supabase Configuration (Critical)
  VITE_SUPABASE_URL: {
    required: true,
    type: 'url',
    format: /^https:\/\/[a-zA-Z0-9-]+\.supabase\.co$/,
    description: 'Supabase project URL',
    security: {
      sensitive: false,
      shouldNotBeHardcoded: true
    }
  },

  VITE_SUPABASE_ANON_KEY: {
    required: true,
    type: 'string',
    format: /^eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*$/,
    minLength: 100,
    description: 'Supabase anonymous public key (JWT token)',
    security: {
      sensitive: true,
      shouldNotBeHardcoded: true
    }
  },

  VITE_SUPABASE_REALTIME_ENABLED: {
    required: false,
    type: 'boolean',
    allowedValues: ['true', 'false'],
    description: 'Enable Supabase real-time features'
  },

  // API Configuration (Critical)
  VITE_API_URL: {
    required: true,
    type: 'url',
    format: /^https?:\/\/.+/,
    description: 'Backend API URL',
    validator: (value) => {
      if (value.includes('localhost') || value.includes('127.0.0.1')) {
        return 'Development URL detected'
      }
      return true
    }
  },

  VITE_WS_URL: {
    required: false,
    type: 'string',
    format: /^wss?:\/\//,
    description: 'WebSocket server URL'
  },

  // Application Configuration
  VITE_WHATSAPP_INSTANCE_NAME: {
    required: false,
    type: 'string',
    minLength: 3,
    maxLength: 50,
    description: 'WhatsApp integration instance name'
  },

  // AI Service Configuration (Sensitive)
  VITE_OPENAI_API_KEY: {
    required: false,
    type: 'string',
    format: /^sk-[a-zA-Z0-9]+$/,
    minLength: 20,
    description: 'OpenAI API key',
    security: {
      sensitive: true,
      shouldNotBeHardcoded: true
    }
  },

  VITE_LANGCHAIN_API_KEY: {
    required: false,
    type: 'string',
    description: 'LangChain API key',
    security: {
      sensitive: true,
      shouldNotBeHardcoded: true
    }
  },

  VITE_GEMINI_API_KEY: {
    required: false,
    type: 'string',
    description: 'Google Gemini API key',
    security: {
      sensitive: true,
      shouldNotBeHardcoded: true
    }
  },

  // Feature Flags
  VITE_AI_CHAT_ENABLED: {
    required: false,
    type: 'boolean',
    allowedValues: ['true', 'false'],
    description: 'Enable AI chat features'
  },

  VITE_AI_ANALYTICS_ENABLED: {
    required: false,
    type: 'boolean',
    allowedValues: ['true', 'false'],
    description: 'Enable AI analytics features'
  },

  VITE_AI_INSIGHTS_ENABLED: {
    required: false,
    type: 'boolean',
    allowedValues: ['true', 'false'],
    description: 'Enable AI insights features'
  },

  VITE_AI_RECOMMENDATIONS_ENABLED: {
    required: false,
    type: 'boolean',
    allowedValues: ['true', 'false'],
    description: 'Enable AI recommendations features'
  },

  // Monitoring & Analytics
  VITE_SENTRY_DSN: {
    required: false,
    type: 'url',
    format: /^https:\/\/[a-f0-9]+@[a-z0-9]+\.ingest\.sentry\.io\/[0-9]+$/,
    description: 'Sentry error tracking DSN',
    security: {
      sensitive: true
    }
  },

  VITE_ANALYTICS_TRACKING_ID: {
    required: false,
    type: 'string',
    description: 'Analytics tracking ID'
  },

  // Environment Settings
  VITE_ENVIRONMENT: {
    required: false,
    type: 'string',
    allowedValues: ['development', 'staging', 'production'],
    description: 'Application environment'
  },

  VITE_DEBUG_MODE: {
    required: false,
    type: 'boolean',
    allowedValues: ['true', 'false'],
    description: 'Enable debug mode'
  },

  VITE_SESSION_TIMEOUT: {
    required: false,
    type: 'number',
    validator: (value) => {
      const num = parseInt(value)
      return num > 0 && num <= 86400000 // Max 24 hours
    },
    description: 'Session timeout in milliseconds'
  },

  VITE_TOKEN_REFRESH_THRESHOLD: {
    required: false,
    type: 'number',
    validator: (value) => {
      const num = parseInt(value)
      return num > 0 && num <= 3600000 // Max 1 hour
    },
    description: 'Token refresh threshold in milliseconds'
  },

  VITE_MAX_FILE_SIZE: {
    required: false,
    type: 'number',
    validator: (value) => {
      const num = parseInt(value)
      return num > 0 && num <= 104857600 // Max 100MB
    },
    description: 'Maximum file upload size in bytes'
  },

  VITE_SUPPORTED_FILE_TYPES: {
    required: false,
    type: 'string',
    description: 'Comma-separated list of supported file MIME types'
  },

  // Evolution and Demo Configuration
  VITE_ENABLE_EVOLUTION: {
    required: false,
    type: 'boolean',
    allowedValues: ['true', 'false'],
    description: 'Enable evolution features'
  },

  VITE_EVOLUTION_API_URL: {
    required: false,
    type: 'url',
    description: 'Evolution API URL'
  },

  VITE_SHOW_DEMO_CREDENTIALS: {
    required: false,
    type: 'boolean',
    allowedValues: ['true', 'false'],
    description: 'Show demo credentials in UI'
  }
}

/**
 * Validates a single environment variable
 */
function validateField(key: string, value: any, rule: ValidationRule): {
  errors: ValidationError[]
  warnings: ValidationWarning[]
} {
  const errors: ValidationError[] = []
  const warnings: ValidationWarning[] = []

  // Check if required field is missing
  if (rule.required && (!value || value.trim() === '')) {
    errors.push({
      field: key,
      message: `Required environment variable is missing`,
      severity: 'critical',
      suggestion: `Set ${key} in your .env file. ${rule.description}`
    })
    return { errors, warnings }
  }

  // Skip further validation if field is optional and empty
  if (!value || value.trim() === '') {
    return { errors, warnings }
  }

  // Type validation
  if (rule.type) {
    switch (rule.type) {
      case 'number':
        if (isNaN(Number(value))) {
          errors.push({
            field: key,
            message: `Must be a valid number`,
            severity: 'error',
            suggestion: `Provide a numeric value for ${key}`
          })
        }
        break

      case 'boolean':
        if (!['true', 'false'].includes(value.toLowerCase())) {
          errors.push({
            field: key,
            message: `Must be 'true' or 'false'`,
            severity: 'error',
            suggestion: `Set ${key} to either 'true' or 'false'`
          })
        }
        break

      case 'url':
        try {
          const url = new URL(value)
          if (!['http:', 'https:', 'ws:', 'wss:'].includes(url.protocol)) {
            errors.push({
              field: key,
              message: `Must be a valid HTTP/HTTPS/WS/WSS URL`,
              severity: 'error'
            })
          }
        } catch {
          errors.push({
            field: key,
            message: `Must be a valid URL`,
            severity: 'error',
            suggestion: `Provide a valid URL for ${key} (e.g., https://example.com)`
          })
        }
        break

      case 'email':
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        if (!emailRegex.test(value)) {
          errors.push({
            field: key,
            message: `Must be a valid email address`,
            severity: 'error'
          })
        }
        break
    }
  }

  // Format validation
  if (rule.format && !rule.format.test(value)) {
    errors.push({
      field: key,
      message: `Does not match required format`,
      severity: 'error',
      suggestion: `Check the format requirements for ${key}`
    })
  }

  // Length validation
  if (rule.minLength && value.length < rule.minLength) {
    errors.push({
      field: key,
      message: `Must be at least ${rule.minLength} characters long`,
      severity: 'error'
    })
  }

  if (rule.maxLength && value.length > rule.maxLength) {
    errors.push({
      field: key,
      message: `Must not exceed ${rule.maxLength} characters`,
      severity: 'error'
    })
  }

  // Allowed values validation
  if (rule.allowedValues && !rule.allowedValues.includes(value)) {
    errors.push({
      field: key,
      message: `Must be one of: ${rule.allowedValues.join(', ')}`,
      severity: 'error'
    })
  }

  // Custom validation
  if (rule.validator) {
    const result = rule.validator(value)
    if (result !== true) {
      if (typeof result === 'string') {
        warnings.push({
          field: key,
          message: result,
          suggestion: `Review the configuration for ${key}`
        })
      } else {
        errors.push({
          field: key,
          message: `Custom validation failed`,
          severity: 'error'
        })
      }
    }
  }

  // Security checks
  if (rule.security?.shouldNotBeHardcoded) {
    // Check if this appears to be a hardcoded value (very basic check)
    if (value.length > 20 && !value.includes('$') && !value.includes('{')) {
      warnings.push({
        field: key,
        message: `Appears to be hardcoded. Consider using environment variables.`,
        suggestion: `Move this value to a secure environment variable`
      })
    }
  }

  return { errors, warnings }
}

/**
 * Validates the entire runtime configuration
 */
export function validateRuntimeConfig(config: Partial<RuntimeConfig>): ValidationResult {
  const errors: ValidationError[] = []
  const warnings: ValidationWarning[] = []
  let validated = 0

  // Validate each field
  Object.entries(ENV_VALIDATION_RULES).forEach(([key, rule]) => {
    const value = config[key as keyof RuntimeConfig]
    const { errors: fieldErrors, warnings: fieldWarnings } = validateField(key, value, rule)

    errors.push(...fieldErrors)
    warnings.push(...fieldWarnings)

    if (value !== undefined && value !== null && value !== '') {
      validated++
    }
  })

  // Environment-specific validations
  const environment = config.VITE_ENVIRONMENT || 'development'

  if (environment === 'production') {
    // Production-specific checks
    if (config.VITE_DEBUG_MODE === 'true') {
      warnings.push({
        field: 'VITE_DEBUG_MODE',
        message: 'Debug mode is enabled in production',
        suggestion: 'Set VITE_DEBUG_MODE=false for production'
      })
    }

    if (config.VITE_API_URL?.includes('localhost')) {
      errors.push({
        field: 'VITE_API_URL',
        message: 'Using localhost URL in production',
        severity: 'critical',
        suggestion: 'Use production API URL'
      })
    }
  }

  // Check for common configuration issues
  if (!config.VITE_SUPABASE_URL && !config.VITE_API_URL) {
    errors.push({
      field: 'configuration',
      message: 'No backend configuration found',
      severity: 'critical',
      suggestion: 'Configure either Supabase or custom API backend'
    })
  }

  const summary = {
    total: Object.keys(ENV_VALIDATION_RULES).length,
    validated,
    errors: errors.length,
    warnings: warnings.length,
    missing: Object.keys(ENV_VALIDATION_RULES).filter(key => {
      const rule = ENV_VALIDATION_RULES[key as keyof RuntimeConfig]
      const value = config[key as keyof RuntimeConfig]
      return rule.required && (!value || value.trim() === '')
    }).length
  }

  return {
    isValid: errors.length === 0,
    errors,
    warnings,
    summary
  }
}

/**
 * Validates environment variables and logs results
 */
export function validateAndLogConfig(config: Partial<RuntimeConfig>): boolean {
  const result = validateRuntimeConfig(config)

  if (result.errors.length > 0) {
    logger.group('❌ Environment Configuration Errors')
    result.errors.forEach(error => {
      logger.error(`${error.field}: ${error.message}`)
      if (error.suggestion) {
        logger.info(`💡 Suggestion: ${error.suggestion}`)
      }
    })
    logger.groupEnd()
  }

  if (result.warnings.length > 0) {
    logger.group('⚠️ Environment Configuration Warnings')
    result.warnings.forEach(warning => {
      logger.warn(`${warning.field}: ${warning.message}`)
      if (warning.suggestion) {
        logger.info(`💡 Suggestion: ${warning.suggestion}`)
      }
    })
    logger.groupEnd()
  }

  if (result.isValid && result.warnings.length === 0) {
    logger.log('✅ Environment configuration is valid')
  }

  logger.log(`📊 Configuration Summary:`, result.summary)

  return result.isValid
}

/**
 * Gets validation rules for a specific field
 */
export function getValidationRule(field: keyof RuntimeConfig): ValidationRule | undefined {
  return ENV_VALIDATION_RULES[field]
}

/**
 * Gets all required environment variables
 */
export function getRequiredEnvVars(): string[] {
  return Object.entries(ENV_VALIDATION_RULES)
    .filter(([_, rule]) => rule.required)
    .map(([key, _]) => key)
}

/**
 * Gets all sensitive environment variables
 */
export function getSensitiveEnvVars(): string[] {
  return Object.entries(ENV_VALIDATION_RULES)
    .filter(([_, rule]) => rule.security?.sensitive)
    .map(([key, _]) => key)
}

/**
 * Masks sensitive values for logging
 */
export function maskSensitiveConfig(config: Partial<RuntimeConfig>): Partial<RuntimeConfig> {
  const masked = { ...config }
  const sensitiveFields = getSensitiveEnvVars()

  sensitiveFields.forEach(field => {
    const value = masked[field as keyof RuntimeConfig]
    if (value && typeof value === 'string') {
      masked[field as keyof RuntimeConfig] = value.length > 8
        ? `${value.substring(0, 4)}...${value.substring(value.length - 4)}`
        : '***'
    }
  })

  return masked
}