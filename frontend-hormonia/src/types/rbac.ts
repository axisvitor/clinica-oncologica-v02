/**
 * RBAC (Role-Based Access Control) Types
 *
 * Complete TypeScript types matching backend-hormonia/app/core/permissions.py
 * This file provides type-safe RBAC functionality for the frontend admin system.
 */

// ============================================================================
// USER ROLES - Matches backend UserRole enum
// ============================================================================

/**
 * User roles in the system (ONLY admin and doctor exist)
 * Backend: app/models/user.py UserRole enum
 */
export enum UserRole {
  ADMIN = 'admin',
  DOCTOR = 'doctor'
}

/**
 * Authentication provider types
 * Backend: app/models/user.py AuthProvider enum
 */
export enum AuthProvider {
  LOCAL = 'local',
  FIREBASE = 'firebase'
}

// ============================================================================
// PERMISSIONS - Matches backend Permission enum
// ============================================================================

/**
 * Complete permission enumeration matching backend
 * Backend: app/core/permissions.py Permission enum
 */
export enum Permission {
  // User Management
  USER_CREATE = 'user:create',
  USER_READ = 'user:read',
  USER_UPDATE = 'user:update',
  USER_DELETE = 'user:delete',
  USER_LIST = 'user:list',
  USER_IMPERSONATE = 'user:impersonate',

  // Patient Management
  PATIENT_CREATE = 'patient:create',
  PATIENT_READ = 'patient:read',
  PATIENT_UPDATE = 'patient:update',
  PATIENT_DELETE = 'patient:delete',
  PATIENT_LIST = 'patient:list',
  PATIENT_MEDICAL_RECORDS = 'patient:medical_records',
  PATIENT_SENSITIVE_DATA = 'patient:sensitive_data',

  // Quiz and Assessments
  QUIZ_CREATE = 'quiz:create',
  QUIZ_READ = 'quiz:read',
  QUIZ_UPDATE = 'quiz:update',
  QUIZ_DELETE = 'quiz:delete',
  QUIZ_PUBLISH = 'quiz:publish',
  QUIZ_RESULTS_VIEW = 'quiz:results_view',
  QUIZ_ANALYTICS = 'quiz:analytics',

  // Reports and Analytics
  REPORT_CREATE = 'report:create',
  REPORT_READ = 'report:read',
  REPORT_UPDATE = 'report:update',
  REPORT_DELETE = 'report:delete',
  REPORT_EXPORT = 'report:export',
  ANALYTICS_VIEW = 'analytics:view',
  ANALYTICS_ADVANCED = 'analytics:advanced',

  // System Administration
  ADMIN_PANEL = 'admin:panel',
  ADMIN_SETTINGS = 'admin:settings',
  ADMIN_LOGS = 'admin:logs',
  ADMIN_BACKUP = 'admin:backup',
  ADMIN_RESTORE = 'admin:restore',
  ADMIN_MAINTENANCE = 'admin:maintenance',

  // AI and Flows
  AI_ACCESS = 'ai:access',
  AI_CONFIGURE = 'ai:configure',
  FLOW_CREATE = 'flow:create',
  FLOW_EXECUTE = 'flow:execute',
  FLOW_MANAGE = 'flow:manage',

  // Templates and Content
  TEMPLATE_CREATE = 'template:create',
  TEMPLATE_READ = 'template:read',
  TEMPLATE_UPDATE = 'template:update',
  TEMPLATE_DELETE = 'template:delete',
  TEMPLATE_PUBLISH = 'template:publish',

  // Messaging and Notifications
  MESSAGE_SEND = 'message:send',
  MESSAGE_BROADCAST = 'message:broadcast',
  NOTIFICATION_MANAGE = 'notification:manage',

  // API and Integration
  API_ACCESS = 'api:access',
  API_RATE_LIMIT_BYPASS = 'api:rate_limit_bypass',
  WEBHOOK_MANAGE = 'webhook:manage',
  INTEGRATION_MANAGE = 'integration:manage'
}

/**
 * Security levels for permission validation
 * Backend: app/core/permissions.py SecurityLevel enum
 */
