/**
 * Phone Normalization Utilities
 * Unified phone formatting for Brazilian numbers
 */

/**
 * Remove caracteres não numéricos do telefone
 */
export function cleanPhone(phone: string): string {
  return phone.replace(/\D/g, '')
}

/**
 * Normaliza telefone brasileiro para formato internacional
 * Aceita: 11999999999, (11)99999-9999, +5511999999999, etc.
 * Retorna: +5511999999999
 */
export function normalizePhone(phone: string): string {
  const cleaned = cleanPhone(phone)

  // Se já começa com 55, adiciona apenas +
  if (cleaned.startsWith('55') && cleaned.length >= 12) {
    return `+${cleaned}`
  }

  // Se tem 10-11 dígitos (DDD + número), adiciona +55
  if (cleaned.length >= 10 && cleaned.length <= 11) {
    return `+55${cleaned}`
  }

  // Retorna como está se não reconhecido
  return phone
}

/**
 * Formata telefone para exibição: (XX) XXXXX-XXXX
 */
export function formatPhone(phone: string): string {
  const cleaned = cleanPhone(phone)

  // Remove código do país se presente
  const nationalNumber = cleaned.startsWith('55') ? cleaned.slice(2) : cleaned

  if (nationalNumber.length === 11) {
    return nationalNumber.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3')
  }
  if (nationalNumber.length === 10) {
    return nationalNumber.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3')
  }

  return phone
}

/**
 * Valida se telefone brasileiro é válido
 */
export function isValidBrazilianPhone(phone: string): boolean {
  const cleaned = cleanPhone(phone)
  const nationalNumber = cleaned.startsWith('55') ? cleaned.slice(2) : cleaned

  // Telefone brasileiro: 10 ou 11 dígitos (DDD + número)
  return nationalNumber.length >= 10 && nationalNumber.length <= 11
}
