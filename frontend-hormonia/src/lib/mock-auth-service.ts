/// <reference types="vite/client" />

/**
 * Mock Authentication Service
 * Temporary authentication service for MVP development
 * Will be replaced with Firebase Auth when frontend is complete
 */

import { createLogger } from './logger'

const logger = createLogger('MockAuthService')

export interface MockUser {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'medico' | 'user'
  is_active: boolean
  permissions: string[]
  created_at: string
  updated_at?: string
  last_login?: string

  // Medico-specific fields
  crm?: string
  especialidade?: string
  conselho_regional?: string
  pacientes_atribuidos?: string[]
}

export interface MockSession {
  access_token: string
  refresh_token: string
  expires_at: number
  user: MockUser
}

export interface MockAuthResponse {
  success: boolean
  user?: MockUser
  session?: MockSession
  error?: string
}

// Mock users database
const MOCK_USERS: MockUser[] = [
  // Admin users
  {
    id: 'admin-001',
    email: 'admin@sistema.com',
    full_name: 'Administrador Sistema',
    role: 'admin',
    is_active: true,
    permissions: ['*'],
    created_at: '2024-01-01T00:00:00-03:00'
  },
  {
    id: 'admin-002',
    email: 'admin2@sistema.com',
    full_name: 'Admin Secundário',
    role: 'admin',
    is_active: true,
    permissions: ['read:*', 'write:*', 'delete:patients', 'manage:users'],
    created_at: '2024-01-15T00:00:00-03:00'
  },

  // Medico users
  {
    id: 'medico-001',
    email: '123456@medico.local',
    full_name: 'Dr. Carlos Silva',
    role: 'medico',
    is_active: true,
    permissions: ['read:pacientes', 'write:consultas', 'read:exames', 'write:prescricoes'],
    created_at: '2024-01-10T00:00:00-03:00',
    crm: '123456',
    especialidade: 'Oncologia',
    conselho_regional: 'CRM-SC',
    pacientes_atribuidos: ['patient-001', 'patient-002', 'patient-003']
  },
  {
    id: 'medico-002',
    email: '789012@medico.local',
    full_name: 'Dra. Maria Santos',
    role: 'medico',
    is_active: true,
    permissions: ['read:pacientes', 'write:consultas', 'read:exames', 'write:prescricoes'],
    created_at: '2024-01-12T00:00:00-03:00',
    crm: '789012',
    especialidade: 'Oncologia Clínica',
    conselho_regional: 'CRM-SC',
    pacientes_atribuidos: ['patient-004', 'patient-005']
  },
  {
    id: 'medico-003',
    email: '345678@medico.local',
    full_name: 'Dr. João Oliveira',
    role: 'medico',
    is_active: true,
    permissions: ['read:pacientes', 'write:consultas', 'read:exames', 'write:prescricoes'],
    created_at: '2024-01-20T00:00:00-03:00',
    crm: '345678',
    especialidade: 'Radioterapia',
    conselho_regional: 'CRM-SC',
    pacientes_atribuidos: ['patient-006']
  },

  // Regular users
  {
    id: 'user-001',
    email: 'user@sistema.com',
    full_name: 'Usuário Teste',
    role: 'user',
    is_active: true,
    permissions: ['read:pacientes', 'read:mensagens'],
    created_at: '2024-02-01T00:00:00-03:00'
  }
]

// Default password for all mock users
const MOCK_PASSWORD = 'senha123'

// Session storage
const SESSION_KEY = 'mock_auth_session'
const TOKEN_PREFIX = 'mock_token_'

/**
 * Generate mock token
 */
function generateMockToken(userId: string): string {
  const timestamp = Date.now()
  const random = Math.random().toString(36).substring(7)
  return `${TOKEN_PREFIX}${userId}_${timestamp}_${random}`
}

/**
 * Simulate network delay
 */
async function simulateDelay(min = 300, max = 800): Promise<void> {
  const delay = Math.floor(Math.random() * (max - min + 1)) + min
  return new Promise(resolve => setTimeout(resolve, delay))
}

/**
 * Get stored session
 */
export function getMockSession(): MockSession | null {
  try {
    const stored = localStorage.getItem(SESSION_KEY)
    if (!stored) return null

    const session: MockSession = JSON.parse(stored)

    // Check if session expired
    if (session.expires_at < Date.now()) {
      localStorage.removeItem(SESSION_KEY)
      return null
    }

    return session
  } catch (error) {
    logger.error('Error getting session', { error })
    return null
  }
}

/**
 * Store session
 */
function storeMockSession(session: MockSession): void {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  } catch (error) {
    logger.error('Error storing session', { error })
  }
}