export enum SecurityLevel {
  PUBLIC = 'public',
  AUTHENTICATED = 'authenticated',
  VERIFIED = 'verified',
  PRIVILEGED = 'privileged',
  RESTRICTED = 'restricted'
}

// ============================================================================
// ROLE DEFINITIONS
// ============================================================================

/**
 * Role definition with permissions and security constraints
 * Backend: app/core/permissions.py RoleDefinition class
 */
export interface RoleDefinition {
  name: string
  permissions: Permission[]
  security_level: SecurityLevel
  description: string
  is_default: boolean
  requires_verification: boolean
  max_auto_grant_duration_ms?: number // milliseconds (backend uses timedelta)
  allowed_domains?: string[]
  restricted_domains?: string[]
}

/**
 * Complete role definitions matching backend ROLE_DEFINITIONS
 * Backend: app/core/permissions.py ROLE_DEFINITIONS
 */
export const ROLE_DEFINITIONS: Record<UserRole, RoleDefinition> = {
  [UserRole.ADMIN]: {
    name: 'Administrator',
    permissions: [
      Permission.USER_CREATE,
      Permission.USER_READ,
      Permission.USER_UPDATE,
      Permission.USER_LIST,
      Permission.PATIENT_CREATE,
      Permission.PATIENT_READ,
      Permission.PATIENT_UPDATE,
      Permission.PATIENT_DELETE,
      Permission.PATIENT_LIST,
      Permission.PATIENT_MEDICAL_RECORDS,
      Permission.QUIZ_CREATE,
      Permission.QUIZ_READ,
      Permission.QUIZ_UPDATE,
      Permission.QUIZ_DELETE,
      Permission.QUIZ_PUBLISH,
      Permission.QUIZ_RESULTS_VIEW,
      Permission.QUIZ_ANALYTICS,
      Permission.REPORT_CREATE,
      Permission.REPORT_READ,
      Permission.REPORT_UPDATE,
      Permission.REPORT_EXPORT,
      Permission.ANALYTICS_VIEW,
      Permission.ANALYTICS_ADVANCED,
      Permission.ADMIN_PANEL,
      Permission.ADMIN_SETTINGS,
      Permission.ADMIN_LOGS,
      Permission.AI_ACCESS,
      Permission.AI_CONFIGURE,
      Permission.FLOW_CREATE,
      Permission.FLOW_EXECUTE,
      Permission.FLOW_MANAGE,
      Permission.TEMPLATE_CREATE,
      Permission.TEMPLATE_READ,
      Permission.TEMPLATE_UPDATE,
      Permission.TEMPLATE_DELETE,
      Permission.TEMPLATE_PUBLISH,
      Permission.MESSAGE_SEND,
      Permission.MESSAGE_BROADCAST,
      Permission.NOTIFICATION_MANAGE,
      Permission.API_ACCESS,
      Permission.WEBHOOK_MANAGE,
      Permission.INTEGRATION_MANAGE
    ],
    security_level: SecurityLevel.PRIVILEGED,
    description: 'Administrative access with management capabilities',
    is_default: false,
    requires_verification: true,
    max_auto_grant_duration_ms: 24 * 60 * 60 * 1000, // 24 hours
    allowed_domains: ['hormonia.io', 'admin.local', 'clinica.med.br']
  },
  [UserRole.DOCTOR]: {
    name: 'Doctor',
    permissions: [
      Permission.USER_READ,
      Permission.PATIENT_CREATE,
      Permission.PATIENT_READ,
      Permission.PATIENT_UPDATE,
      Permission.PATIENT_DELETE,
      Permission.PATIENT_LIST,
      Permission.PATIENT_MEDICAL_RECORDS,
      Permission.PATIENT_SENSITIVE_DATA,
      Permission.QUIZ_CREATE,
      Permission.QUIZ_READ,
      Permission.QUIZ_UPDATE,
      Permission.QUIZ_RESULTS_VIEW,
      Permission.QUIZ_ANALYTICS,
      Permission.REPORT_CREATE,
      Permission.REPORT_READ,
      Permission.REPORT_EXPORT,
      Permission.ANALYTICS_VIEW,
      Permission.AI_ACCESS,
      Permission.FLOW_EXECUTE,
      Permission.TEMPLATE_READ,
      Permission.TEMPLATE_CREATE,
      Permission.MESSAGE_SEND,
      Permission.API_ACCESS
    ],
    security_level: SecurityLevel.VERIFIED,
    description: 'Medical professional with patient care access',
    is_default: true,
    requires_verification: true,
    allowed_domains: ['med.br', 'saude.gov.br', 'crm.org.br', 'hospital.com.br']
  }
}

