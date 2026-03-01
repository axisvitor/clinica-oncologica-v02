const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PASSWORD_COMPLEXITY_REGEX = /(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/

export type ValidationErrors = Record<string, string>

export function validateEmailField(
  email: string | undefined,
  errors: ValidationErrors,
  field: string = 'email'
) {
  const value = email?.trim() ?? ''
  if (!value) {
    errors[field] = 'Email é obrigatório'
    return
  }

  if (!EMAIL_REGEX.test(value)) {
    errors[field] = 'Email inválido'
  }
}

export function validateFullNameField(
  fullName: string | undefined,
  errors: ValidationErrors,
  field: string = 'full_name'
) {
  const value = fullName?.trim() ?? ''
  if (!value) {
    errors[field] = 'Nome completo é obrigatório'
    return
  }

  if (value.length < 2) {
    errors[field] = 'Nome deve ter pelo menos 2 caracteres'
  }
}

export function validatePasswordPolicy(
  password: string,
  errors: ValidationErrors,
  field: string = 'password'
) {
  if (password.length < 8) {
    errors[field] = 'Senha deve ter pelo menos 8 caracteres'
    return
  }

  if (!PASSWORD_COMPLEXITY_REGEX.test(password)) {
    errors[field] = 'Senha deve conter pelo menos uma letra minúscula, uma maiúscula e um número'
  }
}

export function validatePasswordConfirmation(
  password: string | undefined,
  confirmation: string | undefined,
  errors: ValidationErrors,
  field: string = 'confirm_password'
) {
  if (password !== confirmation) {
    errors[field] = 'Senhas não coincidem'
  }
}
