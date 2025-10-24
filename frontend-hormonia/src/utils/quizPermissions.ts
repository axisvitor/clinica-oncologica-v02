/**
 * Quiz permissions utility module
 * 
 * This module provides centralized permission checking for quiz operations
 * to ensure proper access control and security.
 */


export interface QuizPermissionsUser {
  id: string
  role: string
  permissions?: string[]
  is_active?: boolean
}

/**
 * Check if user can create quiz links
 * Only admin and doctor roles can create quiz links
 */
export function canCreateQuizLink(user: QuizPermissionsUser | null): boolean {
  if (!user || !user.is_active) {
    return false
  }

  // Allow admin and doctor roles
  const allowedRoles = ['admin', 'doctor']
  return allowedRoles.includes(user['role'].toLowerCase())
}

/**
 * Check if user can view quiz statistics
 * Role-based data filtering applies
 */
export function canViewQuizStats(user: QuizPermissionsUser | null): boolean {
  if (!user || !user.is_active) {
    return false
  }

  // Allow admin and doctor roles
  const allowedRoles = ['admin', 'doctor']
  return allowedRoles.includes(user['role'].toLowerCase())
}

/**
 * Check if user can resend quiz links
 * Only admin and doctor roles can resend links
 */
export function canResendLink(user: QuizPermissionsUser | null): boolean {
  if (!user || !user.is_active) {
    return false
  }

  // Allow admin and doctor roles
  const allowedRoles = ['admin', 'doctor']
  return allowedRoles.includes(user['role'].toLowerCase())
}

/**
 * Check if user can cancel quiz links
 * Only admin and doctor roles can cancel links
 */
export function canCancelQuizLink(user: QuizPermissionsUser | null): boolean {
  if (!user || !user.is_active) {
    return false
  }

  // Allow admin and doctor roles
  const allowedRoles = ['admin', 'doctor']
  return allowedRoles.includes(user['role'].toLowerCase())
}

/**
 * Check if user can view specific quiz data
 * Admins can view all data, doctors can view their patients' data
 */
export function canViewPatientQuizData(
  user: QuizPermissionsUser | null, 
  patientDoctorId?: string
): boolean {
  if (!user || !user.is_active) {
    return false
  }

  // Admin can view all patient data
  if (user['role'].toLowerCase() === 'admin') {
    return true
  }

  // Doctor can only view their own patients' data
  if (user['role'].toLowerCase() === 'doctor') {
    return !patientDoctorId || patientDoctorId === user['id']
  }

  return false
}

/**
 * Check if user can manage quiz templates
 * Only admin role can manage templates
 */
export function canManageQuizTemplates(user: QuizPermissionsUser | null): boolean {
  if (!user || !user.is_active) {
    return false
  }

  return user['role'].toLowerCase() === 'admin'
}

/**
 * Check if user can perform bulk operations
 * Only admin role can perform bulk operations
 */
export function canPerformBulkOperations(user: QuizPermissionsUser | null): boolean {
  if (!user || !user.is_active) {
    return false
  }

  return user['role'].toLowerCase() === 'admin'
}

/**
 * Get filtered quiz stats based on user permissions
 * Returns data scope based on user role
 */
export function getQuizStatsScope(user: QuizPermissionsUser | null): 'all' | 'own_patients' | 'none' {
  if (!user || !user.is_active) {
    return 'none'
  }

  if (user['role'].toLowerCase() === 'admin') {
    return 'all'
  }

  if (user['role'].toLowerCase() === 'doctor') {
    return 'own_patients'
  }

  return 'none'
}

/**
 * Generate permission error message for UI feedback
 */
export function getPermissionErrorMessage(action: string, userRole?: string): string {
  const roleText = userRole ? ` (Perfil atual: ${userRole})` : ''
  
  switch (action) {
    case 'create_quiz_link':
      return `Apenas administradores e médicos podem criar links de questionário${roleText}`
    case 'view_quiz_stats':
      return `Apenas administradores e médicos podem visualizar estatísticas${roleText}`
    case 'resend_link':
      return `Apenas administradores e médicos podem reenviar links${roleText}`
    case 'cancel_link':
      return `Apenas administradores e médicos podem cancelar links${roleText}`
    case 'manage_templates':
      return `Apenas administradores podem gerenciar templates${roleText}`
    case 'bulk_operations':
      return `Apenas administradores podem realizar operações em lote${roleText}`
    default:
      return `Você não tem permissão para realizar esta ação${roleText}`
  }
}

/**
 * Comprehensive permission checker for quiz operations
 */
export const quizPermissions = {
  canCreateQuizLink,
  canViewQuizStats,
  canResendLink,
  canCancelQuizLink,
  canViewPatientQuizData,
  canManageQuizTemplates,
  canPerformBulkOperations,
  getQuizStatsScope,
  getPermissionErrorMessage
}

export default quizPermissions
