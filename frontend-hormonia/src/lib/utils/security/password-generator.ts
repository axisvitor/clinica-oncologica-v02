/**
 * Secure Password Generator Utility
 *
 * SECURITY: Isolated password generation logic using Web Crypto API
 * - Cryptographically secure random number generation
 * - Configurable complexity requirements
 * - Excludes ambiguous characters for better usability
 */

export interface PasswordOptions {
  /** Password length (minimum 8, recommended 12+) */
  length?: number
  /** Include uppercase letters (A-Z) */
  includeUppercase?: boolean
  /** Include lowercase letters (a-z) */
  includeLowercase?: boolean
  /** Include numbers (0-9) */
  includeNumbers?: boolean
  /** Include special characters */
  includeSpecial?: boolean
  /** Exclude ambiguous characters (0, O, I, l, etc.) */
  excludeAmbiguous?: boolean
}

/**
 * Character sets for password generation
 */
const CHAR_SETS = {
  uppercase: 'ABCDEFGHJKLMNPQRSTUVWXYZ', // Excludes I, O
  lowercase: 'abcdefghjkmnpqrstuvwxyz', // Excludes i, l, o
  numbers: '23456789', // Excludes 0, 1
  special: '!@#$%^&*',
  uppercaseAll: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  lowercaseAll: 'abcdefghijklmnopqrstuvwxyz',
  numbersAll: '0123456789',
}

/**
 * Generate a cryptographically secure temporary password
 *
 * @param options - Password generation options
 * @returns Secure random password
 *
 * @example
 * ```ts
 * // Default: 12 chars, all types, no ambiguous
 * const pwd = generateSecurePassword()
 *
 * // Custom: 16 chars with all characters
 * const pwd = generateSecurePassword({
 *   length: 16,
 *   excludeAmbiguous: false
 * })
 * ```
 */
export function generateSecurePassword(options: PasswordOptions = {}): string {
  const {
    length = 12,
    includeUppercase = true,
    includeLowercase = true,
    includeNumbers = true,
    includeSpecial = true,
    excludeAmbiguous = true,
  } = options

  // Validation
  if (length < 8) {
    throw new Error('Password length must be at least 8 characters')
  }

  // Build character set based on options
  let charset = ''
  const requiredChars: string[] = []

  if (includeUppercase) {
    const upperSet = excludeAmbiguous ? CHAR_SETS.uppercase : CHAR_SETS.uppercaseAll
    charset += upperSet
    requiredChars.push(getRandomChar(upperSet))
  }

  if (includeLowercase) {
    const lowerSet = excludeAmbiguous ? CHAR_SETS.lowercase : CHAR_SETS.lowercaseAll
    charset += lowerSet
    requiredChars.push(getRandomChar(lowerSet))
  }

  if (includeNumbers) {
    const numberSet = excludeAmbiguous ? CHAR_SETS.numbers : CHAR_SETS.numbersAll
    charset += numberSet
    requiredChars.push(getRandomChar(numberSet))
  }

  if (includeSpecial) {
    charset += CHAR_SETS.special
    requiredChars.push(getRandomChar(CHAR_SETS.special))
  }

  if (charset.length === 0) {
    throw new Error('At least one character type must be enabled')
  }

  // Calculate remaining length after required characters
  const remainingLength = length - requiredChars.length

  // Generate remaining random characters
  const remainingChars = Array.from(
    crypto.getRandomValues(new Uint8Array(remainingLength)),
    (byte) => charset[byte % charset.length]
  )

  // Combine required and remaining characters
  const allChars = [...requiredChars, ...remainingChars]

  // Shuffle array using Fisher-Yates algorithm with crypto random
  for (let i = allChars.length - 1; i > 0; i--) {
    const randomBytes = new Uint32Array(1)
    crypto.getRandomValues(randomBytes)
    const j = randomBytes[0]! % (i + 1)
    const temp = allChars[i]!
    allChars[i] = allChars[j]!
    allChars[j] = temp
  }

  return allChars.join('')
}

/**
 * Get a random character from a character set
 * Uses Web Crypto API for cryptographic randomness
 */
function getRandomChar(charset: string): string {
  const randomBytes = new Uint8Array(1)
  crypto.getRandomValues(randomBytes)
  const index = randomBytes[0]! % charset.length
  return charset[index]!
}

/**
 * Generate a temporary password with default settings
 * Convenience wrapper for admin password resets
 *
 * @returns 12-character secure password
 */
export function generateTemporaryPassword(): string {
  return generateSecurePassword({
    length: 12,
    includeUppercase: true,
    includeLowercase: true,
    includeNumbers: true,
    includeSpecial: true,
    excludeAmbiguous: true,
  })
}

/**
 * Validate password strength
 *
 * @param password - Password to validate
 * @returns Strength score (0-4) and feedback
 */
export function validatePasswordStrength(password: string): {
  score: number
  feedback: string[]
  isStrong: boolean
} {
  const feedback: string[] = []
  let score = 0

  // Length check
  if (password.length >= 12) score++
  else if (password.length >= 8) score += 0.5
  else feedback.push('Senha muito curta (mínimo 8 caracteres)')

  // Character variety checks
  if (/[A-Z]/.test(password)) score++
  else feedback.push('Adicione letras maiúsculas')

  if (/[a-z]/.test(password)) score++
  else feedback.push('Adicione letras minúsculas')

  if (/[0-9]/.test(password)) score++
  else feedback.push('Adicione números')

  if (/[!@#$%^&*]/.test(password)) score++
  else feedback.push('Adicione caracteres especiais')

  // Common pattern checks
  if (/(.)\1{2,}/.test(password)) {
    score -= 0.5
    feedback.push('Evite caracteres repetidos')
  }

  if (/^[a-zA-Z]+$/.test(password) || /^[0-9]+$/.test(password)) {
    score -= 1
    feedback.push('Use uma combinação de tipos de caracteres')
  }

  // Normalize score to 0-4 range
  score = Math.max(0, Math.min(4, score))

  return {
    score: Math.round(score),
    feedback,
    isStrong: score >= 3,
  }
}
