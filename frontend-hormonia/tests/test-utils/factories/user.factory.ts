/**
 * User Test Data Factory
 * Provides reusable test data for user/admin-related tests
 */

export interface User {
  id: string;
  email: string;
  nome: string;
  role: 'admin' | 'medico' | 'enfermeiro' | 'assistente';
  permissions: string[];
  created_at: string;
  last_login: string | null;
  active: boolean;
}

let userIdCounter = 1;

export const createMockUser = (role: User['role'] = 'admin', overrides?: Partial<User>): User => {
  const permissions = {
    admin: ['read', 'write', 'delete', 'manage_users', 'view_reports'],
    medico: ['read', 'write', 'view_patients', 'view_reports'],
    enfermeiro: ['read', 'write', 'view_patients'],
    assistente: ['read', 'view_patients'],
  };

  return {
    id: `user-${userIdCounter++}`,
    email: `user${userIdCounter}@example.com`,
    nome: `Usuário ${userIdCounter}`,
    role,
    permissions: permissions[role],
    created_at: '2024-01-01T00:00:00Z',
    last_login: null,
    active: true,
    ...overrides,
  };
};

export const createAdminUser = (overrides?: Partial<User>): User =>
  createMockUser('admin', {
    email: 'admin@example.com',
    nome: 'Administrador',
    ...overrides,
  });

export const createMedicoUser = (overrides?: Partial<User>): User =>
  createMockUser('medico', {
    email: 'medico@example.com',
    nome: 'Dr. João Silva',
    ...overrides,
  });

export const createMockUsers = (count: number, role: User['role'] = 'medico'): User[] =>
  Array.from({ length: count }, () => createMockUser(role));

export const resetUserCounter = () => {
  userIdCounter = 1;
};
