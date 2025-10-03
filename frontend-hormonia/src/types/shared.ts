/**
 * Shared types and constants for user roles and permissions
 */

export enum UserRole {
  SUPER_ADMIN = 'super_admin',
  ADMIN = 'admin',
  DOCTOR = 'doctor',
  NURSE = 'nurse',
  PATIENT = 'patient',
  RESEARCHER = 'researcher',
  COORDINATOR = 'coordinator',
}

export const ROLE_LABELS: Record<UserRole, string> = {
  [UserRole.SUPER_ADMIN]: 'Super Administrador',
  [UserRole.ADMIN]: 'Administrador',
  [UserRole.DOCTOR]: 'Médico',
  [UserRole.NURSE]: 'Enfermeiro(a)',
  [UserRole.PATIENT]: 'Paciente',
  [UserRole.RESEARCHER]: 'Pesquisador(a)',
  [UserRole.COORDINATOR]: 'Coordenador(a)',
}

export const ROLE_COLORS: Record<UserRole, string> = {
  [UserRole.SUPER_ADMIN]: 'bg-purple-500 text-white',
  [UserRole.ADMIN]: 'bg-purple-100 text-purple-800',
  [UserRole.DOCTOR]: 'bg-green-100 text-green-800',
  [UserRole.NURSE]: 'bg-blue-100 text-blue-800',
  [UserRole.PATIENT]: 'bg-gray-100 text-gray-800',
  [UserRole.RESEARCHER]: 'bg-yellow-100 text-yellow-800',
  [UserRole.COORDINATOR]: 'bg-orange-100 text-orange-800',
}

/**
 * Get display label for a role
 */
export function getRoleLabel(role: string): string {
  const roleKey = role.toUpperCase() as keyof typeof UserRole
  const roleValue = UserRole[roleKey]
  return ROLE_LABELS[roleValue] || role
}

/**
 * Get color classes for a role badge
 */
export function getRoleColor(role: string): string {
  const roleKey = role.toUpperCase() as keyof typeof UserRole
  const roleValue = UserRole[roleKey]
  return ROLE_COLORS[roleValue] || 'bg-gray-100 text-gray-800'
}

/**
 * Check if a role string is valid
 */
export function isValidRole(role: string): boolean {
  return Object.values(UserRole).includes(role as UserRole)
}