// ============================================================================
// PERMISSION CHECKING
// ============================================================================

/**
 * Permission resource types for access control
 */
export type PermissionResource = 'user' | 'patient' | 'quiz' | 'report' | 'analytics' | 'admin' | 'template' | 'flow' | 'message' | 'webhook'

/**
 * Permission actions for resource access
 */
export type PermissionAction = 'create' | 'read' | 'update' | 'delete' | 'list' | 'execute' | 'manage'

/**
 * Permission check request
 */
export interface PermissionCheckRequest {
  user_role: UserRole
  resource: PermissionResource
  action: PermissionAction
  resource_owner_role?: UserRole
}

/**
 * Permission check response
 */
export interface PermissionCheckResponse {
  allowed: boolean
  reason?: string
  required_permission?: Permission
}

/**
 * Resource-action to permission mapping
 */
export const PERMISSION_MAP: Record<string, Permission> = {
  'user:create': Permission.USER_CREATE,
  'user:read': Permission.USER_READ,
  'user:update': Permission.USER_UPDATE,
  'user:delete': Permission.USER_DELETE,
  'user:list': Permission.USER_LIST,
  'patient:create': Permission.PATIENT_CREATE,
  'patient:read': Permission.PATIENT_READ,
  'patient:update': Permission.PATIENT_UPDATE,
  'patient:delete': Permission.PATIENT_DELETE,
  'patient:list': Permission.PATIENT_LIST,
  'quiz:create': Permission.QUIZ_CREATE,
  'quiz:read': Permission.QUIZ_READ,
  'quiz:update': Permission.QUIZ_UPDATE,
  'quiz:delete': Permission.QUIZ_DELETE,
  'report:create': Permission.REPORT_CREATE,
  'report:read': Permission.REPORT_READ,
  'report:update': Permission.REPORT_UPDATE,
  'report:delete': Permission.REPORT_DELETE,
  'report:export': Permission.REPORT_EXPORT,
  'analytics:view': Permission.ANALYTICS_VIEW,
  'analytics:advanced': Permission.ANALYTICS_ADVANCED,
  'flow:create': Permission.FLOW_CREATE,
  'flow:execute': Permission.FLOW_EXECUTE,
  'flow:manage': Permission.FLOW_MANAGE,
  'template:create': Permission.TEMPLATE_CREATE,
  'template:read': Permission.TEMPLATE_READ,
  'template:update': Permission.TEMPLATE_UPDATE,
  'template:delete': Permission.TEMPLATE_DELETE,
  'message:send': Permission.MESSAGE_SEND,
  'webhook:manage': Permission.WEBHOOK_MANAGE
}

// ============================================================================
// ROLE ASSIGNMENT
// ============================================================================

/**
 * Role assignment request (for updating user role)
 */
export interface RoleAssignmentRequest {
  user_id: string
  role: UserRole
}

/**
 * Role assignment response
 */
export interface RoleAssignmentResponse {
  user_id: string
  role: UserRole
  permissions: Permission[]
  message: string
}

/**
 * Role assignment validation result
 */
export interface RoleAssignmentValidation {
  is_valid: boolean
  reason: string
}

// ============================================================================
// PERMISSION UTILITIES
// ============================================================================

/**
 * Check if a role has a specific permission
 */
export function hasPermission(role: UserRole, permission: Permission): boolean {
  const roleDef = ROLE_DEFINITIONS[role]
  return roleDef ? roleDef.permissions.includes(permission) : false
}

/**
 * Check if a role has any of the specified permissions
 */
export function hasAnyPermission(role: UserRole, permissions: Permission[]): boolean {
  return permissions.some(p => hasPermission(role, p))
}

