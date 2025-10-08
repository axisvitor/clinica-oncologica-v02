import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QuizProgress } from '@/components/quiz/QuizProgress';

describe('QuizProgress Component', () => {
  const defaultProps = {
    currentStep: 3,
    totalSteps: 10,
    percentage: 30,
    showStepIndicator: true,
    showPercentage: true,
    animated: true,
  };

  describe('Rendering', () => {
    it('should render progress bar with correct percentage', () => {
      render(<QuizProgress {...defaultProps} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute('aria-valuenow', '30');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });

    it('should display step indicator when enabled', () => {
      render(<QuizProgress {...defaultProps} />);

      expect(screen.getByText('Etapa 3 de 10')).toBeInTheDocument();
    });

    it('should hide step indicator when disabled', () => {
      render(<QuizProgress {...defaultProps} showStepIndicator={false} />);

      expect(screen.queryByText(/Etapa/)).not.toBeInTheDocument();
    });

    it('should display percentage when enabled', () => {
      render(<QuizProgress {...defaultProps} />);

      expect(screen.getByText('30%')).toBeInTheDocument();
    });

    it('should hide percentage when disabled', () => {
      render(<QuizProgress {...defaultProps} showPercentage={false} />);

      expect(screen.queryByText('30%')).not.toBeInTheDocument();
    });

    it('should render with custom className', () => {
      const { container } = render(
        <QuizProgress {...defaultProps} className="custom-progress" />
      );

      const progressElement = container.querySelector('.custom-progress');
      expect(progressElement).toBeInTheDocument();
    });

    it('should render with custom colors', () => {
      const { container } = render(
        <QuizProgress
          {...defaultProps}
          progressColor="bg-green-500"
          backgroundColor="bg-gray-200"
        />
      );

      const progressBar = container.querySelector('.bg-green-500');
      const background = container.querySelector('.bg-gray-200');
      expect(progressBar).toBeInTheDocument();
      expect(background).toBeInTheDocument();
    });
  });

  describe('Progress Calculation', () => {
    it('should calculate percentage from steps when percentage not provided', () => {
      render(
        <QuizProgress
          currentStep={5}
          totalSteps={10}
          showPercentage={true}
        />
      );

      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('should handle zero total steps', () => {
      render(
        <QuizProgress
          currentStep={0}
          totalSteps={0}
          showPercentage={true}
        />
      );

      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('should handle current step greater than total', () => {
      render(
        <QuizProgress
          currentStep={15}
          totalSteps={10}
          showPercentage={true}
        />
      );

      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('should round percentage to nearest integer', () => {
      render(
        <QuizProgress
          currentStep={1}
          totalSteps={3}
          showPercentage={true}
        />
      );

      expect(screen.getByText('33%')).toBeInTheDocument();
    });
  });

  describe('Animation', () => {
    it('should apply animation classes when enabled', () => {
      const { container } = render(
        <QuizProgress {...defaultProps} animated={true} />
      );

      const progressBar = container.querySelector('.transition-all');
      expect(progressBar).toBeInTheDocument();
    });

    it('should not apply animation classes when disabled', () => {
      const { container } = render(
        <QuizProgress {...defaultProps} animated={false} />
      );

      const progressBar = container.querySelector('.transition-all');
      expect(progressBar).not.toBeInTheDocument();
    });

    it('should animate width changes', async () => {
      const { rerender, container } = render(
        <QuizProgress {...defaultProps} percentage={20} />
      );

      const progressBar = container.querySelector('[role="progressbar"] > div');
      expect(progressBar).toHaveStyle('width: 20%');

      rerender(<QuizProgress {...defaultProps} percentage={60} />);

      await waitFor(() => {
        expect(progressBar).toHaveStyle('width: 60%');
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(<QuizProgress {...defaultProps} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-label', 'Quiz progress');
      expect(progressBar).toHaveAttribute('aria-valuenow', '30');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });

    it('should support custom aria-label', () => {
      render(
        <QuizProgress
          {...defaultProps}
          ariaLabel="Progresso do questionário"
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-label', 'Progresso do questionário');
    });

    it('should announce progress changes to screen readers', () => {
      const { rerender } = render(
        <QuizProgress {...defaultProps} percentage={30} />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '30');

      rerender(<QuizProgress {...defaultProps} percentage={50} />);
      expect(progressBar).toHaveAttribute('aria-valuenow', '50');
    });
  });

  describe('Responsive Design', () => {
    it('should hide percentage on small screens', () => {
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

      render(
        <QuizProgress {...defaultProps} hidePercentageOnMobile={true} />
      );

      expect(screen.queryByText('30%')).not.toBeInTheDocument();
    });

    it('should adjust height for mobile', () => {
      const { container } = render(
        <QuizProgress {...defaultProps} mobileHeight="h-2" desktopHeight="h-4" />
      );

      const progressBar = container.querySelector('.h-2.md\\:h-4');
      expect(progressBar).toBeInTheDocument();
    });
  });

  describe('Variants', () => {
    it('should render linear variant', () => {
      const { container } = render(
        <QuizProgress {...defaultProps} variant="linear" />
      );

      const linearProgress = container.querySelector('.rounded-full');
      expect(linearProgress).toBeInTheDocument();
    });

    it('should render segmented variant', () => {
      render(
        <QuizProgress
          {...defaultProps}
          variant="segmented"
          segments={10}
        />
      );

      const segments = screen.getAllByTestId(/segment-/);
      expect(segments).toHaveLength(10);
    });

    it('should highlight active segments', () => {
      const { container } = render(
        <QuizProgress
          currentStep={3}
          totalSteps={5}
          variant="segmented"
          segments={5}
        />
      );

      const activeSegments = container.querySelectorAll('.bg-blue-500');
      expect(activeSegments).toHaveLength(3);
    });
  });

  describe('Integration', () => {
    it('should work with quiz context', () => {
      const mockQuizContext = {
        currentQuestion: 5,
        totalQuestions: 20,
        progress: 25,
      };

      render(
        <QuizProgress
          currentStep={mockQuizContext.currentQuestion}
          totalSteps={mockQuizContext.totalQuestions}
          percentage={mockQuizContext.progress}
        />
      );

      expect(screen.getByText('Etapa 5 de 20')).toBeInTheDocument();
      expect(screen.getByText('25%')).toBeInTheDocument();
    });

    it('should handle progress updates', () => {
      const { rerender } = render(
        <QuizProgress currentStep={1} totalSteps={10} />
      );

      expect(screen.getByText('Etapa 1 de 10')).toBeInTheDocument();

      rerender(<QuizProgress currentStep={5} totalSteps={10} />);
      expect(screen.getByText('Etapa 5 de 10')).toBeInTheDocument();

      rerender(<QuizProgress currentStep={10} totalSteps={10} />);
      expect(screen.getByText('Etapa 10 de 10')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should handle negative values', () => {
      render(
        <QuizProgress
          currentStep={-1}
          totalSteps={10}
          percentage={-10}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '0');
    });

    it('should handle invalid percentage values', () => {
      render(
        <QuizProgress
          {...defaultProps}
          percentage={150}
        />
      );

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '100');
    });

    it('should handle missing props gracefully', () => {
      render(<QuizProgress />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute('aria-valuenow', '0');
    });
  });
});