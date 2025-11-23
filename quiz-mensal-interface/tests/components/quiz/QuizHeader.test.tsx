import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QuizHeader } from '@/components/quiz/QuizHeader';
import { useRouter } from 'next/navigation';

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

describe('QuizHeader Component', () => {
  const mockRouter = {
    push: jest.fn(),
    back: jest.fn(),
    refresh: jest.fn(),
  };

  const defaultProps = {
    title: 'Questionário Mensal',
    currentQuestion: 5,
    totalQuestions: 20,
    sessionId: 'test-session-123',
    patientName: 'Maria Silva',
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
  });

  describe('Rendering', () => {
    it('should render quiz header with all elements', () => {
      render(<QuizHeader {...defaultProps} />);

      expect(screen.getByText('Questionário Mensal')).toBeInTheDocument();
      expect(screen.getByText('Maria Silva')).toBeInTheDocument();
      expect(screen.getByText('Questão 5 de 20')).toBeInTheDocument();
    });

    it('should render with custom className', () => {
      const { container } = render(
        <QuizHeader {...defaultProps} className="custom-header" />
      );

      const header = container.querySelector('.custom-header');
      expect(header).toBeInTheDocument();
    });

    it('should render logout button when showLogout is true', () => {
      render(<QuizHeader {...defaultProps} showLogout={true} />);

      const logoutButton = screen.getByRole('button', { name: /sair/i });
      expect(logoutButton).toBeInTheDocument();
    });

    it('should render back button when showBack is true', () => {
      render(<QuizHeader {...defaultProps} showBack={true} />);

      const backButton = screen.getByRole('button', { name: /voltar/i });
      expect(backButton).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    it('should handle logout click', async () => {
      const onLogout = jest.fn();
      render(
        <QuizHeader
          {...defaultProps}
          showLogout={true}
          onLogout={onLogout}
        />
      );

      const logoutButton = screen.getByRole('button', { name: /sair/i });
      fireEvent.click(logoutButton);

      await waitFor(() => {
        expect(onLogout).toHaveBeenCalledTimes(1);
      });
    });

    it('should handle back navigation', () => {
      render(<QuizHeader {...defaultProps} showBack={true} />);

      const backButton = screen.getByRole('button', { name: /voltar/i });
      fireEvent.click(backButton);

      expect(mockRouter.back).toHaveBeenCalledTimes(1);
    });

    it('should show confirmation dialog on logout', async () => {
      render(
        <QuizHeader
          {...defaultProps}
          showLogout={true}
          confirmLogout={true}
        />
      );

      const logoutButton = screen.getByRole('button', { name: /sair/i });
      fireEvent.click(logoutButton);

      await waitFor(() => {
        expect(screen.getByText(/deseja realmente sair/i)).toBeInTheDocument();
      });
    });
  });

  describe('Progress Display', () => {
    it('should calculate and display progress percentage', () => {
      render(<QuizHeader {...defaultProps} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '25');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });

    it('should display 0% progress when on first question', () => {
      render(
        <QuizHeader
          {...defaultProps}
          currentQuestion={1}
          totalQuestions={20}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '5');
    });

    it('should display 100% progress when on last question', () => {
      render(
        <QuizHeader
          {...defaultProps}
          currentQuestion={20}
          totalQuestions={20}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '100');
    });
  });

  describe('Responsive Design', () => {
    it('should hide patient name on mobile', () => {
      // Mock window.matchMedia
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation(query => ({
          matches: query === '(max-width: 640px)',
          media: query,
          onchange: null,
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        })),
      });

      const { container } = render(<QuizHeader {...defaultProps} />);

      const patientName = container.querySelector('.hidden-mobile');
      expect(patientName).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<QuizHeader {...defaultProps} />);

      expect(screen.getByRole('banner')).toBeInTheDocument();
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should support keyboard navigation', () => {
      render(
        <QuizHeader
          {...defaultProps}
          showLogout={true}
          showBack={true}
        />
      );

      const backButton = screen.getByRole('button', { name: /voltar/i });
      const logoutButton = screen.getByRole('button', { name: /sair/i });

      backButton.focus();
      expect(backButton).toHaveFocus();

      // Tab to next button
      fireEvent.keyDown(backButton, { key: 'Tab' });
      logoutButton.focus();
      expect(logoutButton).toHaveFocus();
    });
  });

  describe('Error Handling', () => {
    it('should handle missing props gracefully', () => {
      const { container } = render(
        <QuizHeader
          title=""
          currentQuestion={0}
          totalQuestions={0}
          sessionId=""
        />
      );

      expect(container).toBeInTheDocument();
    });

    it('should handle invalid question numbers', () => {
      render(
        <QuizHeader
          {...defaultProps}
          currentQuestion={-1}
          totalQuestions={20}
        />
      );

      expect(screen.getByText(/questão/i)).toBeInTheDocument();
    });
  });

  describe('Session Management', () => {
    it('should display session ID when in debug mode', () => {
      process.env.NODE_ENV = 'development';

      render(
        <QuizHeader
          {...defaultProps}
          showDebugInfo={true}
        />
      );

      expect(screen.getByText(/test-session-123/)).toBeInTheDocument();
    });

    it('should not display session ID in production', () => {
      process.env.NODE_ENV = 'production';

      render(
        <QuizHeader
          {...defaultProps}
          showDebugInfo={true}
        />
      );

      expect(screen.queryByText(/test-session-123/)).not.toBeInTheDocument();
    });
  });
});