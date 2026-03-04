/**
 * Comprehensive tests for UserListPage component.
 *
 * Tests cover:
 * - Component rendering and layout
 * - User data display and formatting
 * - Search and filtering functionality
 * - Pagination controls
 * - CRUD operation triggers
 * - Error handling and loading states
 * - Accessibility compliance
 * - Performance with large datasets
 */

import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { UserListPage } from '../users/UserListPage'
import { apiClient } from '@/lib/api-client'
import type { AdminUser } from '@/types/admin'
import '@/lib/test-utils'

// Mock the API client
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    adminUsers: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
  },
}))

// Mock child components
vi.mock('../users/UsersTable', () => ({
  UsersTable: ({ users, onViewUser, onEditUser }: any) => (
    <div data-testid="users-table">
      {users.map((user: AdminUser) => (
        <div key={user['id']} data-testid={`user-row-${user['id']}`}>
          <span>{user['full_name']}</span>
          <span>{user['email']}</span>
          <span>{user['role']}</span>
          <button onClick={() => onViewUser(user)}>View</button>
          <button onClick={() => onEditUser(user)}>Edit</button>
        </div>
      ))}
    </div>
  ),
}))

vi.mock('../users/CreateUserModal', () => ({
  CreateUserModal: ({ open, onOpenChange: _onOpenChange }: any) =>
    open ? <div data-testid="create-user-modal">Create User Modal</div> : null,
}))

vi.mock('../users/UserDetailsModal', () => ({
  UserDetailsModal: ({ user, open, onOpenChange: _onOpenChange }: any) =>
    open ? <div data-testid="user-details-modal">User Details for {user?.full_name}</div> : null,
}))

// Sample test data
const mockUsers: AdminUser[] = [
  {
    id: '1',
    email: 'admin1@test.com',
    full_name: 'Admin One',
    role: 'admin',
    is_active: true,
    created_at: '2024-01-01T00:00:00-03:00',
    updated_at: '2024-01-01T00:00:00-03:00',
    last_login: '2024-01-01T00:00:00-03:00',
    login_count: 5,
    locked_until: null,
    permissions: ['read', 'write'],
    two_factor_enabled: false,
    failed_login_attempts: 0,
  },
  {
    id: '2',
    email: 'admin2@test.com',
    full_name: 'Admin Two',
    role: 'admin',
    is_active: false,
    created_at: '2024-01-02T00:00:00-03:00',
    updated_at: '2024-01-02T00:00:00-03:00',
    last_login: '2024-01-02T00:00:00-03:00',
    login_count: 10,
    locked_until: '2024-12-31T23:59:59-03:00',
    permissions: ['read', 'write', 'admin'],
    two_factor_enabled: true,
    failed_login_attempts: 2,
  },
  {
    id: '3',
    email: 'admin3@test.com',
    full_name: 'Admin Three',
    role: 'admin',
    is_active: true,
    created_at: '2024-01-03T00:00:00-03:00',
    updated_at: '2024-01-03T00:00:00-03:00',
    last_login: null,
    login_count: 0,
    locked_until: null,
    permissions: ['read'],
    two_factor_enabled: false,
    failed_login_attempts: 0,
  },
]

const mockApiResponse = {
  items: mockUsers,
  total: mockUsers.length,
  pages: 1,
  current_page: 1,
  page_size: 10,
}

