/**
 * CPF Validation Utilities
 * Implements Brazilian CPF checksum validation algorithm
 */

/**
 * Remove caracteres não numéricos do CPF
 */
export function cleanCPF(cpf: string): string {
  return cpf.replace(/\D/g, '');
}

/**
 * Formata CPF para exibição (XXX.XXX.XXX-XX)
 */
export function formatCPF(cpf: string): string {
  const cleaned = cleanCPF(cpf);
  if (cleaned.length !== 11) return cpf;
  return cleaned.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
}

/**
 * Valida CPF com algoritmo de dígito verificador
 * @returns true se CPF é válido, false caso contrário
 */
export function validateCPF(cpf: string | undefined): boolean {
  if (!cpf) return false;

  const cleaned = cleanCPF(cpf);

  // Deve ter 11 dígitos
  if (cleaned.length !== 11) return false;

  // Rejeitar CPFs conhecidos como inválidos (todos dígitos iguais)
  if (/^(\d)\1+$/.test(cleaned)) return false;

  // Validar primeiro dígito verificador
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    const digit = cleaned.charAt(i);
    if (!digit) return false;
    sum += parseInt(digit) * (10 - i);
  }
  let remainder = (sum * 10) % 11;
  if (remainder === 10) remainder = 0;
  const firstCheckDigit = cleaned.charAt(9);
  if (!firstCheckDigit || remainder !== parseInt(firstCheckDigit)) return false;

  // Validar segundo dígito verificador
  sum = 0;
  for (let i = 0; i < 10; i++) {
    const digit = cleaned.charAt(i);
    if (!digit) return false;
    sum += parseInt(digit) * (11 - i);
  }
  remainder = (sum * 10) % 11;
  if (remainder === 10) remainder = 0;
  const secondCheckDigit = cleaned.charAt(10);
  if (!secondCheckDigit || remainder !== parseInt(secondCheckDigit)) return false;

  return true;
}

/**
 * Zod refinement para validação de CPF
 */
export function cpfRefinement(cpf: string | undefined): boolean {
  if (!cpf) return true; // CPF é opcional
  return validateCPF(cpf);
}
