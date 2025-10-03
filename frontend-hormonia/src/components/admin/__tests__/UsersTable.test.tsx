/**
 * Comprehensive tests for UsersTable component.
 *
 * Tests cover:
 * - Data display and formatting
 * - Sorting functionality
 * - Row actions (view, edit, delete)
 * - Pagination controls
 * - Loading and empty states
 * - Row selection and bulk actions
 * - Accessibility compliance
 * - Performance with large datasets
 */

import React from 'react'
import { render, screen, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { UsersTable } from '../users/UsersTable'
import type { AdminUser } from '@/types/admin'
import '@/lib/test-utils'

// Mock icons
vi.mock('lucide-react', () => ({
  MoreHorizontal: () => <div data-testid="more-icon" />,
  Eye: () => <div data-testid="eye-icon" />,
  Edit: () => <div data-testid="edit-icon" />,
  Trash2: () => <div data-testid="trash-icon" />,
  Shield: () => <div data-testid="shield-icon" />,
  Clock: () => <div data-testid="clock-icon" />,
  Lock: () => <div data-testid="lock-icon" />,
  ArrowUpDown: () => <div data-testid="sort-icon" />,
  ChevronLeft: () => <div data-testid="chevron-left" />,
  ChevronRight: () => <div data-testid="chevron-right" />
}))

// Sample test data
const mockUsers: AdminUser[] = [
  {
    id: '1',
    email: 'admin1@test.com',
    full_name: 'Admin One',
    role: 'admin',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    last_login: '2024-01-01T10:00:00Z',
    login_count: 5,
    locked_until: null,
    permissions: ['read', 'write'],
    two_factor_enabled: false,
    failed_login_attempts: 0
  },
  {
    id: '2',
    email: 'superadmin@test.com',
    full_name: 'Super Admin',
    role: 'admin',
    is_active: false,
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
    last_login: '2024-01-02T15:30:00Z',
    login_count: 25,
    locked_until: '2024-12-31T23:59:59Z',
    permissions: ['read', 'write', 'admin'],
    two_factor_enabled: true,
    failed_login_attempts: 3
  },
  {
    id: '3',
    email: 'newuser@test.com',
    full_name: 'New User',
    role: 'admin',
    is_active: true,
    created_at: '2024-01-03T00:00:00Z',
    updated_at: '2024-01-03T00:00:00Z',
    last_login: null,
    login_count: 0,
    locked_until: null,
    permissions: ['read'],
    two_factor_enabled: false,
    failed_login_attempts: 0
  }
]

const defaultProps = {
  users: mockUsers,
  currentPage: 1,
  totalPages: 1,
  onPageChange: vi.fn(),
  onViewUser: vi.fn(),
  onEditUser: vi.fn(),
  onDeleteUser: vi.fn(),
  onToggleStatus: vi.fn(),
  onBulkAction: vi.fn(),
  loading: false,
  selectedUsers: [],
  onUserSelect: vi.fn(),
  sortBy: 'created_at' as const,
  sortOrder: 'desc' as const,
  onSort: vi.fn()
}

describe('UsersTable', () => {
  const user = userEvent.setup()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Component Rendering', () => {
    it('renders table headers correctly', () => {
      render(<UsersTable {...defaultProps} />)

      expect(screen.getByText('Nome')).toBeInTheDocument()
      expect(screen.getByText('Email')).toBeInTheDocument()
      expect(screen.getByText('Função')).toBeInTheDocument()
      expect(screen.getByText('Status')).toBeInTheDocument()
      expect(screen.getByText('Último Login')).toBeInTheDocument()
      expect(screen.getByText('Criado em')).toBeInTheDocument()
      expect(screen.getByText('Ações')).toBeInTheDocument()
    })

    it('renders user data in table rows', () => {
      render(<UsersTable {...defaultProps} />)

      mockUsers.forEach(user => {
        expect(screen.getByText(user['full_name'])).toBeInTheDocument()
        expect(screen.getByText(user['email'])).toBeInTheDocument()
      })
    })

    it('displays correct role labels', () => {
      render(<UsersTable {...defaultProps} />)

      expect(screen.getByText('Admin')).toBeInTheDocument()
      expect(screen.getByText('Super Admin')).toBeInTheDocument()
    })

    it('shows active/inactive status correctly', () => {
      render(<UsersTable {...defaultProps} />)

      const activeStatuses = screen.getAllByText('Ativo')
      const inactiveStatuses = screen.getAllByText('Inativo')

      expect(activeStatuses).toHaveLength(2) // Users 1 and 3 are active
      expect(inactiveStatuses).toHaveLength(1) // User 2 is inactive
    })

    it('formats dates correctly', () => {
      render(<UsersTable {...defaultProps} />)

      // Check that dates are displayed (exact format may vary)
      expect(screen.getByText(/01\/01\/2024/)).toBeInTheDocument()
      expect(screen.getByText(/02\/01\/2024/)).toBeInTheDocument()
      expect(screen.getByText(/03\/01\/2024/)).toBeInTheDocument()
    })

    it('handles null last_login correctly', () => {
      render(<UsersTable {...defaultProps} />)

      expect(screen.getByText('Nunca')).toBeInTheDocument()
    })

    it('shows locked status when user is locked', () => {
      render(<UsersTable {...defaultProps} />)

      // User 2 is locked
      expect(screen.getByTestId('lock-icon')).toBeInTheDocument()
    })
  })

  describe('Empty State', () => {
    it('displays empty state when no users', () => {
      render(<UsersTable {...defaultProps} users={[]} />)

      expect(screen.getByText('Nenhum usuário encontrado')).toBeInTheDocument()
      expect(screen.getByText('Não há usuários cadastrados ou que atendam aos filtros aplicados.')).toBeInTheDocument()
    })

    it('shows create user suggestion in empty state', () => {
      render(<UsersTable {...defaultProps} users={[]} />)

      expect(screen.getByText('Crie um novo usuário para começar.')).toBeInTheDocument()
    })
  })

  describe('Loading State', () => {
    it('shows loading skeletons when loading', () => {
      render(<UsersTable {...defaultProps} loading={true} />)

      // Should show skeleton rows instead of actual data
      const skeletons = screen.getAllByTestId('skeleton-row')
      expect(skeletons).toHaveLength(5) // Default skeleton count
    })

    it('does not show user data when loading', () => {
      render(<UsersTable {...defaultProps} loading={true} />)

      // Should not show actual user names
      expect(screen.queryByText('Admin One')).not.toBeInTheDocument()
    })
  })

  describe('Sorting Functionality', () => {
    it('shows sort icons in sortable headers', () => {
      render(<UsersTable {...defaultProps} />)

      const sortIcons = screen.getAllByTestId('sort-icon')
      expect(sortIcons.length).toBeGreaterThan(0)
    })

    it('calls onSort when header is clicked', async () => {
      const onSort = vi.fn()
      render(<UsersTable {...defaultProps} onSort={onSort} />)

      const nameHeader = screen.getByText('Nome')
      await user.click(nameHeader)

      expect(onSort).toHaveBeenCalledWith('full_name')
    })

    it('calls onSort for email column', async () => {
      const onSort = vi.fn()
      render(<UsersTable {...defaultProps} onSort={onSort} />)

      const emailHeader = screen.getByText('Email')
      await user.click(emailHeader)

      expect(onSort).toHaveBeenCalledWith('email')
    })

    it('calls onSort for creation date', async () => {
      const onSort = vi.fn()
      render(<UsersTable {...defaultProps} onSort={onSort} />)

      const createdHeader = screen.getByText('Criado em')
      await user.click(createdHeader)

      expect(onSort).toHaveBeenCalledWith('created_at')
    })

    it('displays current sort indicator', () => {
      render(<UsersTable {...defaultProps} sortBy="full_name" sortOrder="asc" />)

      // Should show visual indicator for current sort
      const nameHeader = screen.getByText('Nome')
      expect(nameHeader.closest('th')).toHaveClass('sorted-asc') // Assuming CSS class
    })
  })

  describe('Row Actions', () => {
    it('shows action menu for each user', () => {
      render(<UsersTable {...defaultProps} />)

      const actionMenus = screen.getAllByTestId('more-icon')
      expect(actionMenus).toHaveLength(mockUsers.length)
    })

    it('calls onViewUser when view action is clicked', async () => {
      const onViewUser = vi.fn()
      render(<UsersTable {...defaultProps} onViewUser={onViewUser} />)

      // Open first user's action menu
      const firstActionMenu = screen.getAllByTestId('more-icon')[0]
      await user.click(firstActionMenu)

      // Click view action
      const viewAction = screen.getByText('Visualizar')
      await user.click(viewAction)

      expect(onViewUser).toHaveBeenCalledWith(mockUsers[0])
    })

    it('calls onEditUser when edit action is clicked', async () => {
      const onEditUser = vi.fn()
      render(<UsersTable {...defaultProps} onEditUser={onEditUser} />)

      // Open first user's action menu
      const firstActionMenu = screen.getAllByTestId('more-icon')[0]
      await user.click(firstActionMenu)

      // Click edit action
      const editAction = screen.getByText('Editar')
      await user.click(editAction)

      expect(onEditUser).toHaveBeenCalledWith(mockUsers[0])
    })

    it('calls onDeleteUser when delete action is clicked', async () => {
      const onDeleteUser = vi.fn()
      render(<UsersTable {...defaultProps} onDeleteUser={onDeleteUser} />)

      // Open first user's action menu
      const firstActionMenu = screen.getAllByTestId('more-icon')[0]
      await user.click(firstActionMenu)

      // Click delete action
      const deleteAction = screen.getByText('Excluir')
      await user.click(deleteAction)

      expect(onDeleteUser).toHaveBeenCalledWith(mockUsers[0])
    })

    it('calls onToggleStatus when status toggle is clicked', async () => {
      const onToggleStatus = vi.fn()
      render(<UsersTable {...defaultProps} onToggleStatus={onToggleStatus} />)

      // Open first user's action menu
      const firstActionMenu = screen.getAllByTestId('more-icon')[0]
      await user.click(firstActionMenu)

      // Click status toggle action
      const toggleAction = screen.getByText('Desativar') // Active user should show "Desativar"
      await user.click(toggleAction)

      expect(onToggleStatus).toHaveBeenCalledWith(mockUsers[0])
    })

    it('shows correct toggle text for active/inactive users', async () => {
      render(<UsersTable {...defaultProps} />)

      // Open active user's menu (user 1)
      const firstActionMenu = screen.getAllByTestId('more-icon')[0]
      await user.click(firstActionMenu)
      expect(screen.getByText('Desativar')).toBeInTheDocument()

      // Close first menu and open inactive user's menu (user 2)
      await user.click(firstActionMenu) // Close menu
      const secondActionMenu = screen.getAllByTestId('more-icon')[1]
      await user.click(secondActionMenu)
      expect(screen.getByText('Ativar')).toBeInTheDocument()
    })
  })

  describe('Row Selection', () => {
    it('shows checkboxes when onUserSelect is provided', () => {
      render(<UsersTable {...defaultProps} />)

      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes).toHaveLength(mockUsers.length + 1) // +1 for select all
    })

    it('calls onUserSelect when individual checkbox is clicked', async () => {
      const onUserSelect = vi.fn()
      render(<UsersTable {...defaultProps} onUserSelect={onUserSelect} />)

      const firstCheckbox = screen.getAllByRole('checkbox')[1] // Skip select all
      await user.click(firstCheckbox)

      expect(onUserSelect).toHaveBeenCalledWith(mockUsers[0].id, true)
    })

    it('calls onUserSelect for select all checkbox', async () => {
      const onUserSelect = vi.fn()
      render(<UsersTable {...defaultProps} onUserSelect={onUserSelect} />)

      const selectAllCheckbox = screen.getAllByRole('checkbox')[0]
      await user.click(selectAllCheckbox)

      expect(onUserSelect).toHaveBeenCalledWith('all', true)
    })

    it('shows selected state correctly', () => {
      render(<UsersTable {...defaultProps} selectedUsers={['1', '2']} />)

      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes[1]).toBeChecked() // First user
      expect(checkboxes[2]).toBeChecked() // Second user
      expect(checkboxes[3]).not.toBeChecked() // Third user
    })

    it('shows indeterminate state for select all when some selected', () => {
      render(<UsersTable {...defaultProps} selectedUsers={['1']} />)

      const selectAllCheckbox = screen.getAllByRole('checkbox')[0]
      expect(selectAllCheckbox).toHaveProperty('indeterminate', true)
    })
  })

  describe('Pagination', () => {
    const paginationProps = {
      ...defaultProps,
      currentPage: 2,
      totalPages: 5
    }

    it('shows pagination controls when multiple pages', () => {
      render(<UsersTable {...paginationProps} />)

      expect(screen.getByText('Página 2 de 5')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /anterior/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /próxima/i })).toBeInTheDocument()
    })

    it('disables previous button on first page', () => {
      render(<UsersTable {...defaultProps} currentPage={1} totalPages={5} />)

      const prevButton = screen.getByRole('button', { name: /anterior/i })
      expect(prevButton).toBeDisabled()
    })

    it('disables next button on last page', () => {
      render(<UsersTable {...defaultProps} currentPage={5} totalPages={5} />)

      const nextButton = screen.getByRole('button', { name: /próxima/i })
      expect(nextButton).toBeDisabled()
    })

    it('calls onPageChange when pagination buttons are clicked', async () => {
      const onPageChange = vi.fn()
      render(<UsersTable {...paginationProps} onPageChange={onPageChange} />)

      const nextButton = screen.getByRole('button', { name: /próxima/i })
      await user.click(nextButton)

      expect(onPageChange).toHaveBeenCalledWith(3)

      const prevButton = screen.getByRole('button', { name: /anterior/i })
      await user.click(prevButton)

      expect(onPageChange).toHaveBeenCalledWith(1)
    })

    it('hides pagination when only one page', () => {
      render(<UsersTable {...defaultProps} totalPages={1} />)

      expect(screen.queryByText(/página/i)).not.toBeInTheDocument()
    })
  })

  describe('Bulk Actions', () => {
    it('shows bulk action bar when users are selected', () => {
      render(<UsersTable {...defaultProps} selectedUsers={['1', '2']} />)

      expect(screen.getByText('2 usuários selecionados')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /ativar/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /desativar/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /excluir/i })).toBeInTheDocument()
    })

    it('calls onBulkAction for bulk activate', async () => {
      const onBulkAction = vi.fn()
      render(<UsersTable {...defaultProps} selectedUsers={['1', '2']} onBulkAction={onBulkAction} />)

      const activateButton = screen.getByRole('button', { name: /ativar/i })
      await user.click(activateButton)

      expect(onBulkAction).toHaveBeenCalledWith('activate', ['1', '2'])
    })

    it('calls onBulkAction for bulk deactivate', async () => {
      const onBulkAction = vi.fn()
      render(<UsersTable {...defaultProps} selectedUsers={['1', '2']} onBulkAction={onBulkAction} />)

      const deactivateButton = screen.getByRole('button', { name: /desativar/i })
      await user.click(deactivateButton)

      expect(onBulkAction).toHaveBeenCalledWith('deactivate', ['1', '2'])
    })

    it('calls onBulkAction for bulk delete', async () => {
      const onBulkAction = vi.fn()
      render(<UsersTable {...defaultProps} selectedUsers={['1', '2']} onBulkAction={onBulkAction} />)

      const deleteButton = screen.getByRole('button', { name: /excluir/i })
      await user.click(deleteButton)

      expect(onBulkAction).toHaveBeenCalledWith('delete', ['1', '2'])
    })

    it('hides bulk action bar when no users selected', () => {
      render(<UsersTable {...defaultProps} selectedUsers={[]} />)

      expect(screen.queryByText(/usuários selecionados/i)).not.toBeInTheDocument()
    })
  })

  describe('Performance', () => {
    it('handles large datasets efficiently', () => {
      const largeUserSet = Array.from({ length: 1000 }, (_, i) => ({
        id: `user-${i}`,
        email: `user${i}@test.com`,
        full_name: `User ${i}`,
        role: 'admin' as const,
        is_active: i % 2 === 0,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        last_login: i % 3 === 0 ? '2024-01-01T00:00:00Z' : null,
        login_count: i,
        locked_until: null,
        permissions: ['read'],
    two_factor_enabled: false,
    failed_login_attempts: 0
      }))

      const startTime = performance.now()

      render(<UsersTable {...defaultProps} users={largeUserSet} />)

      const endTime = performance.now()
      const renderTime = endTime - startTime

      // Should render within reasonable time
      expect(renderTime).toBeLessThan(1000) // 1 second max
    })

    it('optimizes re-renders for selection changes', () => {
      const renderSpy = vi.fn()

      const TestComponent = ({ selectedUsers }: { selectedUsers: string[] }) => {
        renderSpy()
        return <UsersTable {...defaultProps} selectedUsers={selectedUsers} />
      }

      const { rerender } = render(<TestComponent selectedUsers={[]} />)

      const initialRenderCount = renderSpy.mock.calls.length

      // Change selection
      rerender(<TestComponent selectedUsers={['1']} />)

      // Should not cause excessive re-renders
      expect(renderSpy.mock.calls.length - initialRenderCount).toBeLessThanOrEqual(2)
    })
  })

  describe('Accessibility', () => {
    it('has proper table structure for screen readers', () => {
      render(<UsersTable {...defaultProps} />)

      const table = screen.getByRole('table')
      expect(table).toBeInTheDocument()

      const columnHeaders = screen.getAllByRole('columnheader')
      expect(columnHeaders.length).toBeGreaterThan(0)

      const rows = screen.getAllByRole('row')
      expect(rows.length).toBe(mockUsers.length + 1) // +1 for header
    })

    it('provides accessible labels for actions', () => {
      render(<UsersTable {...defaultProps} />)

      const actionButtons = screen.getAllByLabelText(/ações para/i)
      expect(actionButtons).toHaveLength(mockUsers.length)
    })

    it('supports keyboard navigation for checkboxes', async () => {
      render(<UsersTable {...defaultProps} />)

      const firstCheckbox = screen.getAllByRole('checkbox')[1]

      firstCheckbox.focus()
      expect(document.activeElement).toBe(firstCheckbox)

      await user.keyboard('{space}')
      expect(defaultProps.onUserSelect).toHaveBeenCalled()
    })

    it('has accessible sort buttons', () => {
      render(<UsersTable {...defaultProps} />)

      const sortButtons = screen.getAllByRole('button', { name: /ordenar por/i })
      expect(sortButtons.length).toBeGreaterThan(0)
    })

    it('provides status indicators for screen readers', () => {
      render(<UsersTable {...defaultProps} />)

      // Should have aria-labels or text for status indicators
      const statusElements = screen.getAllByText(/ativo|inativo/i)
      expect(statusElements.length).toBeGreaterThan(0)
    })
  })

  describe('Error Handling', () => {
    it('handles undefined user data gracefully', () => {
      const usersWithUndefined = [
        ...mockUsers,
        {
          id: '4',
          email: undefined as any,
          full_name: undefined as any,
          role: 'admin' as const,
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          last_login: null,
          login_count: 0,
          locked_until: null,
          permissions: []
        }
      ]

      expect(() => {
        render(<UsersTable {...defaultProps} users={usersWithUndefined} />)
      }).not.toThrow()
    })

    it('handles invalid date formats gracefully', () => {
      const usersWithInvalidDates = [
        {
          ...mockUsers[0],
          created_at: 'invalid-date',
          last_login: 'another-invalid-date'
        }
      ]

      expect(() => {
        render(<UsersTable {...defaultProps} users={usersWithInvalidDates} />)
      }).not.toThrow()
    })
  })
})