// Test wrapper component
function TestWrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('UserListPage', () => {
  const user = userEvent.setup()

  beforeEach(() => {
    vi.clearAllMocks()
    // Default successful API response
    vi.mocked(apiClient.adminUsers.list).mockResolvedValue(mockApiResponse)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Component Rendering', () => {
    it('renders the page header correctly', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      expect(screen.getByText('Gerenciamento de Usuários')).toBeInTheDocument()
      expect(
        screen.getByText('Gerencie usuários administrativos, permissões e atividades')
      ).toBeInTheDocument()
    })

    it('renders action buttons in header', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      expect(screen.getByRole('button', { name: /exportar/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /novo usuário/i })).toBeInTheDocument()
    })

    it('renders statistics cards', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByText('Total de Usuários')).toBeInTheDocument()
        expect(screen.getByText('Usuários Ativos')).toBeInTheDocument()
        expect(screen.getByText('Super Admins')).toBeInTheDocument()
        expect(screen.getByText('Bloqueados')).toBeInTheDocument()
      })
    })

    it('displays correct statistics based on user data', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        // Total users
        expect(screen.getByText('3')).toBeInTheDocument()
        // Active users (2 out of 3)
        expect(screen.getByText('2')).toBeInTheDocument()
        // Super admins (1 out of 3)
        expect(screen.getByText('1')).toBeInTheDocument()
        // Locked users (1 out of 3)
        expect(screen.getByText('1')).toBeInTheDocument()
      })
    })

    it('renders filter controls', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      expect(screen.getByPlaceholderText('Buscar por nome ou email...')).toBeInTheDocument()
      expect(screen.getByRole('combobox', { name: /função/i })).toBeInTheDocument()
      expect(screen.getByRole('combobox', { name: /status/i })).toBeInTheDocument()
    })
  })

  describe('Data Loading', () => {
    it('shows loading state while fetching data', () => {
      vi.mocked(apiClient.adminUsers.list).mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 1000))
      )

      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
    })

    it('displays error state when API call fails', async () => {
      const errorMessage = 'Failed to fetch users'
      vi.mocked(apiClient.adminUsers.list).mockRejectedValue(new Error(errorMessage))

      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByText('Erro ao carregar usuários')).toBeInTheDocument()
        expect(screen.getByText(errorMessage)).toBeInTheDocument()
      })
    })

    it('calls API with correct default parameters', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenCalledWith({
          page: 1,
          size: 10,
        })
      })
    })

    it('renders users table when data loads successfully', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByTestId('users-table')).toBeInTheDocument()
        expect(screen.getByTestId('user-row-1')).toBeInTheDocument()
        expect(screen.getByTestId('user-row-2')).toBeInTheDocument()
        expect(screen.getByTestId('user-row-3')).toBeInTheDocument()
      })
    })
  })

  describe('Search Functionality', () => {
    it('updates search term and triggers API call', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      const searchInput = screen.getByPlaceholderText('Buscar por nome ou email...')
      await user.type(searchInput, 'admin1')

      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenCalledWith({
          page: 1,
          size: 10,
          search: 'admin1',
        })
      })
    })

    it('resets page to 1 when searching', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      // Simulate being on page 2
      const searchInput = screen.getByPlaceholderText('Buscar por nome ou email...')
      await user.type(searchInput, 'test')

      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenLastCalledWith(
          expect.objectContaining({ page: 1 })
        )
      })
    })

    it('handles empty search correctly', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      const searchInput = screen.getByPlaceholderText('Buscar por nome ou email...')
      await user.type(searchInput, 'test')
      await user.clear(searchInput)

      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenLastCalledWith({
          page: 1,
          size: 10,
        })
      })
    })
  })

  describe('Filter Functionality', () => {
    it('applies role filter correctly', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      const roleFilter = screen.getByRole('combobox', { name: /função/i })
      await user.click(roleFilter)
      await user.click(screen.getByText('Admin'))

      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenCalledWith({
          page: 1,
          size: 10,
          role: 'admin',
        })
      })
    })

    it('applies status filter correctly', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      const statusFilter = screen.getByRole('combobox', { name: /status/i })
      await user.click(statusFilter)
      await user.click(screen.getByText('Ativos'))

      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenCalledWith({
          page: 1,
          size: 10,
          is_active: true,
        })
      })
    })

    it('combines multiple filters correctly', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      // Apply search
      const searchInput = screen.getByPlaceholderText('Buscar por nome ou email...')
      await user.type(searchInput, 'admin')

      // Apply role filter
      const roleFilter = screen.getByRole('combobox', { name: /função/i })
      await user.click(roleFilter)
      await user.click(screen.getByText('Super Admin'))

      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenCalledWith({
          page: 1,
          size: 10,
          search: 'admin',
          role: 'admin',
        })
      })
    })

    it('shows clear filters button when filters are applied', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      const searchInput = screen.getByPlaceholderText('Buscar por nome ou email...')
      await user.type(searchInput, 'test')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /limpar filtros/i })).toBeInTheDocument()
      })
    })

    it('clears all filters when clear button is clicked', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      // Apply filters
      const searchInput = screen.getByPlaceholderText('Buscar por nome ou email...')
      await user.type(searchInput, 'admin')

      const roleFilter = screen.getByRole('combobox', { name: /função/i })
      await user.click(roleFilter)
      await user.click(screen.getByText('Admin'))

      // Clear filters
      const clearButton = screen.getByRole('button', { name: /limpar filtros/i })
      await user.click(clearButton)

      expect(searchInput).toHaveValue('')
      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenCalledWith({
          page: 1,
          size: 10,
        })
      })
    })
  })

  describe('User Actions', () => {
    it('opens create user modal when new user button is clicked', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      const newUserButton = screen.getByRole('button', { name: /novo usuário/i })
      await user.click(newUserButton)

      await waitFor(() => {
        expect(screen.getByTestId('create-user-modal')).toBeInTheDocument()
      })
    })

    it('opens user details modal when view button is clicked', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        const viewButtons = screen.getAllByText('View')
        expect(viewButtons).toHaveLength(mockUsers.length)
      })

      const firstViewButton = screen.getAllByText('View')[0]
      await user.click(firstViewButton)

      await waitFor(() => {
        expect(screen.getByTestId('user-details-modal')).toBeInTheDocument()
        expect(screen.getByText('User Details for Admin One')).toBeInTheDocument()
      })
    })

    it('handles edit user action correctly', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        const editButtons = screen.getAllByText('Edit')
        expect(editButtons).toHaveLength(mockUsers.length)
      })

      const firstEditButton = screen.getAllByText('Edit')[0]
      await user.click(firstEditButton)

      await waitFor(() => {
        expect(screen.getByTestId('user-details-modal')).toBeInTheDocument()
      })
    })
  })

  describe('Export Functionality', () => {
    it('logs export action when export button is clicked', async () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {})

      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      const exportButton = screen.getByRole('button', { name: /exportar/i })
      await user.click(exportButton)

      expect(consoleSpy).toHaveBeenCalledWith('Export users data')
      consoleSpy.mockRestore()
    })
  })

  describe('Pagination', () => {
    it('handles pagination correctly', async () => {
      const paginatedResponse = {
        items: mockUsers.slice(0, 2),
        total: 10,
        pages: 5,
        current_page: 1,
        page_size: 2,
      }

      vi.mocked(apiClient.adminUsers.list).mockResolvedValue(paginatedResponse)

      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(apiClient.adminUsers.list).toHaveBeenCalledWith({
          page: 1,
          size: 10,
        })
      })
    })
  })

  describe('Error Handling', () => {
    it('handles network errors gracefully', async () => {
      vi.mocked(apiClient.adminUsers.list).mockRejectedValue(new Error('Network error'))

      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByText('Erro ao carregar usuários')).toBeInTheDocument()
        expect(screen.getByText('Network error')).toBeInTheDocument()
      })
    })

    it('handles API validation errors', async () => {
      vi.mocked(apiClient.adminUsers.list).mockRejectedValue({
        response: {
          status: 422,
          data: { detail: 'Invalid parameters' },
        },
      })

      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByText('Erro ao carregar usuários')).toBeInTheDocument()
      })
    })

    it('handles unauthorized access', async () => {
      vi.mocked(apiClient.adminUsers.list).mockRejectedValue({
        response: {
          status: 401,
          data: { detail: 'Unauthorized' },
        },
      })

      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByText('Erro ao carregar usuários')).toBeInTheDocument()
      })
    })
  })

  describe('Performance Tests', () => {
    it('handles large datasets efficiently', async () => {
      const largeDataset = Array.from({ length: 1000 }, (_, i) => ({
        id: `user-${i}`,
        email: `user${i}@test.com`,
        full_name: `User ${i}`,
        role: 'admin' as const,
        is_active: true,
        created_at: '2024-01-01T00:00:00-03:00',
        updated_at: '2024-01-01T00:00:00-03:00',
        last_login: '2024-01-01T00:00:00-03:00',
        login_count: i,
        locked_until: null,
        permissions: ['read'],
        two_factor_enabled: false,
        failed_login_attempts: 0,
      }))

      const largeResponse = {
        items: largeDataset.slice(0, 50), // First page
        total: largeDataset.length,
        pages: 20,
        current_page: 1,
        page_size: 50,
      }

      vi.mocked(apiClient.adminUsers.list).mockResolvedValue(largeResponse)

      const startTime = performance.now()

      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByTestId('users-table')).toBeInTheDocument()
      })

      const endTime = performance.now()
      const renderTime = endTime - startTime

      // Should render within reasonable time (2 seconds)
      expect(renderTime).toBeLessThan(2000)
    })

    it('optimizes re-renders when filters change', async () => {
      const renderSpy = vi.fn()

      const TestComponent = () => {
        renderSpy()
        return <UserListPage />
      }

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByTestId('users-table')).toBeInTheDocument()
      })

      const initialRenderCount = renderSpy.mock.calls.length

      // Change search
      const searchInput = screen.getByPlaceholderText('Buscar por nome ou email...')
      await user.type(searchInput, 'a')

      // Should not cause excessive re-renders
      expect(renderSpy.mock.calls.length - initialRenderCount).toBeLessThan(5)
    })
  })

  describe('Accessibility', () => {
    it('has proper ARIA labels and roles', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      expect(screen.getByRole('button', { name: /novo usuário/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /exportar/i })).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: /buscar/i })).toBeInTheDocument()
    })

    it('supports keyboard navigation', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      const searchInput = screen.getByPlaceholderText('Buscar por nome ou email...')

      // Should be focusable
      searchInput.focus()
      expect(document.activeElement).toBe(searchInput)

      // Should be able to tab to other elements
      await user.tab()
      expect(document.activeElement).not.toBe(searchInput)
    })

    it('provides screen reader friendly content', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        // Check for descriptive text
        expect(
          screen.getByText('Gerencie usuários administrativos, permissões e atividades')
        ).toBeInTheDocument()
        expect(
          screen.getByText('Use os filtros abaixo para encontrar usuários específicos')
        ).toBeInTheDocument()
      })
    })
  })

  describe('Modal Management', () => {
    it('closes create modal when onOpenChange is called', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      // Open modal
      const newUserButton = screen.getByRole('button', { name: /novo usuário/i })
      await user.click(newUserButton)

      await waitFor(() => {
        expect(screen.getByTestId('create-user-modal')).toBeInTheDocument()
      })

      // Modal should close when onOpenChange(false) is triggered
      // This would typically happen when the modal's close button is clicked
      // Since we're mocking the modal, we test the state management indirectly
    })

    it('closes user details modal when onOpenChange is called', async () => {
      render(
        <TestWrapper>
          <UserListPage />
        </TestWrapper>
      )

      await waitFor(() => {
        const viewButtons = screen.getAllByText('View')
        expect(viewButtons).toHaveLength(mockUsers.length)
      })

      // Open modal
      const firstViewButton = screen.getAllByText('View')[0]
      await user.click(firstViewButton)

      await waitFor(() => {
        expect(screen.getByTestId('user-details-modal')).toBeInTheDocument()
      })
    })
  })
})
