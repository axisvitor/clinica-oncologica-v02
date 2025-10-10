/**
 * Unit Tests for ReAuthenticationModal Component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReAuthenticationModal } from '@/components/auth/ReAuthenticationModal'

describe('ReAuthenticationModal', () => {
  const mockOnOpenChange = vi.fn()
  const mockOnSuccess = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render when open', () => {
    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    expect(screen.getByText('Confirmar identidade')).toBeInTheDocument()
    expect(
      screen.getByText('Por segurança, confirme sua senha atual antes de continuar.')
    ).toBeInTheDocument()
  })

  it('should not render when closed', () => {
    render(
      <ReAuthenticationModal
        open={false}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    expect(screen.queryByText('Confirmar identidade')).not.toBeInTheDocument()
  })

  it('should display custom title and description', () => {
    const customTitle = 'Verificação Necessária'
    const customDescription = 'Digite sua senha para continuar com esta ação.'

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        title={customTitle}
        description={customDescription}
      />
    )

    expect(screen.getByText(customTitle)).toBeInTheDocument()
    expect(screen.getByText(customDescription)).toBeInTheDocument()
  })

  it('should display error message when provided', () => {
    const errorMessage = 'Senha incorreta. Tente novamente.'

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
        error={errorMessage}
      />
    )

    expect(screen.getByText(errorMessage)).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveClass('destructive')
  })

  it('should call onSuccess with password when form is submitted', async () => {
    const user = userEvent.setup()
    const testPassword = 'TestPassword123!'

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    const passwordInput = screen.getByPlaceholderText('Digite sua senha atual')
    const confirmButton = screen.getByRole('button', { name: /confirmar/i })

    await user.type(passwordInput, testPassword)
    await user.click(confirmButton)

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalledWith(testPassword)
    })
  })

  it('should show validation error for empty password', async () => {
    const user = userEvent.setup()

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    const confirmButton = screen.getByRole('button', { name: /confirmar/i })
    await user.click(confirmButton)

    await waitFor(() => {
      expect(screen.getByText('Senha é obrigatória')).toBeInTheDocument()
    })

    expect(mockOnSuccess).not.toHaveBeenCalled()
  })

  it('should disable form during submission', async () => {
    const user = userEvent.setup()
    const slowOnSuccess = vi.fn(() => new Promise(resolve => setTimeout(resolve, 1000)))

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={slowOnSuccess}
      />
    )

    const passwordInput = screen.getByPlaceholderText('Digite sua senha atual')
    const confirmButton = screen.getByRole('button', { name: /confirmar/i })
    const cancelButton = screen.getByRole('button', { name: /cancelar/i })

    await user.type(passwordInput, 'TestPassword123!')
    await user.click(confirmButton)

    // Check that form elements are disabled during submission
    await waitFor(() => {
      expect(passwordInput).toBeDisabled()
      expect(confirmButton).toBeDisabled()
      expect(cancelButton).toBeDisabled()
    })

    // Check loading state
    expect(screen.getByText('Verificando...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /verificando/i })).toHaveClass('disabled')
  })

  it('should clear form when modal is closed', async () => {
    const user = userEvent.setup()

    const { rerender } = render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    const passwordInput = screen.getByPlaceholderText('Digite sua senha atual')
    await user.type(passwordInput, 'TestPassword123!')

    expect(passwordInput).toHaveValue('TestPassword123!')

    // Close modal
    const cancelButton = screen.getByRole('button', { name: /cancelar/i })
    await user.click(cancelButton)

    expect(mockOnOpenChange).toHaveBeenCalledWith(false)

    // Reopen modal - form should be cleared
    rerender(
      <ReAuthenticationModal
        open={false}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    rerender(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    const newPasswordInput = screen.getByPlaceholderText('Digite sua senha atual')
    expect(newPasswordInput).toHaveValue('')
  })

  it('should call onOpenChange when cancel button is clicked', async () => {
    const user = userEvent.setup()

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    const cancelButton = screen.getByRole('button', { name: /cancelar/i })
    await user.click(cancelButton)

    expect(mockOnOpenChange).toHaveBeenCalledWith(false)
  })

  it('should handle async onSuccess callbacks', async () => {
    const user = userEvent.setup()
    const asyncOnSuccess = vi.fn(async (password: string) => {
      await new Promise(resolve => setTimeout(resolve, 100))
      return password
    })

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={asyncOnSuccess}
      />
    )

    const passwordInput = screen.getByPlaceholderText('Digite sua senha atual')
    const confirmButton = screen.getByRole('button', { name: /confirmar/i })

    await user.type(passwordInput, 'TestPassword123!')
    await user.click(confirmButton)

    await waitFor(() => {
      expect(asyncOnSuccess).toHaveBeenCalledWith('TestPassword123!')
    })

    // Form should be cleared after async success
    await waitFor(() => {
      expect(passwordInput).toHaveValue('')
    })
  })

  it('should have proper accessibility attributes', () => {
    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    const passwordInput = screen.getByPlaceholderText('Digite sua senha atual')
    expect(passwordInput).toHaveAttribute('type', 'password')
    expect(passwordInput).toHaveAttribute('autoComplete', 'current-password')
    expect(passwordInput).toHaveAttribute('autoFocus')

    const form = screen.getByRole('form', { hidden: true })
    expect(form).toBeInTheDocument()
  })

  it('should display shield icon', () => {
    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    const icons = screen.getAllByTestId(/shield/i)
    expect(icons.length).toBeGreaterThan(0)
  })

  it('should handle onSuccess errors gracefully', async () => {
    const user = userEvent.setup()
    const errorOnSuccess = vi.fn(async () => {
      throw new Error('Authentication failed')
    })

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={errorOnSuccess}
      />
    )

    const passwordInput = screen.getByPlaceholderText('Digite sua senha atual')
    const confirmButton = screen.getByRole('button', { name: /confirmar/i })

    await user.type(passwordInput, 'TestPassword123!')
    await user.click(confirmButton)

    await waitFor(() => {
      expect(errorOnSuccess).toHaveBeenCalled()
    })

    expect(consoleSpy).toHaveBeenCalledWith(
      'Re-authentication error:',
      expect.any(Error)
    )

    consoleSpy.mockRestore()
  })
})

describe('ReAuthenticationModal Keyboard Navigation', () => {
  const mockOnOpenChange = vi.fn()
  const mockOnSuccess = vi.fn()

  it('should support Enter key to submit', async () => {
    const user = userEvent.setup()

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    const passwordInput = screen.getByPlaceholderText('Digite sua senha atual')
    await user.type(passwordInput, 'TestPassword123!{Enter}')

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalledWith('TestPassword123!')
    })
  })

  it('should support Escape key to close', async () => {
    const user = userEvent.setup()

    render(
      <ReAuthenticationModal
        open={true}
        onOpenChange={mockOnOpenChange}
        onSuccess={mockOnSuccess}
      />
    )

    await user.keyboard('{Escape}')

    expect(mockOnOpenChange).toHaveBeenCalledWith(false)
  })
})
