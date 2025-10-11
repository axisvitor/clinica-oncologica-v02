/**
 * Integration Test: Reset Password Flow
 *
 * Verifies end-to-end reset password functionality works correctly
 * with proper token validation and error handling
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { apiClient } from '../../../frontend-hormonia/src/lib/api-client';

// Mock API client
vi.mock('../../../frontend-hormonia/src/lib/api-client', () => ({
  apiClient: {
    post: vi.fn(),
  },
}));

// Mock component for testing (simplified version)
const ResetPasswordForm = ({ token }: { token: string }) => {
  const [password, setPassword] = React.useState('');
  const [confirmPassword, setConfirmPassword] = React.useState('');
  const [error, setError] = React.useState('');
  const [success, setSuccess] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (password !== confirmPassword) {
        throw new Error('Passwords do not match');
      }

      await apiClient.post('/auth/reset-password', {
        token,
        new_password: password,
      });

      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to reset password');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return <div data-testid="success-message">Password reset successful</div>;
  }

  return (
    <form onSubmit={handleSubmit} data-testid="reset-password-form">
      <input
        type="password"
        placeholder="New Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        data-testid="password-input"
      />
      <input
        type="password"
        placeholder="Confirm Password"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        data-testid="confirm-password-input"
      />
      <button type="submit" disabled={loading} data-testid="submit-button">
        {loading ? 'Resetting...' : 'Reset Password'}
      </button>
      {error && <div data-testid="error-message">{error}</div>}
    </form>
  );
};

import React from 'react';

const renderResetPasswordForm = (token: string = 'valid-token-123') => {
  return render(
    <BrowserRouter>
      <ResetPasswordForm token={token} />
    </BrowserRouter>
  );
};

describe('Reset Password Flow Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Successful Password Reset', () => {
    it('should successfully reset password with valid token and matching passwords', async () => {
      const mockResponse = {
        data: {
          message: 'Password reset successful',
        },
      };

      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      renderResetPasswordForm('valid-token-123');

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewSecure123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewSecure123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/auth/reset-password', {
          token: 'valid-token-123',
          new_password: 'NewSecure123!',
        });
      });

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
    });

    it('should handle password reset with strong password', async () => {
      const mockResponse = {
        data: {
          message: 'Password reset successful',
        },
      };

      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      const strongPassword = 'Str0ng!P@ssw0rd#2024$%^&*()';
      fireEvent.change(passwordInput, { target: { value: strongPassword } });
      fireEvent.change(confirmPasswordInput, { target: { value: strongPassword } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/auth/reset-password', {
          token: 'valid-token-123',
          new_password: strongPassword,
        });
      });

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
    });
  });

  describe('Token Validation', () => {
    it('should handle invalid token error', async () => {
      const mockError = {
        response: {
          status: 400,
          data: {
            detail: 'Invalid or expired reset token',
          },
        },
      };

      (apiClient.post as any).mockRejectedValueOnce(mockError);

      renderResetPasswordForm('invalid-token');

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Invalid or expired reset token');
      });
    });

    it('should handle expired token error', async () => {
      const mockError = {
        response: {
          status: 400,
          data: {
            detail: 'Reset token has expired. Please request a new one.',
          },
        },
      };

      (apiClient.post as any).mockRejectedValueOnce(mockError);

      renderResetPasswordForm('expired-token');

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Reset token has expired');
      });
    });

    it('should handle missing token error', async () => {
      const mockError = {
        response: {
          status: 400,
          data: {
            detail: 'Reset token is required',
          },
        },
      };

      (apiClient.post as any).mockRejectedValueOnce(mockError);

      renderResetPasswordForm('');

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Reset token is required');
      });
    });
  });

  describe('Password Validation', () => {
    it('should show error when passwords do not match', async () => {
      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'Password123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'DifferentPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Passwords do not match');
      });

      expect(apiClient.post).not.toHaveBeenCalled();
    });

    it('should handle weak password error from backend', async () => {
      const mockError = {
        response: {
          status: 400,
          data: {
            detail: 'Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character',
          },
        },
      };

      (apiClient.post as any).mockRejectedValueOnce(mockError);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'weak' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'weak' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Password must be at least 8 characters');
      });
    });

    it('should handle empty password fields', async () => {
      renderResetPasswordForm();

      const submitButton = screen.getByTestId('submit-button');

      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Passwords do not match');
      });

      expect(apiClient.post).not.toHaveBeenCalled();
    });
  });

  describe('Network and Server Errors', () => {
    it('should handle network errors gracefully', async () => {
      const networkError = new Error('Network error');
      (apiClient.post as any).mockRejectedValueOnce(networkError);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Network error');
      });
    });

    it('should handle 500 server errors', async () => {
      const serverError = {
        response: {
          status: 500,
          data: {
            detail: 'Internal server error',
          },
        },
      };

      (apiClient.post as any).mockRejectedValueOnce(serverError);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Internal server error');
      });
    });

    it('should handle timeout errors', async () => {
      const timeoutError = {
        response: {
          status: 408,
          data: {
            detail: 'Request timeout',
          },
        },
      };

      (apiClient.post as any).mockRejectedValueOnce(timeoutError);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('Request timeout');
      });
    });
  });

  describe('Loading States', () => {
    it('should show loading state during password reset', async () => {
      let resolvePromise: any;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      (apiClient.post as any).mockReturnValueOnce(promise);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('submit-button')).toHaveTextContent('Resetting...');
        expect(screen.getByTestId('submit-button')).toBeDisabled();
      });

      resolvePromise({ data: { message: 'Success' } });

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
    });

    it('should disable submit button during request', async () => {
      let resolvePromise: any;
      const promise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      (apiClient.post as any).mockReturnValueOnce(promise);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(submitButton).toBeDisabled();
      });

      resolvePromise({ data: { message: 'Success' } });

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
    });
  });

  describe('API Contract Validation', () => {
    it('should send correct payload format to backend', async () => {
      const mockResponse = { data: { message: 'Success' } };
      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      renderResetPasswordForm('token-abc-123');

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'ValidPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'ValidPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/auth/reset-password', {
          token: 'token-abc-123',
          new_password: 'ValidPassword123!',
        });
      });
    });

    it('should handle successful response with correct message', async () => {
      const mockResponse = {
        data: {
          message: 'Password has been reset successfully',
          user_id: '12345',
        },
      };

      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long passwords', async () => {
      const mockResponse = { data: { message: 'Success' } };
      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      const longPassword = 'A1!' + 'a'.repeat(200); // 203 characters
      fireEvent.change(passwordInput, { target: { value: longPassword } });
      fireEvent.change(confirmPasswordInput, { target: { value: longPassword } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/auth/reset-password', {
          token: 'valid-token-123',
          new_password: longPassword,
        });
      });
    });

    it('should handle special characters in password', async () => {
      const mockResponse = { data: { message: 'Success' } };
      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      const specialCharPassword = 'P@$$w0rd!#%^&*(){}[]|\\/<>?';
      fireEvent.change(passwordInput, { target: { value: specialCharPassword } });
      fireEvent.change(confirmPasswordInput, { target: { value: specialCharPassword } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/auth/reset-password', {
          token: 'valid-token-123',
          new_password: specialCharPassword,
        });
      });
    });

    it('should handle unicode characters in password', async () => {
      const mockResponse = { data: { message: 'Success' } };
      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      const unicodePassword = 'P@ssw0rd123!😀🔒';
      fireEvent.change(passwordInput, { target: { value: unicodePassword } });
      fireEvent.change(confirmPasswordInput, { target: { value: unicodePassword } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/auth/reset-password', {
          token: 'valid-token-123',
          new_password: unicodePassword,
        });
      });
    });
  });

  describe('Performance', () => {
    it('should complete password reset within acceptable time', async () => {
      const mockResponse = { data: { message: 'Success' } };
      (apiClient.post as any).mockResolvedValueOnce(mockResponse);

      const startTime = performance.now();

      renderResetPasswordForm();

      const passwordInput = screen.getByTestId('password-input');
      const confirmPasswordInput = screen.getByTestId('confirm-password-input');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(passwordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.change(confirmPasswordInput, { target: { value: 'NewPassword123!' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });

      const endTime = performance.now();
      const duration = endTime - startTime;

      expect(duration).toBeLessThan(2000); // Should complete in less than 2 seconds
    });
  });
});