/**
 * Clear session
 */
function clearMockSession(): void {
  localStorage.removeItem(SESSION_KEY)
}

/**
 * Find user by email
 */
function findUserByEmail(email: string): MockUser | null {
  return MOCK_USERS.find(u => u.email.toLowerCase() === email.toLowerCase()) || null
}

/**
 * Mock sign in with email and password
 */
export async function mockSignIn(email: string, password: string): Promise<MockAuthResponse> {
  logger.debug('Attempting sign in', { email })

  await simulateDelay()

  // Find user
  const user = findUserByEmail(email)

  if (!user) {
    logger.error('User not found', { email })
    return {
      success: false,
      error: 'Usuário não encontrado'
    }
  }

  // Check if user is active
  if (!user.is_active) {
    logger.error('User is inactive', { email })
    return {
      success: false,
      error: 'Usuário inativo'
    }
  }

  // Validate password
  if (password !== MOCK_PASSWORD) {
    logger.error('Invalid password')
    return {
      success: false,
      error: 'Senha incorreta'
    }
  }

  // Update last login
  const updatedUser = {
    ...user,
    last_login: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }

  // Create session
  const session: MockSession = {
    access_token: generateMockToken(user.id),
    refresh_token: generateMockToken(user.id + '_refresh'),
    expires_at: Date.now() + (60 * 60 * 1000), // 1 hour
    user: updatedUser
  }

  storeMockSession(session)

  logger.info('Sign in successful', { email: user.email, role: user.role })

  return {
    success: true,
    user: updatedUser,
    session
  }
}

/**
 * Mock sign out
 */
export async function mockSignOut(): Promise<{ success: boolean; error?: string }> {
  logger.debug('Signing out')

  await simulateDelay(100, 300)

  clearMockSession()

  logger.info('Sign out successful')

  return { success: true }
}

/**
 * Get current user from session
 */
export function mockGetCurrentUser(): MockUser | null {
  const session = getMockSession()
  return session?.user || null
}

/**
 * Check if user is authenticated
 */
export function mockIsAuthenticated(): boolean {
  return getMockSession() !== null
}

/**
 * Refresh session (extend expiry)
 */
export async function mockRefreshSession(): Promise<MockAuthResponse> {
  logger.debug('Refreshing session')

  await simulateDelay(200, 400)

  const currentSession = getMockSession()

  if (!currentSession) {
    logger.warn('No active session to refresh')
    return {
      success: false,
      error: 'No active session'
    }
  }

  // Extend session
  const newSession: MockSession = {
    ...currentSession,
    access_token: generateMockToken(currentSession.user.id),
    refresh_token: generateMockToken(currentSession.user.id + '_refresh'),
    expires_at: Date.now() + (60 * 60 * 1000) // 1 hour
  }

  storeMockSession(newSession)

  logger.debug('Session refreshed', { userId: currentSession.user.id })

  return {
    success: true,
    user: currentSession.user,
    session: newSession
  }
}

/**
 * Validate user has permission
 */
export function mockHasPermission(permission: string): boolean {
  const user = mockGetCurrentUser()
  if (!user) return false

  // Admin with * has all permissions
  if (user.permissions.includes('*')) return true

  // Check specific permission
  if (user.permissions.includes(permission)) return true

  // Check wildcard permissions (e.g., "read:*" matches "read:pacientes")
  return user.permissions.some(p => {
    if (p.endsWith(':*')) {
      const prefix = p.split(':')[0]
      return permission.startsWith(prefix + ':')
    }
    return false
  })
}

/**
 * Validate user has role
 */
export function mockHasRole(role: string): boolean {
  const user = mockGetCurrentUser()
  if (!user) return false
  return user.role === role
}

/**
 * Get mock users for development (only expose in dev mode)
 */
export function getMockUsersForDev(): Array<{ email: string; role: string; name: string }> {
  if (import.meta.env.DEV) {
    return MOCK_USERS.map(u => ({
      email: u.email,
      role: u.role,
      name: u.full_name
    }))
  }
  return []
}

/**
 * Get default password for development
 */
export function getMockPasswordForDev(): string {
  if (import.meta.env.DEV) {
    return MOCK_PASSWORD
  }
  return ''
}

export default {
  signIn: mockSignIn,
  signOut: mockSignOut,
  getCurrentUser: mockGetCurrentUser,
  isAuthenticated: mockIsAuthenticated,
  refreshSession: mockRefreshSession,
  hasPermission: mockHasPermission,
  hasRole: mockHasRole,
  getSession: getMockSession,
  getMockUsersForDev,
  getMockPasswordForDev
}