/**
 * Check if a role has all of the specified permissions
 */
export function hasAllPermissions(role: UserRole, permissions: Permission[]): boolean {
  return permissions.every(p => hasPermission(role, p))
}

/**
 * Get all permissions for a user role
 */
export function getUserPermissions(role: UserRole): Permission[] {
  const roleDef = ROLE_DEFINITIONS[role]
  return roleDef ? [...roleDef.permissions] : []
}

/**
 * Check if user can access a resource with specific action
 */
export function canAccessResource(
  userRole: UserRole,
  resource: PermissionResource,
  action: PermissionAction,
  resourceOwnerRole?: UserRole
): PermissionCheckResponse {
  const permissionKey = `${resource}:${action}`
  const requiredPermission = PERMISSION_MAP[permissionKey]

  if (!requiredPermission) {
    return {
      allowed: false,
      reason: `Unknown resource action: ${permissionKey}`
    }
  }

  const hasBasePermission = hasPermission(userRole, requiredPermission)

  // Hierarchical security check
  if (resourceOwnerRole && hasBasePermission) {
    const userLevel = ROLE_DEFINITIONS[userRole]?.security_level
    const ownerLevel = ROLE_DEFINITIONS[resourceOwnerRole]?.security_level

    const levelHierarchy: Record<SecurityLevel, number> = {
      [SecurityLevel.PUBLIC]: 0,
      [SecurityLevel.AUTHENTICATED]: 1,
      [SecurityLevel.VERIFIED]: 2,
      [SecurityLevel.PRIVILEGED]: 3,
      [SecurityLevel.RESTRICTED]: 4
    }

    const userLevelValue = userLevel ? levelHierarchy[userLevel] : 0
    const ownerLevelValue = ownerLevel ? levelHierarchy[ownerLevel] : 0

    if (userLevelValue < ownerLevelValue) {
      return {
        allowed: false,
        reason: 'Insufficient security level',
        required_permission: requiredPermission
      }
    }
  }

  return {
    allowed: hasBasePermission,
    reason: hasBasePermission ? undefined : `Missing permission: ${requiredPermission}`,
    required_permission: requiredPermission
  }
}

/**
 * Validate if a role can be assigned based on email domain
 */
export function validateRoleAssignment(
  userEmail: string,
  proposedRole: UserRole,
  currentUserRole?: UserRole
): RoleAssignmentValidation {
  const domain = extractDomain(userEmail)
  if (!domain) {
    return { is_valid: false, reason: 'Invalid email format' }
  }

  const roleDef = ROLE_DEFINITIONS[proposedRole]

  // Check if current user has permission to assign this role
  if (currentUserRole) {
    if (!canAssignRole(currentUserRole, proposedRole)) {
      return { is_valid: false, reason: `Insufficient permissions to assign role ${proposedRole}` }
    }
  }

  // Check domain restrictions
  if (roleDef.restricted_domains?.includes(domain)) {
    return { is_valid: false, reason: `Domain ${domain} is restricted for role ${proposedRole}` }
  }

  // Check allowed domains for privileged roles
  if (
    roleDef.security_level === SecurityLevel.PRIVILEGED ||
    roleDef.security_level === SecurityLevel.RESTRICTED
  ) {
    if (roleDef.allowed_domains && !roleDef.allowed_domains.includes(domain)) {
      return { is_valid: false, reason: `Domain ${domain} is not approved for restricted role ${proposedRole}` }
    }
  }

  return { is_valid: true, reason: 'Role assignment valid' }
}

/**
 * Extract domain from email address
 */
function extractDomain(email: string): string | null {
  const parts = email.toLowerCase().split('@')
  if (parts.length !== 2 || !parts[0] || !parts[1]) {
    return null
  }
  return parts[1]
}

/**
 * Check if one role can assign another role
 */
function canAssignRole(assignerRole: UserRole, targetRole: UserRole): boolean {
  // Admin can assign doctor role
  if (assignerRole === UserRole.ADMIN && targetRole === UserRole.DOCTOR) {
    return true
  }
  // Admins cannot assign other admin roles (requires super admin, which doesn't exist yet)
  return false
}

/**
 * Get human-readable permission name
 */
export function getPermissionName(permission: Permission): string {
  const names: Record<Permission, string> = {
    [Permission.USER_CREATE]: 'Criar Usuários',
    [Permission.USER_READ]: 'Visualizar Usuários',
    [Permission.USER_UPDATE]: 'Editar Usuários',
    [Permission.USER_DELETE]: 'Excluir Usuários',
    [Permission.USER_LIST]: 'Listar Usuários',
    [Permission.USER_IMPERSONATE]: 'Impersonar Usuários',
    [Permission.PATIENT_CREATE]: 'Criar Pacientes',
    [Permission.PATIENT_READ]: 'Visualizar Pacientes',
    [Permission.PATIENT_UPDATE]: 'Editar Pacientes',
    [Permission.PATIENT_DELETE]: 'Excluir Pacientes',
    [Permission.PATIENT_LIST]: 'Listar Pacientes',
    [Permission.PATIENT_MEDICAL_RECORDS]: 'Registros Médicos',
    [Permission.PATIENT_SENSITIVE_DATA]: 'Dados Sensíveis',
    [Permission.QUIZ_CREATE]: 'Criar Questionários',
    [Permission.QUIZ_READ]: 'Visualizar Questionários',
    [Permission.QUIZ_UPDATE]: 'Editar Questionários',
    [Permission.QUIZ_DELETE]: 'Excluir Questionários',
    [Permission.QUIZ_PUBLISH]: 'Publicar Questionários',
    [Permission.QUIZ_RESULTS_VIEW]: 'Ver Resultados',
    [Permission.QUIZ_ANALYTICS]: 'Analytics de Questionários',
    [Permission.REPORT_CREATE]: 'Criar Relatórios',
    [Permission.REPORT_READ]: 'Visualizar Relatórios',
    [Permission.REPORT_UPDATE]: 'Editar Relatórios',
    [Permission.REPORT_DELETE]: 'Excluir Relatórios',
    [Permission.REPORT_EXPORT]: 'Exportar Relatórios',
    [Permission.ANALYTICS_VIEW]: 'Visualizar Analytics',
    [Permission.ANALYTICS_ADVANCED]: 'Analytics Avançado',
    [Permission.ADMIN_PANEL]: 'Painel Administrativo',
    [Permission.ADMIN_SETTINGS]: 'Configurações',
    [Permission.ADMIN_LOGS]: 'Logs do Sistema',
    [Permission.ADMIN_BACKUP]: 'Backup',
    [Permission.ADMIN_RESTORE]: 'Restaurar',
    [Permission.ADMIN_MAINTENANCE]: 'Manutenção',
    [Permission.AI_ACCESS]: 'Acesso à IA',
    [Permission.AI_CONFIGURE]: 'Configurar IA',
    [Permission.FLOW_CREATE]: 'Criar Fluxos',
    [Permission.FLOW_EXECUTE]: 'Executar Fluxos',
    [Permission.FLOW_MANAGE]: 'Gerenciar Fluxos',
    [Permission.TEMPLATE_CREATE]: 'Criar Templates',
    [Permission.TEMPLATE_READ]: 'Visualizar Templates',
    [Permission.TEMPLATE_UPDATE]: 'Editar Templates',
    [Permission.TEMPLATE_DELETE]: 'Excluir Templates',
    [Permission.TEMPLATE_PUBLISH]: 'Publicar Templates',
    [Permission.MESSAGE_SEND]: 'Enviar Mensagens',
    [Permission.MESSAGE_BROADCAST]: 'Broadcast de Mensagens',
    [Permission.NOTIFICATION_MANAGE]: 'Gerenciar Notificações',
    [Permission.API_ACCESS]: 'Acesso à API',
    [Permission.API_RATE_LIMIT_BYPASS]: 'Bypass de Rate Limit',
    [Permission.WEBHOOK_MANAGE]: 'Gerenciar Webhooks',
    [Permission.INTEGRATION_MANAGE]: 'Gerenciar Integrações'
  }
  return names[permission] || permission
}
